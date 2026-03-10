"""
Global Keyword Sink
===================
Reusable helper that upserts keyword strings into the global ``keywords`` table
(dictionary only — no metrics) and optionally writes app-keyword relations into
the normalised ``app_keywords`` table.

3-table architecture
--------------------
keywords        — dictionary: id, term, created_at (+ legacy provenance cols)
keyword_metrics — intelligence: search_volume, difficulty, trend_score, …
app_keywords    — relations:  app_id, keyword_id, rank, traffic, opportunity_score

Usage::
    from app.services.global_keyword_sink import GlobalKeywordSink

    sink = GlobalKeywordSink(db)

    # 1. Insert terms into keyword dictionary
    inserted, skipped = sink.push(
        keywords=["focus timer", "deep work app", "pomodoro"],
        source="discovered",
        discovered_from="focus timer",
    )

    # 2. Wire app→keyword relations with enrichment signals
    sink.push_app_keywords(
        app_id=42,
        kw_data={
            "focus timer":  {"rank": 5,  "traffic": 12.3, "opportunity_score": 74.1},
            "deep work app": {"rank": None, "traffic": 0.5, "opportunity_score": 61.0},
        },
        source="discovered",
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import AppKeyword, Keyword

logger = logging.getLogger(__name__)

# Batch size for bulk inserts (keywords dictionary)
_BATCH_SIZE = 500

# Hard limits
_MAX_GLOBAL_KEYWORDS = 500_000
_MAX_PER_APP = 100


class GlobalKeywordSink:
    """
    Two-phase writer for the 3-table keyword architecture.

    push()             → inserts into ``keywords`` (dictionary only, no metrics)
    push_app_keywords() → inserts into ``app_keywords`` (app→keyword relations)

    Both methods use ON CONFLICT DO NOTHING so they are safe to call repeatedly.
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Phase 1: keyword dictionary ──────────────────────────────────────────

    def push(
        self,
        keywords: List[str],
        source: str,
        discovered_from: Optional[str] = None,
    ) -> Tuple[int, int]:
        """
        Upsert keyword terms into the ``keywords`` dictionary table.

        Only inserts: term, keyword_source, discovered_from, first_seen_at.
        Metric columns (search_volume, difficulty, etc.) are left at defaults
        so the intelligence pipeline can fill them in later.

        Returns
        -------
        (inserted, skipped)
        """
        if not keywords:
            return 0, 0

        # ── Global limit guard ────────────────────────────────────────────────
        global_count = self.db.query(func.count(Keyword.id)).scalar() or 0
        if global_count >= _MAX_GLOBAL_KEYWORDS:
            logger.warning(
                f"[KeywordLimit] global keyword limit reached "
                f"({global_count:,} / {_MAX_GLOBAL_KEYWORDS:,}) "
                f"— skipping insertion (source={source!r})"
            )
            return 0, 0

        # Normalise: lowercase, strip, deduplicate, min length 3
        normalised = list({kw.strip().lower() for kw in keywords if len(kw.strip()) >= 3})

        # Cap to remaining slots
        remaining = _MAX_GLOBAL_KEYWORDS - global_count
        if len(normalised) > remaining:
            normalised = normalised[:remaining]

        inserted = 0
        skipped = 0
        now = datetime.now(timezone.utc)

        for i in range(0, len(normalised), _BATCH_SIZE):
            batch = normalised[i : i + _BATCH_SIZE]
            try:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = (
                    pg_insert(Keyword.__table__)
                    .values(
                        [
                            {
                                "term": kw,
                                "keyword_source": source,
                                "discovered_from": discovered_from,
                                "first_seen_at": now,
                            }
                            for kw in batch
                        ]
                    )
                    .on_conflict_do_nothing(index_elements=["term"])
                )
                result = self.db.execute(stmt)
                self.db.commit()
                batch_inserted = result.rowcount or 0
                inserted += batch_inserted
                skipped += len(batch) - batch_inserted
            except Exception as exc:
                self.db.rollback()
                logger.error(
                    f"[GlobalKeywordSink] push batch failed "
                    f"(source={source!r}, batch_start={i}): {exc}",
                    exc_info=True,
                )

        logger.info(
            f"[GlobalKeywordSink] source={source!r}: "
            f"{inserted} inserted, {skipped} skipped (already existed)"
        )
        return inserted, skipped

    # ── Phase 2: app→keyword relations ───────────────────────────────────────

    def push_app_keywords(
        self,
        app_id: int,
        kw_data: Dict[str, Dict],
        source: str,
    ) -> int:
        """
        Upsert app→keyword relations into the ``app_keywords`` table.

        Parameters
        ----------
        app_id:   DB primary key of the app.
        kw_data:  ``{term: {"rank": int|None, "traffic": float, "opportunity_score": float}}``
                  Terms that are not yet in the ``keywords`` table are silently skipped
                  (call ``push()`` first to ensure they exist).
        source:   provenance label, e.g. ``"discovered"``, ``"alphabet"``, ``"competitor"``.

        Enforces per-app limit of ``_MAX_PER_APP`` rows in ``app_keywords``.

        Returns
        -------
        Count of newly inserted rows.
        """
        if not kw_data or not app_id:
            return 0

        # ── Per-app limit guard ───────────────────────────────────────────────
        current = (
            self.db.query(func.count(AppKeyword.id))
            .filter(AppKeyword.app_id == app_id)
            .scalar() or 0
        )
        if current >= _MAX_PER_APP:
            logger.info(
                f"[KeywordLimit] app {app_id} already has {current} app_keywords "
                f"(limit={_MAX_PER_APP}) — skipping app_keywords insertion"
            )
            return 0

        slots = _MAX_PER_APP - current
        terms = list(kw_data.keys())[:slots]

        # Look up keyword IDs for these terms (only those already in `keywords`)
        id_map: Dict[str, int] = {
            row.term: row.id
            for row in (
                self.db.query(Keyword.id, Keyword.term)
                .filter(Keyword.term.in_(terms))
                .all()
            )
        }

        if not id_map:
            return 0

        now = datetime.now(timezone.utc)
        inserted = 0

        for term, keyword_id in id_map.items():
            d = kw_data.get(term, {})
            try:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = (
                    pg_insert(AppKeyword.__table__)
                    .values(
                        app_id=app_id,
                        keyword_id=keyword_id,
                        rank=d.get("rank"),
                        traffic=float(d.get("traffic", 0.0)),
                        opportunity_score=float(d.get("opportunity_score", 0.0)),
                        source=source,
                        created_at=now,
                    )
                    .on_conflict_do_nothing(index_elements=["app_id", "keyword_id"])
                )
                result = self.db.execute(stmt)
                self.db.commit()
                inserted += result.rowcount or 0
            except Exception as exc:
                self.db.rollback()
                logger.error(
                    f"[GlobalKeywordSink] push_app_keywords failed for "
                    f"app={app_id} term={term!r}: {exc}",
                    exc_info=True,
                )

        logger.info(
            f"[GlobalKeywordSink] app {app_id}: {inserted} app_keywords inserted "
            f"(source={source!r})"
        )
        return inserted

    # ── Utility ───────────────────────────────────────────────────────────────

    def get_keyword_ids(self, terms: List[str]) -> Dict[str, int]:
        """Return {term: keyword_id} for all terms that exist in ``keywords``."""
        if not terms:
            return {}
        return {
            row.term: row.id
            for row in (
                self.db.query(Keyword.id, Keyword.term)
                .filter(Keyword.term.in_(terms))
                .all()
            )
        }
