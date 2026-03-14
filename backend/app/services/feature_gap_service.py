"""
Feature Gap Service
===================
Coordinator around the existing FeatureGapAnalyzer.  Runs gap analysis for
all tracked apps that have at least a minimum number of reviews, and writes
results to the feature_gaps table.

Usage:
    svc = FeatureGapService(db)
    svc.compute_for_app(app_id=42)
    svc.compute_for_all_apps(min_reviews=5)
"""

import logging
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.models import App, Review
from app.scoring.feature_gaps import FeatureGapAnalyzer

logger = logging.getLogger(__name__)

_MIN_REVIEWS_DEFAULT = 5


class FeatureGapService:
    def __init__(self, db: Session):
        self.db = db
        self._analyzer = FeatureGapAnalyzer(db)

    def compute_for_app(self, app_id: int) -> List[Dict]:
        """
        Run gap analysis for one app.  Returns the list of gaps found
        (each: {"feature": str, "mentions": int}).
        """
        try:
            gaps = self._analyzer.compute_for_app(app_id)
            if gaps:
                logger.debug(f"[FeatureGap] app {app_id}: {len(gaps)} gaps found")
            return gaps
        except Exception as exc:
            logger.warning(f"[FeatureGap] app {app_id} failed: {exc}")
            self.db.rollback()
            return []

    def compute_for_all_apps(self, min_reviews: int = _MIN_REVIEWS_DEFAULT) -> int:
        """
        Run gap analysis for all apps that have at least *min_reviews* reviews.
        Returns the number of apps processed.
        """
        # Find app IDs that meet the minimum review threshold
        app_ids = [
            row[0]
            for row in (
                self.db.query(Review.app_id)
                .group_by(Review.app_id)
                .having(
                    # sqlalchemy func.count
                    __import__("sqlalchemy").func.count(Review.id) >= min_reviews
                )
                .all()
            )
        ]

        processed = 0
        for app_id in app_ids:
            self.compute_for_app(app_id)
            processed += 1

        logger.info(f"[FeatureGap] computed for {processed} apps (min_reviews={min_reviews})")
        return processed
