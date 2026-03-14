"""
test_reviews_intelligence.py
============================
Tests for:
1. Sentiment classification logic (_classify function)
2. ReviewSentimentService — classify_pending_reviews + update_app_analytics
3. FeatureGapService — delegates to FeatureGapAnalyzer correctly
4. Review model — sentiment column present
"""

import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# 1. Sentiment classification logic
# ---------------------------------------------------------------------------

class TestSentimentClassification:
    """Unit-test _classify() without touching the DB."""

    def _classify(self, rating, content=""):
        from app.services.review_sentiment_service import _classify
        return _classify(rating, content)

    def test_5_star_is_positive(self):
        label, score = self._classify(5)
        assert label == "positive"
        assert score >= 0.75

    def test_4_star_is_positive(self):
        label, score = self._classify(4)
        assert label == "positive"

    def test_3_star_is_neutral(self):
        label, score = self._classify(3)
        assert label == "neutral"

    def test_2_star_is_negative(self):
        label, score = self._classify(2)
        assert label == "negative"

    def test_1_star_is_negative(self):
        label, score = self._classify(1)
        assert label == "negative"
        assert score <= 0.25

    def test_score_clamped_to_0_1(self):
        for rating in range(1, 6):
            _, score = self._classify(rating, "terrible awful horrible crash freeze")
            assert 0.0 <= score <= 1.0, f"score out of range for {rating}★"

    def test_positive_keywords_boost_score(self):
        _, score_plain = self._classify(3)
        _, score_boosted = self._classify(3, "love amazing excellent perfect")
        assert score_boosted >= score_plain

    def test_negative_keywords_lower_score(self):
        _, score_plain = self._classify(3)
        _, score_lowered = self._classify(3, "terrible awful crash freeze broken")
        assert score_lowered <= score_plain

    def test_none_rating_returns_neutral(self):
        label, score = self._classify(None)
        assert label == "neutral"
        assert score == 0.5

    def test_score_is_float(self):
        _, score = self._classify(4, "great app!")
        assert isinstance(score, float)


# ---------------------------------------------------------------------------
# 2. ReviewSentimentService
# ---------------------------------------------------------------------------

class TestReviewSentimentService:
    """Mock DB interactions to test service logic."""

    def _make_review(self, rating, content="test review content", sentiment=None, days_ago=None):
        rv = MagicMock()
        rv.rating = rating
        rv.content = content
        rv.sentiment = sentiment
        if days_ago is not None:
            rv.date = datetime.utcnow() - timedelta(days=days_ago)
        else:
            rv.date = None
        return rv

    def _make_service(self, pending_reviews=None, classified_reviews=None):
        db = MagicMock()
        svc_class = __import__(
            "app.services.review_sentiment_service",
            fromlist=["ReviewSentimentService"]
        ).ReviewSentimentService

        svc = svc_class(db)

        if pending_reviews is not None:
            db.query.return_value.filter.return_value.limit.return_value.all.return_value = pending_reviews
        if classified_reviews is not None:
            db.query.return_value.filter.return_value.all.return_value = classified_reviews
        return svc, db

    def test_classify_pending_sets_sentiment(self):
        reviews = [
            self._make_review(5, "Love this app!"),
            self._make_review(1, "Terrible crash"),
        ]
        svc, db = self._make_service(pending_reviews=reviews)
        svc.classify_pending_reviews()
        # Sentiment should have been set on each review
        assert reviews[0].sentiment == "positive"
        assert reviews[1].sentiment == "negative"

    def test_classify_pending_returns_count(self):
        reviews = [self._make_review(4)] * 7
        svc, db = self._make_service(pending_reviews=reviews)
        count = svc.classify_pending_reviews()
        assert count == 7

    def test_classify_empty_reviews_returns_zero(self):
        svc, db = self._make_service(pending_reviews=[])
        count = svc.classify_pending_reviews()
        assert count == 0
        db.commit.assert_not_called()

    def test_update_app_analytics_no_reviews_returns_none(self):
        svc, db = self._make_service(classified_reviews=[])
        result = svc.update_app_analytics(app_id=1)
        assert result is None

    def test_update_app_analytics_populates_sentiment(self):
        reviews = [
            self._make_review(5, sentiment="positive"),
            self._make_review(5, sentiment="positive"),
            self._make_review(1, sentiment="negative"),
        ]
        svc, db = self._make_service(classified_reviews=reviews)
        # Simulate AppAnalytics query returning None (new record)
        db.query.return_value.filter.return_value.all.return_value = reviews
        db.query.return_value.filter.return_value.first.return_value = None

        result = svc.update_app_analytics(app_id=1)
        assert result is not None
        assert "sentiment_score" in result
        assert "sentiment_label" in result

    def test_update_app_analytics_returns_dict_with_all_keys(self):
        reviews = [self._make_review(4, sentiment="positive", days_ago=10)] * 5
        svc, db = self._make_service(classified_reviews=reviews)
        db.query.return_value.filter.return_value.first.return_value = None

        result = svc.update_app_analytics(app_id=1)
        if result:
            expected_keys = {
                "app_id", "sentiment_score", "sentiment_label",
                "review_growth_30d", "review_growth_90d",
                "rating_change_30d", "rating_change_90d",
            }
            assert expected_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# 3. FeatureGapService
