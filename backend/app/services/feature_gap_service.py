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

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import App, FeatureGap, Review
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
        Run gap analysis only for apps that have received new negative reviews
        since their last FeatureGap detection (or have no FeatureGap rows yet),
        and that have at least *min_reviews* reviews total.
        Returns the number of apps processed.
        """
        # Latest negative review timestamp per app
        latest_neg_sq = (
            self.db.query(
                Review.app_id.label("app_id"),
                func.max(Review.created_at).label("latest_neg_at"),
            )
            .filter(Review.sentiment == "negative")
            .group_by(Review.app_id)
            .subquery()
        )

        # Latest feature-gap detection per app
        latest_gap_sq = (
            self.db.query(
                FeatureGap.app_id.label("app_id"),
                func.max(FeatureGap.detected_at).label("last_gap_at"),
            )
            .group_by(FeatureGap.app_id)
            .subquery()
        )

        # Apps where new negative reviews arrived after last gap analysis
        stale_ids = [
            row[0]
            for row in (
                self.db.query(latest_neg_sq.c.app_id)
                .outerjoin(
                    latest_gap_sq,
                    latest_gap_sq.c.app_id == latest_neg_sq.c.app_id,
                )
                .filter(
                    (latest_gap_sq.c.last_gap_at.is_(None))
                    | (latest_neg_sq.c.latest_neg_at > latest_gap_sq.c.last_gap_at)
                )
                .all()
            )
        ]

        # Enforce minimum total review count for quality
        eligible_ids = set(
            row[0]
            for row in (
                self.db.query(Review.app_id)
                .group_by(Review.app_id)
                .having(func.count(Review.id) >= min_reviews)
                .all()
            )
        )
        app_ids = [aid for aid in stale_ids if aid in eligible_ids]

        processed = 0
        for app_id in app_ids:
            self.compute_for_app(app_id)
            processed += 1

        logger.info(
            f"[FeatureGap] computed for {processed}/{len(stale_ids)} stale apps "
            f"(min_reviews={min_reviews})"
        )
        return processed
