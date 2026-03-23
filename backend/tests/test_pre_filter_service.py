"""
Tests for PreFilterService — scoring formula, threshold filtering, edge cases.
"""
import math
from datetime import datetime, timedelta, timezone

import pytest

from app.services.pre_filter_service import PreFilterService, DEFAULT_THRESHOLD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_info(
    release_date=None,
    current_reviews=0,
    current_rank=None,
    **extra,
) -> dict:
    return {
        "app_id": "123456",
        "name": "Test App",
        "release_date": release_date,
        "current_reviews": current_reviews,
        "current_rank": current_rank,
        **extra,
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Recency score
# ---------------------------------------------------------------------------

class TestRecencyScore:
    def setup_method(self):
        self.svc = PreFilterService()

    def test_released_today_scores_100(self):
        score = self.svc._recency_score(_now())
        assert score == 100.0

    def test_released_30d_ago_scores_100(self):
        score = self.svc._recency_score(_now() - timedelta(days=30))
        assert score == 100.0

    def test_released_59d_ago_scores_100(self):
        score = self.svc._recency_score(_now() - timedelta(days=59))
        assert score == 100.0

    def test_released_61d_ago_scores_60(self):
        score = self.svc._recency_score(_now() - timedelta(days=61))
        assert score == 60.0

    def test_released_181d_ago_scores_30(self):
        score = self.svc._recency_score(_now() - timedelta(days=181))
        assert score == 30.0

    def test_released_366d_ago_scores_10(self):
        score = self.svc._recency_score(_now() - timedelta(days=366))
        assert score == 10.0

    def test_none_release_date_scores_10(self):
        score = self.svc._recency_score(None)
        assert score == 10.0

    def test_iso_string_parsed(self):
        iso = (_now() - timedelta(days=30)).isoformat()
        score = self.svc._recency_score(iso)
        assert score == 100.0

    def test_naive_datetime_treated_as_utc(self):
        naive = datetime.utcnow() - timedelta(days=30)
        score = self.svc._recency_score(naive)
        assert score == 100.0

    def test_future_release_date_scores_100(self):
        score = self.svc._recency_score(_now() + timedelta(days=5))
        assert score == 100.0


# ---------------------------------------------------------------------------
# Reviews score
# ---------------------------------------------------------------------------

class TestReviewsScore:
    def setup_method(self):
        self.svc = PreFilterService()

    def test_zero_reviews_scores_0(self):
        assert self.svc._reviews_score(0) == 0.0

    def test_none_reviews_scores_0(self):
        assert self.svc._reviews_score(None) == 0.0

    def test_100_reviews_scores_100(self):
        assert self.svc._reviews_score(100) == pytest.approx(100.0, abs=0.01)

    def test_1_review_scores_positive(self):
        score = self.svc._reviews_score(1)
        assert 0 < score < 30

    def test_10_reviews(self):
        expected = math.log2(11) / math.log2(101) * 100
        assert self.svc._reviews_score(10) == pytest.approx(expected, abs=0.01)

    def test_more_than_100_capped_at_100(self):
        assert self.svc._reviews_score(10000) == pytest.approx(100.0, abs=0.01)

    def test_negative_reviews_treated_as_zero(self):
        assert self.svc._reviews_score(-5) == 0.0


# ---------------------------------------------------------------------------
# Ranking score
# ---------------------------------------------------------------------------

class TestRankingScore:
    def setup_method(self):
        self.svc = PreFilterService()

    def test_ranked_app_scores_60(self):
        assert self.svc._ranking_score(1) == 60.0
        assert self.svc._ranking_score(200) == 60.0
        assert self.svc._ranking_score(50000) == 60.0

    def test_no_rank_scores_0(self):
        assert self.svc._ranking_score(None) == 0.0

    def test_rank_0_scores_0(self):
        assert self.svc._ranking_score(0) == 0.0

    def test_string_rank_handled(self):
        assert self.svc._ranking_score("100") == 60.0

    def test_invalid_rank_scores_0(self):
        assert self.svc._ranking_score("abc") == 0.0


# ---------------------------------------------------------------------------
# Combined score_one
# ---------------------------------------------------------------------------

class TestScoreOne:
    def setup_method(self):
        self.svc = PreFilterService()

    def test_no_signal_app_scores_4(self):
        """Old unranked app with no reviews — minimum score."""
        info = _make_info(
            release_date=_now() - timedelta(days=500),  # >1yr
            current_reviews=0,
            current_rank=None,
        )
        score = self.svc.score_one(info)
        assert score == pytest.approx(10.0 * 0.40 + 0.0 * 0.35 + 0.0 * 0.25, abs=0.1)

    def test_fresh_ranked_app_scores_high(self):
        info = _make_info(
            release_date=_now() - timedelta(days=10),
            current_reviews=50,
            current_rank=100,
        )
        score = self.svc.score_one(info)
        assert score >= 60.0

    def test_ranked_any_age_passes_min_threshold(self):
        """Any ranked app should score >= 15 regardless of age/reviews."""
        info = _make_info(
            release_date=_now() - timedelta(days=800),
            current_reviews=0,
            current_rank=1,
        )
        score = self.svc.score_one(info)
        # recency=10*0.4=4, reviews=0*0.35=0, ranking=60*0.25=15 → total=19
        assert score >= 15.0

    def test_alternative_field_names_accepted(self):
        """score_one should accept aliased iTunes field names."""
        info = {
            "app_id": "111",
            "releaseDate": (_now() - timedelta(days=10)).isoformat(),
            "userRatingCount": 50,
            "rank": 100,
        }
        score = self.svc.score_one(info)
        assert score >= 60.0

    def test_score_is_float(self):
        info = _make_info(release_date=_now(), current_reviews=10, current_rank=50)
        assert isinstance(self.svc.score_one(info), float)


# ---------------------------------------------------------------------------
# filter_batch
# ---------------------------------------------------------------------------

class TestFilterBatch:
    def setup_method(self):
        self.svc = PreFilterService(threshold=15.0)

    def test_empty_batch_returns_empty(self):
        assert self.svc.filter_batch([]) == []

    def test_passing_apps_returned(self):
        info = _make_info(
            release_date=_now() - timedelta(days=10),
            current_rank=1,
            current_reviews=10,
        )
        result = self.svc.filter_batch([info])
        assert len(result) == 1

    def test_failing_apps_excluded(self):
        info = _make_info(
            release_date=_now() - timedelta(days=800),
            current_reviews=0,
            current_rank=None,
        )
        result = self.svc.filter_batch([info])
        assert len(result) == 0

    def test_score_attached_to_passing_dict(self):
        info = _make_info(release_date=_now(), current_rank=1, current_reviews=5)
        result = self.svc.filter_batch([info])
        assert "_pre_filter_score" in result[0]
        assert result[0]["_pre_filter_score"] >= 15.0

    def test_original_dict_not_mutated(self):
        info = _make_info(release_date=_now(), current_rank=1, current_reviews=5)
        original_keys = set(info.keys())
        self.svc.filter_batch([info])
        assert set(info.keys()) == original_keys

    def test_mixed_batch(self):
        passing = _make_info(
            release_date=_now(), current_rank=1, current_reviews=50
        )
        failing = _make_info(
            release_date=_now() - timedelta(days=800),
            current_reviews=0,
            current_rank=None,
        )
        result = self.svc.filter_batch([passing, failing, passing])
        assert len(result) == 2

    def test_custom_threshold(self):
        svc = PreFilterService(threshold=50.0)
        info = _make_info(release_date=_now(), current_rank=1, current_reviews=0)
        # recency=100*0.4=40, reviews=0, ranking=60*0.25=15 → 55 → passes
        result = svc.filter_batch([info])
        assert len(result) == 1

    def test_default_threshold_is_15(self):
        assert DEFAULT_THRESHOLD == 15