# ---------------------------------------------------------------------------

class TestFeatureGapService:
    """Verify FeatureGapService delegates to FeatureGapAnalyzer."""

    def _make_service(self, analyzer_return=None):
        db = MagicMock()
        from app.services.feature_gap_service import FeatureGapService
        svc = FeatureGapService(db)
        # Patch the internal analyzer
        svc._analyzer = MagicMock()
        svc._analyzer.compute_for_app.return_value = analyzer_return or []
        return svc, db

    def test_compute_for_app_delegates_to_analyzer(self):
        expected_gaps = [{"feature": "dark mode", "mentions": 12}]
        svc, db = self._make_service(analyzer_return=expected_gaps)
        result = svc.compute_for_app(app_id=42)
        svc._analyzer.compute_for_app.assert_called_once_with(42)
        assert result == expected_gaps

    def test_compute_for_app_handles_exception(self):
        svc, db = self._make_service()
        svc._analyzer.compute_for_app.side_effect = RuntimeError("DB error")
        result = svc.compute_for_app(app_id=99)
        assert result == []

    def test_compute_for_all_apps_returns_count(self):
        from app.services.feature_gap_service import FeatureGapService
        db = MagicMock()
        svc = FeatureGapService(db)
        svc._analyzer = MagicMock()
        svc._analyzer.compute_for_app.return_value = []
        # Simulate 3 eligible apps
        db.query.return_value.group_by.return_value.having.return_value.all.return_value = [
            (1,), (2,), (3,)
        ]
        count = svc.compute_for_all_apps(min_reviews=5)
        assert count == 3
        assert svc._analyzer.compute_for_app.call_count == 3


# ---------------------------------------------------------------------------
# 4. Review model — sentiment column present
# ---------------------------------------------------------------------------

class TestReviewModelSentimentColumn:
    """Verify the Review ORM model has the sentiment column."""

    def test_review_model_has_sentiment_column(self):
        from app.models.models import Review
        assert hasattr(Review, "sentiment")

    def test_sentiment_column_accepts_standard_labels(self):
        """The column is VARCHAR(20) — any of the 3 labels should fit."""
        from app.models.models import Review
        rv = Review(sentiment="positive")
        assert rv.sentiment == "positive"
        rv.sentiment = "negative"
        assert rv.sentiment == "negative"
        rv.sentiment = "neutral"
        assert rv.sentiment == "neutral"

    def test_sentiment_column_default_is_none(self):
        from app.models.models import Review
        rv = Review()
        assert rv.sentiment is None
