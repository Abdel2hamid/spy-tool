"""
App Tiering Service — classifies every App row into HOT / WARM / COLD
based on current rank, freshness, age, review count, and blowing-up score.

Tier rules (HOT wins over WARM wins over COLD):
  HOT:  current_rank <= 200
        OR freshness_score >= 80
        OR created_at >= now-3d
        OR blowing_up_score >= 60   (JOIN app_blowing_up_scores)

  WARM: current_rank <= 2000
        OR freshness_score >= 40
        OR current_reviews >= 100
        OR created_at >= now-30d

  COLD: everything else

Enrichment SLA driven by tier:
  HOT  → enrich within 1h
  WARM → enrich within 12h
  COLD → enrich within 7d

The single SQL UPDATE with CASE WHEN avoids N+1 queries and runs in
O(1) round trips regardless of table size.  Rows updated in the last 6h
are skipped to avoid thrashing.
"""

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

_RECLASSIFY_SQL = """
UPDATE apps
SET
    sync_tier = CASE
        WHEN apps.current_rank IS NOT NULL AND apps.current_rank <= 200
             THEN 'hot'
        WHEN apps.freshness_score >= 80
             THEN 'hot'
        WHEN apps.created_at >= NOW() - INTERVAL '3 days'
             THEN 'hot'
        WHEN abs_score.blowing_up_score >= 60
             THEN 'hot'
        WHEN apps.current_rank IS NOT NULL AND apps.current_rank <= 2000
             THEN 'warm'
        WHEN apps.freshness_score >= 40
             THEN 'warm'
        WHEN apps.current_reviews >= 100
             THEN 'warm'
        WHEN apps.created_at >= NOW() - INTERVAL '30 days'
             THEN 'warm'
        ELSE 'cold'
    END,
    tier_computed_at = NOW()
FROM (
    SELECT app_id, blowing_up_score
    FROM app_blowing_up_scores
) AS abs_score
WHERE apps.id = abs_score.app_id
  AND (
      apps.tier_computed_at IS NULL
      OR apps.tier_computed_at < NOW() - INTERVAL '6 hours'
  )
"""

# Separate UPDATE for apps with no blowing_up_scores row
_RECLASSIFY_SQL_NO_BUS = """
UPDATE apps
SET
    sync_tier = CASE
        WHEN apps.current_rank IS NOT NULL AND apps.current_rank <= 200
             THEN 'hot'
        WHEN apps.freshness_score >= 80
             THEN 'hot'
        WHEN apps.created_at >= NOW() - INTERVAL '3 days'
             THEN 'hot'
        WHEN apps.current_rank IS NOT NULL AND apps.current_rank <= 2000
             THEN 'warm'
        WHEN apps.freshness_score >= 40
             THEN 'warm'
        WHEN apps.current_reviews >= 100
             THEN 'warm'
        WHEN apps.created_at >= NOW() - INTERVAL '30 days'
             THEN 'warm'
        ELSE 'cold'
    END,
    tier_computed_at = NOW()
WHERE (
    apps.tier_computed_at IS NULL
    OR apps.tier_computed_at < NOW() - INTERVAL '6 hours'
)
  AND apps.id NOT IN (
      SELECT app_id FROM app_blowing_up_scores
  )
"""


class AppTieringService:
    """
    Classifies all App rows into HOT / WARM / COLD tiers.

    Usage::

        with SessionLocal() as db:
            updated = AppTieringService(db).reclassify_all()
    """

    def __init__(self, db: Session):
        self.db = db

    def reclassify_all(self) -> int:
        """
        Run the two-pass CASE WHEN UPDATE and return total rows updated.

        Pass 1: apps that have a blowing_up_scores row (JOIN path).
        Pass 2: apps without a blowing_up_scores row (NOT IN subquery path).

        Skips rows whose tier_computed_at < 6h ago to avoid thrash.
        """
        try:
            result1 = self.db.execute(text(_RECLASSIFY_SQL))
            self.db.commit()
            rows1 = result1.rowcount if result1.rowcount >= 0 else 0
        except Exception as exc:
            logger.error(f"[Tiering] Pass 1 failed: {exc}")
            self.db.rollback()
            rows1 = 0

        try:
            result2 = self.db.execute(text(_RECLASSIFY_SQL_NO_BUS))
            self.db.commit()
            rows2 = result2.rowcount if result2.rowcount >= 0 else 0
        except Exception as exc:
            logger.error(f"[Tiering] Pass 2 failed: {exc}")
            self.db.rollback()
            rows2 = 0

        total = rows1 + rows2
        logger.info(f"[Tiering] reclassify_all: {total} rows updated ({rows1} with BUS + {rows2} without)")
        return total
