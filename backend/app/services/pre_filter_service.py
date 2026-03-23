"""
Pre-filter service for scalable app ingestion.

Scores candidate apps from discovery sources (charts, keywords, developer
expansion) and rejects low-value entries before they hit the DB.  This keeps
the pipeline lean: only apps that meet a minimum quality bar get a light-insert.

Scoring formula (0–100):
  recency  × 0.40   →  100 if <60d, 60 if <180d, 30 if <365d, 10 otherwise
  reviews  × 0.35   →  log2(n+1) / log2(101) × 100, capped at 100
  ranking  × 0.25   →  60 if rank is not None, else 0

Default threshold: 15 (Phase 1).
Any ranked app passes regardless of age; an app with 0 reviews and no rank
and released >1yr ago scores ≈ 4 and is rejected.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

# Phase thresholds — bump these as the pipeline matures
THRESHOLD_PHASE1 = 15
THRESHOLD_PHASE2 = 20
THRESHOLD_PHASE3 = 30

# Default active threshold (Phase 1)
DEFAULT_THRESHOLD = THRESHOLD_PHASE1


class PreFilterService:
    """
    Lightweight pre-filter applied at discovery time.

    Usage::

        svc = PreFilterService()
        passing = svc.filter_batch(raw_app_infos)
    """

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_one(self, info: dict) -> float:
        """
        Score a single candidate app info dict (from iTunes Search / RSS).

        Expected fields (all optional — missing fields score 0 for that component):
          release_date  : datetime | ISO string | None
          current_reviews / review_count : int | None
          current_rank / rank           : int | None

        Returns a float in [0, 100].
        """
        recency = self._recency_score(
            info.get("release_date") or info.get("releaseDate")
        )
        reviews = self._reviews_score(
            info.get("current_reviews") or info.get("review_count") or info.get("userRatingCount")
        )
        ranking = self._ranking_score(
            info.get("current_rank") or info.get("rank")
        )
        score = recency * 0.40 + reviews * 0.35 + ranking * 0.25
        return round(score, 2)

    def filter_batch(self, app_infos: List[dict]) -> List[dict]:
        """
        Apply threshold filter to a batch of candidate app info dicts.

        Returns the subset whose score >= self.threshold.
        Attaches `_pre_filter_score` to each passing dict for downstream use.
        """
        if not app_infos:
            return []

        passing = []
        rejected = 0
        for info in app_infos:
            score = self.score_one(info)
            if score >= self.threshold:
                info = dict(info)  # shallow copy — don't mutate caller's dict
                info["_pre_filter_score"] = score
                passing.append(info)
            else:
                rejected += 1

        if rejected:
            logger.debug(
                f"[PreFilter] {len(passing)}/{len(app_infos)} passed "
                f"(threshold={self.threshold}, rejected={rejected})"
            )
        return passing

    # ------------------------------------------------------------------
    # Component scorers
    # ------------------------------------------------------------------

    @staticmethod
    def _recency_score(release_date) -> float:
        """
        100 if released <60d ago
         60 if released <180d ago
         30 if released <365d ago
         10 otherwise / unknown
        """
        if not release_date:
            return 10.0
        if isinstance(release_date, str):
            try:
                release_date = datetime.fromisoformat(release_date.rstrip("Z"))
            except Exception:
                return 10.0

        now = datetime.now(timezone.utc)
        # Normalise to UTC-aware
        if release_date.tzinfo is None:
            release_date = release_date.replace(tzinfo=timezone.utc)

        age_days = (now - release_date).days
        if age_days < 0:
            return 100.0
        if age_days < 60:
            return 100.0
        if age_days < 180:
            return 60.0
        if age_days < 365:
            return 30.0
        return 10.0

    @staticmethod
    def _reviews_score(review_count) -> float:
        """
        log2(n+1) / log2(101) × 100, capped at 100.
        0 reviews → 0.0
        100 reviews → 100.0
        """
        if not review_count:
            return 0.0
        n = max(0, int(review_count))
        return min(100.0, math.log2(n + 1) / math.log2(101) * 100.0)

    @staticmethod
    def _ranking_score(rank) -> float:
        """60 if app has any chart rank, 0 otherwise."""
        if rank is not None:
            try:
                if int(rank) > 0:
                    return 60.0
            except (TypeError, ValueError):
                pass
        return 0.0
