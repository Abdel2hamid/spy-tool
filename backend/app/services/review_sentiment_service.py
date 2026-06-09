"""
Review Sentiment Service
========================
Rule-based sentiment classification for App Store reviews.

Each review gets a sentiment label (positive / neutral / negative) derived
from its star rating, with a keyword-boost applied for borderline cases:

  5★          → positive
  4★          → positive (unless strong negative language detected)
  3★          → neutral  (unless strong polarity is detected)
  2★          → negative
  1★          → negative

A continuous sentiment_score (0.0 – 1.0) is also written:
  1★ = 0.0, 2★ = 0.25, 3★ = 0.5, 4★ = 0.75, 5★ = 1.0
plus a ±0.1 keyword adjustment (clamped to [0, 1]).

Per-app averages are rolled up into AppAnalytics.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.models import App, Review, AppAnalytics
from app.utils.batch_utils import log_memory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword sets used to nudge borderline ratings
# ---------------------------------------------------------------------------

_POSITIVE_WORDS = frozenset([
    "love", "amazing", "excellent", "fantastic", "perfect", "wonderful",
    "great", "awesome", "best", "outstanding", "brilliant", "superb",
    "beautiful", "helpful", "easy", "fast", "smooth", "clean", "intuitive",
    "recommend", "impressed", "simple", "flawless", "responsive", "reliable",
])

_NEGATIVE_WORDS = frozenset([
    "terrible", "awful", "horrible", "useless", "broken", "crash", "bug",
    "worst", "hate", "scam", "fraud", "disappointing", "disappointed",
    "slow", "laggy", "freezing", "freeze", "broken", "error", "fail",
    "failed", "annoying", "frustrating", "garbage", "waste", "refund",
    "delete", "uninstall", "disgusting", "pathetic", "glitch", "glitchy",
])


def _classify(rating: Optional[int], content: Optional[str]) -> Tuple[str, float]:
    """Return (sentiment_label, sentiment_score) for a single review."""
    if rating is None:
        return "neutral", 0.5

    # Base score from star rating
    base_score = (rating - 1) / 4.0  # 1★→0.0 … 5★→1.0

    # Keyword adjustment
    keyword_delta = 0.0
    if content:
        words = set(re.findall(r"[a-z]+", content.lower()))
        pos_hits = len(words & _POSITIVE_WORDS)
        neg_hits = len(words & _NEGATIVE_WORDS)
        if pos_hits > neg_hits:
            keyword_delta = 0.05
        elif neg_hits > pos_hits:
            keyword_delta = -0.05

    score = max(0.0, min(1.0, base_score + keyword_delta))

    if score >= 0.65:
        label = "positive"
    elif score <= 0.35:
        label = "negative"
    else:
        label = "neutral"

    return label, round(score, 4)


class ReviewSentimentService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Per-review classification
    # ------------------------------------------------------------------

    def classify_pending_reviews(self, batch_size: int = 5000) -> int:
        """
        Classify all reviews where sentiment IS NULL.
        Uses lightweight tuple queries + batched raw SQL UPDATEs to avoid
        loading 5000 full ORM Review objects.
        Returns the number of reviews updated.
        """
        log_memory("sentiment_classify", "start")

        # Load only the columns needed for classification (no full ORM objects)
        rows = (
            self.db.query(Review.id, Review.rating, Review.content)
            .filter(Review.sentiment.is_(None))
            .limit(batch_size)
            .all()
        )

        if not rows:
            return 0

        # Compute sentiment in Python, then batch UPDATE via raw SQL
        updates = []
        for review_id, rating, content in rows:
            label, score = _classify(rating, content)
            updates.append((review_id, label))

        # Batch update in chunks of 500 to avoid oversized queries
        _UPDATE_CHUNK = 500
        updated = 0
        for i in range(0, len(updates), _UPDATE_CHUNK):
            chunk = updates[i : i + _UPDATE_CHUNK]
            # Build a CASE WHEN for batched update
            cases = " ".join(
                f"WHEN id = {rid} THEN '{label}'" for rid, label in chunk
            )
            ids = ", ".join(str(rid) for rid, _ in chunk)
            self.db.execute(text(
                f"UPDATE reviews SET sentiment = CASE {cases} END WHERE id IN ({ids})"
            ))
            updated += len(chunk)

        self.db.commit()
        self.db.expire_all()
        log_memory("sentiment_classify", "end")
        logger.info(f"[Sentiment] classified {updated} reviews")
        return updated

    # ------------------------------------------------------------------
    # Per-app analytics roll-up
    # ------------------------------------------------------------------

    def update_app_analytics(self, app_id: int) -> Optional[Dict]:
        """
        Recompute sentiment + growth metrics for *app_id* and upsert into
        app_analytics.  Returns the metrics dict or None if no reviews exist.
        """
        now = datetime.utcnow()
        cutoff_30d = now - timedelta(days=30)
        cutoff_90d = now - timedelta(days=90)

        all_reviews = (
            self.db.query(Review)
            .filter(Review.app_id == app_id, Review.sentiment.isnot(None))
            .all()
        )
        if not all_reviews:
            return None

        # --- Sentiment aggregation ---
        scores = [
            (1.0 if r.sentiment == "positive" else 0.5 if r.sentiment == "neutral" else 0.0)
            for r in all_reviews
        ]
        sentiment_score = round(sum(scores) / len(scores), 4) if scores else 0.5

        positives = sum(1 for r in all_reviews if r.sentiment == "positive")
        negatives = sum(1 for r in all_reviews if r.sentiment == "negative")
        if positives >= negatives * 2:
            sentiment_label = "positive"
        elif negatives >= positives * 2:
            sentiment_label = "negative"
        else:
            sentiment_label = "mixed"

        # --- Review growth ---
        def _count_since(cutoff):
            return sum(
                1 for r in all_reviews if r.date and r.date.replace(tzinfo=None) >= cutoff
            )

        new_30d = _count_since(cutoff_30d)
        new_90d = _count_since(cutoff_90d)
        before_30d = len(all_reviews) - new_30d
        before_90d = len(all_reviews) - new_90d

        review_growth_30d = round(new_30d / before_30d * 100, 2) if before_30d > 0 else 0.0
        review_growth_90d = round(new_90d / before_90d * 100, 2) if before_90d > 0 else 0.0

        # --- Rating change ---
        def _avg_rating(reviews_subset):
            ratings = [r.rating for r in reviews_subset if r.rating is not None]
            return sum(ratings) / len(ratings) if ratings else None

        recent_30d = [r for r in all_reviews if r.date and r.date.replace(tzinfo=None) >= cutoff_30d]
        older_30d  = [r for r in all_reviews if r.date and r.date.replace(tzinfo=None) < cutoff_30d]
        recent_90d = [r for r in all_reviews if r.date and r.date.replace(tzinfo=None) >= cutoff_90d]
        older_90d  = [r for r in all_reviews if r.date and r.date.replace(tzinfo=None) < cutoff_90d]

        avg_recent_30 = _avg_rating(recent_30d)
        avg_older_30  = _avg_rating(older_30d)
        avg_recent_90 = _avg_rating(recent_90d)
        avg_older_90  = _avg_rating(older_90d)

        rating_change_30d = round(avg_recent_30 - avg_older_30, 4) if (avg_recent_30 and avg_older_30) else 0.0
        rating_change_90d = round(avg_recent_90 - avg_older_90, 4) if (avg_recent_90 and avg_older_90) else 0.0

        # --- Upsert AppAnalytics ---
        analytics = (
            self.db.query(AppAnalytics)
            .filter(AppAnalytics.app_id == app_id)
            .first()
        )
        if not analytics:
            analytics = AppAnalytics(app_id=app_id)
            self.db.add(analytics)

        analytics.sentiment_score   = sentiment_score
        analytics.sentiment_label   = sentiment_label
        analytics.review_growth_30d = review_growth_30d
        analytics.review_growth_90d = review_growth_90d
        analytics.rating_change_30d = rating_change_30d
        analytics.rating_change_90d = rating_change_90d
        analytics.computed_at       = now

        self.db.commit()

        return {
            "app_id": app_id,
            "sentiment_score": sentiment_score,
            "sentiment_label": sentiment_label,
            "review_growth_30d": review_growth_30d,
            "review_growth_90d": review_growth_90d,
            "rating_change_30d": rating_change_30d,
            "rating_change_90d": rating_change_90d,
        }

    def update_all_app_analytics(self) -> int:
        """
        Run update_app_analytics only for apps that have received new reviews
        since their last AppAnalytics computation (or have no analytics row yet).
        Returns the number of apps updated.
        """
        # Latest review timestamp per app (classified reviews only)
        latest_review_sq = (
            self.db.query(
                Review.app_id.label("app_id"),
                func.max(Review.created_at).label("latest_review_at"),
            )
            .filter(Review.sentiment.isnot(None))
            .group_by(Review.app_id)
            .subquery()
        )

        # Only include apps where latest review is newer than last analytics computation
        # or where analytics row doesn't exist yet.
        from sqlalchemy import outerjoin
        stale_app_ids = [
            row[0]
            for row in (
                self.db.query(latest_review_sq.c.app_id)
                .outerjoin(
                    AppAnalytics,
                    AppAnalytics.app_id == latest_review_sq.c.app_id,
                )
                .filter(
                    (AppAnalytics.computed_at.is_(None))
                    | (latest_review_sq.c.latest_review_at > AppAnalytics.computed_at)
                )
                .all()
            )
        ]

        updated = 0
        for app_id in stale_app_ids:
            try:
                result = self.update_app_analytics(app_id)
                if result:
                    updated += 1
            except Exception as exc:
                logger.warning(f"[Sentiment] analytics update failed for app {app_id}: {exc}")
                self.db.rollback()

        logger.info(f"[Sentiment] updated analytics for {updated}/{len(stale_app_ids)} stale apps")
        return updated
