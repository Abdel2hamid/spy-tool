"""
test_download_estimator.py
===========================
Tests for the 4-layer ensemble download estimator and related config.

Coverage:
  1. rank_curves — interpolation, fuzzy matching, reliability
  2. category_arpu_profiles — profile lookup, fuzzy matching
  3. calibration_profiles — profile lookup, fuzzy matching
  4. ConfidenceEngine — factor computation, uncertainty, labels
  5. DownloadEstimator — layers, ensemble, edge cases, anti-manipulation
  6. Revenue integration — ARPU profiles used in revenue_estimator
"""

import sys
import os
import math
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_app(**kw):
    app = MagicMock()
    app.id = kw.get("id", 1)
    app.app_id = kw.get("app_id", "123456789")
    app.name = kw.get("name", "Test App")
    app.current_reviews = kw.get("current_reviews", 500)
    app.current_rank = kw.get("current_rank", 42)
    app.primary_category = kw.get("primary_category", "Games")
    app.price = kw.get("price", 0.0)
    app.is_free = kw.get("is_free", True)
    app.in_app_purchases = kw.get("in_app_purchases", ["Premium"])
    app.release_date = kw.get("release_date", datetime.now(timezone.utc) - timedelta(days=365))
    app.estimated_installs_min = kw.get("estimated_installs_min", None)
    app.estimated_installs_max = kw.get("estimated_installs_max", None)
    app.install_confidence = kw.get("install_confidence", None)
    app.estimated_revenue_monthly_min = kw.get("estimated_revenue_monthly_min", None)
    app.estimated_revenue_monthly_max = kw.get("estimated_revenue_monthly_max", None)
    app.last_scraped_at = kw.get("last_scraped_at", datetime.now(timezone.utc) - timedelta(days=1))
    app.updated_at = kw.get("updated_at", datetime.now(timezone.utc) - timedelta(days=1))
    return app


def _make_signals(**kw):
    """Build a signals dict with sensible defaults."""
    return {
        "app_id": kw.get("app_id", 1),
        "category": kw.get("category", "games"),
        "review_count": kw.get("review_count", 200),
        "rank": kw.get("rank", 50),
        "velocity": kw.get("velocity", 2.0),
        "ranking_history_days": kw.get("ranking_history_days", 14),
        "keyword_count": kw.get("keyword_count", 30),
        "avg_traffic_score": kw.get("avg_traffic_score", 40.0),
        "momentum_3d": kw.get("momentum_3d", 0.2),
        "momentum_7d": kw.get("momentum_7d", 0.1),
        "has_rank": kw.get("has_rank", True),
        "has_velocity": kw.get("has_velocity", True),
        "has_keywords": kw.get("has_keywords", True),
        "has_momentum": kw.get("has_momentum", True),
        "data_age_days": kw.get("data_age_days", 1),
        "ir_ratio": kw.get("ir_ratio", 1500.0),
    }


def _make_db_empty():
    """Return a mock DB that returns zeros for all queries."""
    db = MagicMock()
    # query().filter().scalar() → 0
    db.query.return_value.filter.return_value.scalar.return_value = 0
    # query().filter().count() → 0
    db.query.return_value.filter.return_value.count.return_value = 0
    # query().filter().first() → None
    db.query.return_value.filter.return_value.first.return_value = None
    # aggregate row for keyword intelligence
    kw_row = MagicMock()
    kw_row.kw_count = 0
    kw_row.avg_traffic = 0.0
    db.query.return_value.filter.return_value.first.return_value = kw_row
    return db


# ===========================================================================
# 1. Rank Curves
# ===========================================================================

class TestRankCurves:
    def test_games_rank1_returns_high_numbers(self):
        from app.config.rank_curves import interpolate_rank_downloads
        lo, hi = interpolate_rank_downloads(1, "games")
        assert lo >= 100_000, f"Expected >100k daily for games #1, got {lo}"
        assert hi >= 200_000, f"Expected >200k daily (hi) for games #1, got {hi}"

    def test_games_rank100_less_than_rank10(self):
        from app.config.rank_curves import interpolate_rank_downloads
        lo10, hi10 = interpolate_rank_downloads(10, "games")
        lo100, hi100 = interpolate_rank_downloads(100, "games")
        assert (lo10 + hi10) > (lo100 + hi100), "Higher rank should yield more downloads"

    def test_finance_less_than_games_for_same_rank(self):
        from app.config.rank_curves import interpolate_rank_downloads
        games_lo, games_hi = interpolate_rank_downloads(10, "games")
        fin_lo, fin_hi = interpolate_rank_downloads(10, "finance")
        assert (games_lo + games_hi) > (fin_lo + fin_hi), (
            "Games should have more downloads than Finance at same rank"
        )

    def test_fallback_category_returns_default(self):
        from app.config.rank_curves import interpolate_rank_downloads
        lo, hi = interpolate_rank_downloads(50, "unknown_category_xyz")
        default_lo, default_hi = interpolate_rank_downloads(50, "default")
        assert (lo, hi) == (default_lo, default_hi), "Unknown category should use default"

    def test_no_rank_returns_zeros(self):
        from app.config.rank_curves import interpolate_rank_downloads
        lo, hi = interpolate_rank_downloads(None, "games")
        assert lo == 0 and hi == 0

    def test_negative_rank_returns_zeros(self):
        from app.config.rank_curves import interpolate_rank_downloads
        lo, hi = interpolate_rank_downloads(-1, "games")
        assert lo == 0 and hi == 0

    def test_fuzzy_category_match(self):
        from app.config.rank_curves import interpolate_rank_downloads
        # "Health & Fitness" should match "health & fitness" or "health"
        lo1, hi1 = interpolate_rank_downloads(10, "Health & Fitness")
        lo2, hi2 = interpolate_rank_downloads(10, "health & fitness")
        assert lo1 == lo2 and hi1 == hi2

    def test_reliability_scores_in_range(self):
        from app.config.rank_curves import get_category_reliability
        for cat in ["games", "finance", "productivity", "default", "unknown_xyz"]:
            r = get_category_reliability(cat)
            assert 0.0 <= r <= 1.0, f"Reliability out of range for {cat}: {r}"

    def test_games_higher_reliability_than_finance(self):
        from app.config.rank_curves import get_category_reliability
        assert get_category_reliability("games") > get_category_reliability("finance")

    def test_rank_1000_less_than_rank_100(self):
        from app.config.rank_curves import interpolate_rank_downloads
        lo100, hi100 = interpolate_rank_downloads(100, "productivity")
        lo1000, hi1000 = interpolate_rank_downloads(1000, "productivity")
        assert (lo100 + hi100) > (lo1000 + hi1000)

    def test_interpolation_is_monotonic(self):
        """A worse rank must never produce a higher central estimate."""
        from app.config.rank_curves import interpolate_rank_downloads

        ranks = [1, 2, 3, 4, 5, 6, 10, 15, 20, 21, 30, 50, 51, 100, 200, 500, 1000]
        centers = []
        for r in ranks:
            lo, hi = interpolate_rank_downloads(r, "games")
            centers.append((lo + hi) / 2)

        for i in range(1, len(centers)):
            assert centers[i - 1] >= centers[i], (
                f"Non-monotonic at ranks {ranks[i - 1]}->{ranks[i]}: "
                f"{centers[i - 1]} < {centers[i]}"
            )

    def test_band_boundaries_are_continuous(self):
        """The central estimate at the top of one band should match the next band's bottom."""
        from app.config.rank_curves import interpolate_rank_downloads

        # games: band (1,5) ends at 200k; band (6,20) starts at 200k
        lo5, hi5 = interpolate_rank_downloads(5, "games")
        lo6, hi6 = interpolate_rank_downloads(6, "games")
        mid5 = (lo5 + hi5) / 2
        mid6 = (lo6 + hi6) / 2
        assert abs(mid5 - mid6) / max(mid5, mid6) < 0.05, (
            f"Midpoint discontinuity at rank 5->6: mid5={mid5}, mid6={mid6}"
        )

        lo20, hi20 = interpolate_rank_downloads(20, "games")
        lo21, hi21 = interpolate_rank_downloads(21, "games")
        mid20 = (lo20 + hi20) / 2
        mid21 = (lo21 + hi21) / 2
        assert abs(mid20 - mid21) / max(mid20, mid21) < 0.05, (
            f"Midpoint discontinuity at rank 20->21: mid20={mid20}, mid21={mid21}"
        )

    def test_rank_20_less_than_rank_6(self):
        """Regression test for the original non-monotonic band-edge bug."""
        from app.config.rank_curves import interpolate_rank_downloads

        lo6, hi6 = interpolate_rank_downloads(6, "games")
        lo20, hi20 = interpolate_rank_downloads(20, "games")
        assert (lo6 + hi6) > (lo20 + hi20), (
            f"Rank 6 should estimate more downloads than rank 20: "
            f"rank6={(lo6+hi6)/2}, rank20={(lo20+hi20)/2}"
        )


# ===========================================================================
# 2. Category ARPU Profiles
# ===========================================================================

class TestCategoryArpuProfiles:
    def test_finance_higher_arpu_than_games(self):
        from app.config.category_arpu_profiles import get_arpu_profile
        finance = get_arpu_profile("finance")
        games = get_arpu_profile("games")
        assert finance["arpu_medium"] > games["arpu_medium"]

    def test_profile_has_required_keys(self):
        from app.config.category_arpu_profiles import get_arpu_profile
        profile = get_arpu_profile("productivity")
        for key in ["arpu_low", "arpu_medium", "arpu_high", "primary_model",
                    "monetization_hint", "iap_conversion_rate", "active_fraction"]:
            assert key in profile, f"Missing key: {key}"

    def test_fallback_for_unknown_category(self):
        from app.config.category_arpu_profiles import get_arpu_profile, CATEGORY_ARPU_PROFILES
        profile = get_arpu_profile("some_unknown_category_xyz")
        assert profile == CATEGORY_ARPU_PROFILES["default"]

    def test_none_category_returns_default(self):
        from app.config.category_arpu_profiles import get_arpu_profile, CATEGORY_ARPU_PROFILES
        assert get_arpu_profile(None) == CATEGORY_ARPU_PROFILES["default"]

    def test_arpu_low_less_than_medium_less_than_high(self):
        from app.config.category_arpu_profiles import CATEGORY_ARPU_PROFILES
        for cat, profile in CATEGORY_ARPU_PROFILES.items():
            assert profile["arpu_low"] <= profile["arpu_medium"] <= profile["arpu_high"], (
                f"ARPU ordering violated for {cat}"
            )

    def test_fuzzy_match_health_and_fitness(self):
        from app.config.category_arpu_profiles import get_arpu_profile
        p1 = get_arpu_profile("Health & Fitness")
        p2 = get_arpu_profile("health & fitness")
        assert p1["arpu_medium"] == p2["arpu_medium"]

    def test_conversion_rate_in_range(self):
        from app.config.category_arpu_profiles import CATEGORY_ARPU_PROFILES
        for cat, profile in CATEGORY_ARPU_PROFILES.items():
            assert 0 < profile["iap_conversion_rate"] <= 0.20, (
                f"Conversion rate out of range for {cat}"
            )

    def test_active_fraction_in_range(self):
        from app.config.category_arpu_profiles import CATEGORY_ARPU_PROFILES
        for cat, profile in CATEGORY_ARPU_PROFILES.items():
            assert 0 < profile["active_fraction"] <= 0.50, (
                f"Active fraction out of range for {cat}"
            )


# ===========================================================================
# 3. Calibration Profiles
# ===========================================================================

class TestCalibrationProfiles:
    def test_all_profiles_have_required_keys(self):
        from app.config.calibration_profiles import CALIBRATION_PROFILES
        for cat, profile in CALIBRATION_PROFILES.items():
            for key in ["rank_curve_factor", "review_ratio_factor", "confidence_ceiling"]:
                assert key in profile, f"Missing {key} in {cat}"

    def test_default_profile_factors_are_one(self):
        from app.config.calibration_profiles import get_calibration
        default = get_calibration("default")
        assert default["rank_curve_factor"] == 1.0
        assert default["review_ratio_factor"] == 1.0

    def test_finance_rank_curve_factor_less_than_one(self):
        from app.config.calibration_profiles import get_calibration
        finance = get_calibration("finance")
        assert finance["rank_curve_factor"] < 1.0, "Finance should have a downward rank correction"

    def test_fuzzy_match_works(self):
        from app.config.calibration_profiles import get_calibration, CALIBRATION_PROFILES
        result = get_calibration("Health & Fitness")
        assert result == CALIBRATION_PROFILES.get("health & fitness") or result == CALIBRATION_PROFILES.get("health")

    def test_unknown_falls_back_to_default(self):
        from app.config.calibration_profiles import get_calibration, CALIBRATION_PROFILES
        assert get_calibration("unknown_xyz") == CALIBRATION_PROFILES["default"]

    def test_confidence_ceiling_in_range(self):
        from app.config.calibration_profiles import CALIBRATION_PROFILES
        for cat, profile in CALIBRATION_PROFILES.items():
            ceiling = profile["confidence_ceiling"]
            assert 0.50 <= ceiling <= 1.0, f"Ceiling {ceiling} out of range for {cat}"


# ===========================================================================
# 4. ConfidenceEngine
# ===========================================================================

class TestConfidenceEngine:
    def setup_method(self):
        from app.services.confidence_engine import ConfidenceEngine
        self.engine = ConfidenceEngine()

    def test_full_signals_returns_medium_to_high_confidence(self):
        signals = _make_signals(
            ranking_history_days=30,
            has_rank=True, has_velocity=True, has_keywords=True, has_momentum=True,
            data_age_days=0, review_count=500, category="games",
        )
        result = self.engine.compute(signals)
        assert result["confidence_score"] >= 0.40, "Full signals should give medium+ confidence"

    def test_missing_rank_lowers_confidence(self):
        full_signals = _make_signals(has_rank=True, review_count=500)
        no_rank_signals = _make_signals(has_rank=False, review_count=500)
        conf_full = self.engine.compute(full_signals)["confidence_score"]
        conf_no_rank = self.engine.compute(no_rank_signals)["confidence_score"]
        assert conf_full >= conf_no_rank, "Missing rank should not increase confidence"

    def test_missing_all_signals_returns_low_confidence(self):
        signals = _make_signals(
            ranking_history_days=0,
            has_rank=False, has_velocity=False, has_keywords=False, has_momentum=False,
            data_age_days=100, review_count=0, category="medical",
        )
        result = self.engine.compute(signals)
        assert result["confidence_score"] < 0.40
        assert result["confidence_label"] == "low"

    def test_stale_data_reduces_confidence(self):
        fresh = _make_signals(data_age_days=1)
        stale = _make_signals(data_age_days=60)
        conf_fresh = self.engine.compute(fresh)["confidence_score"]
        conf_stale = self.engine.compute(stale)["confidence_score"]
        assert conf_fresh > conf_stale

    def test_more_reviews_increases_confidence(self):
        few = _make_signals(review_count=5)
        many = _make_signals(review_count=5000)
        conf_few = self.engine.compute(few)["confidence_score"]
        conf_many = self.engine.compute(many)["confidence_score"]
        assert conf_many >= conf_few

    def test_confidence_bounded_0_1(self):
        signals = _make_signals(
            ranking_history_days=365, review_count=100_000, data_age_days=0,
            has_rank=True, has_velocity=True, has_keywords=True, has_momentum=True,
        )
        result = self.engine.compute(signals)
        assert 0.0 <= result["confidence_score"] <= 1.0

    def test_confidence_never_exceeds_ceiling(self):
        from app.config.calibration_profiles import get_calibration
        signals = _make_signals(
            ranking_history_days=365, review_count=100_000, data_age_days=0,
            has_rank=True, has_velocity=True, has_keywords=True, has_momentum=True,
            category="finance",
        )
        result = self.engine.compute(signals)
        ceiling = get_calibration("finance")["confidence_ceiling"]
        assert result["confidence_score"] <= ceiling

    def test_label_matches_score(self):
        signals_high = _make_signals(
            ranking_history_days=30, review_count=1000, data_age_days=0,
            has_rank=True, has_velocity=True, has_keywords=True, has_momentum=True,
            category="games",
        )
        result = self.engine.compute(signals_high)
        score = result["confidence_score"]
        label = result["confidence_label"]
        if score >= 0.65:
            assert label == "high"
        elif score >= 0.40:
            assert label == "medium"
        else:
            assert label == "low"

    def test_factors_dict_has_all_keys(self):
        result = self.engine.compute(_make_signals())
        for key in ["ranking_history", "signal_completeness", "data_freshness",
                    "category_reliability", "review_coverage"]:
            assert key in result["factors"], f"Missing factor: {key}"

    def test_uncertainty_factor_high_confidence(self):
        uncertainty = self.engine._uncertainty_factor(0.90)
        # High confidence → uncertainty closer to 0.30
        assert uncertainty == pytest.approx(0.30 + (1.0 - 0.90) * 0.70, abs=0.01)

    def test_uncertainty_factor_low_confidence(self):
        uncertainty = self.engine._uncertainty_factor(0.20)
        assert uncertainty == pytest.approx(0.30 + (1.0 - 0.20) * 0.70, abs=0.01)

    def test_uncertainty_factor_bounded(self):
        for conf in [0.0, 0.5, 1.0, -0.1, 1.5]:
            u = self.engine._uncertainty_factor(conf)
            assert 0.30 <= u <= 1.00, f"Uncertainty {u} out of bounds for conf={conf}"


# ===========================================================================
# 5. DownloadEstimator — layers
# ===========================================================================

class TestDownloadEstimatorLayers:
    """Tests for individual layers using direct signals injection (no DB)."""

    def setup_method(self):
        from app.services.download_estimator import DownloadEstimator
        self.est = DownloadEstimator.__new__(DownloadEstimator)
        from app.services.confidence_engine import ConfidenceEngine
        self.est._confidence = ConfidenceEngine()

    def test_layer1_returns_zero_without_rank(self):
        signals = _make_signals(rank=None, has_rank=False)
        assert self.est._layer1_rank_curve(signals) == 0.0

    def test_layer1_higher_rank_more_downloads(self):
        rank10 = self.est._layer1_rank_curve(_make_signals(rank=10, category="games"))
        rank100 = self.est._layer1_rank_curve(_make_signals(rank=100, category="games"))
        assert rank10 > rank100, "Rank 10 should yield more than rank 100"

    def test_layer1_games_more_than_finance_same_rank(self):
        games = self.est._layer1_rank_curve(_make_signals(rank=20, category="games"))
        finance = self.est._layer1_rank_curve(_make_signals(rank=20, category="finance"))
        assert games > finance

    def test_layer2_returns_zero_without_velocity(self):
        signals = _make_signals(velocity=0.0, has_velocity=False)
        assert self.est._layer2_review_velocity(signals) == 0.0

    def test_layer2_higher_velocity_more_downloads(self):
        low_vel = self.est._layer2_review_velocity(_make_signals(velocity=1.0))
        high_vel = self.est._layer2_review_velocity(_make_signals(velocity=10.0))
        assert high_vel > low_vel

    def test_layer2_velocity_cap(self):
        normal = self.est._layer2_review_velocity(_make_signals(velocity=10.0))
        capped = self.est._layer2_review_velocity(_make_signals(velocity=1000.0))  # above 500 cap
        max_allowed = self.est._layer2_review_velocity(_make_signals(velocity=500.0))
        assert capped == max_allowed, "Velocity above 500/day should be capped"

    def test_layer3_returns_zero_without_keywords(self):
        signals = _make_signals(keyword_count=0, has_keywords=False)
        assert self.est._layer3_visibility(signals) == 0.0

    def test_layer3_more_keywords_more_downloads(self):
        low_kw = self.est._layer3_visibility(_make_signals(keyword_count=5, avg_traffic_score=30.0))
        high_kw = self.est._layer3_visibility(_make_signals(keyword_count=50, avg_traffic_score=60.0))
        assert high_kw > low_kw

    def test_layer4_returns_zero_without_momentum(self):
        signals = _make_signals(has_momentum=False, momentum_3d=0.5, momentum_7d=0.5)
        assert self.est._layer4_momentum(signals) == 0.0

    def test_layer4_positive_momentum_positive_adjustment(self):
        signals = _make_signals(has_momentum=True, momentum_3d=0.8, momentum_7d=0.6)
        adj = self.est._layer4_momentum(signals)
        assert adj > 0

    def test_layer4_negative_momentum_negative_adjustment(self):
        signals = _make_signals(has_momentum=True, momentum_3d=-0.8, momentum_7d=-0.6)
        adj = self.est._layer4_momentum(signals)
        assert adj < 0

    def test_layer4_bounded_positive(self):
        signals = _make_signals(has_momentum=True, momentum_3d=100.0, momentum_7d=100.0)
        adj = self.est._layer4_momentum(signals)
        assert adj <= 0.20, f"Positive momentum capped at +20%, got {adj}"

    def test_layer4_bounded_negative(self):
        signals = _make_signals(has_momentum=True, momentum_3d=-100.0, momentum_7d=-100.0)
        adj = self.est._layer4_momentum(signals)
        assert adj >= -0.30, f"Negative momentum capped at -30%, got {adj}"


# ===========================================================================
# 6. DownloadEstimator — weights
# ===========================================================================

class TestDownloadEstimatorWeights:
    def setup_method(self):
        from app.services.download_estimator import DownloadEstimator
        self.est = DownloadEstimator.__new__(DownloadEstimator)
        from app.services.confidence_engine import ConfidenceEngine
        self.est._confidence = ConfidenceEngine()

    def test_default_weights_sum_to_one(self):
        signals = _make_signals(has_rank=True, has_velocity=True, has_keywords=True)
        w = self.est._compute_weights(signals)
        total = w["rank"] + w["review"] + w["visibility"]
        assert abs(total - 1.0) < 1e-6, f"Weights don't sum to 1: {total}"

    def test_no_rank_weight_redistribution(self):
        signals = _make_signals(has_rank=False, has_velocity=True, has_keywords=True)
        w = self.est._compute_weights(signals)
        assert w["rank"] == 0.0
        total = w["rank"] + w["review"] + w["visibility"]
        assert abs(total - 1.0) < 1e-6

    def test_no_velocity_weight_redistribution(self):
        signals = _make_signals(has_rank=True, has_velocity=False, has_keywords=True)
        w = self.est._compute_weights(signals)
        assert w["review"] == 0.0
        total = w["rank"] + w["review"] + w["visibility"]
        assert abs(total - 1.0) < 1e-6

    def test_no_keywords_weight_redistribution(self):
        signals = _make_signals(has_rank=True, has_velocity=True, has_keywords=False)
        w = self.est._compute_weights(signals)
        assert w["visibility"] == 0.0
        total = w["rank"] + w["review"] + w["visibility"]
        assert abs(total - 1.0) < 1e-6

    def test_all_signals_missing_fallback_to_defaults(self):
        signals = _make_signals(has_rank=False, has_velocity=False, has_keywords=False)
        w = self.est._compute_weights(signals)
        # When no signals present, fallback to defaults
        assert w["rank"] == 0.45
        assert w["review"] == 0.25
        assert w["visibility"] == 0.20


# ===========================================================================
# 7. DownloadEstimator — full compute (mocked DB)
# ===========================================================================

class TestDownloadEstimatorCompute:
    def _make_estimator_with_signals(self, signals_override=None):
        """Create a DownloadEstimator with _gather_signals mocked."""
        from app.services.download_estimator import DownloadEstimator
        db = MagicMock()
        est = DownloadEstimator(db)

        base_signals = _make_signals()
        if signals_override:
            base_signals.update(signals_override)

        est._gather_signals = MagicMock(return_value=base_signals)
        return est

    def test_result_has_all_expected_keys(self):
        est = self._make_estimator_with_signals()
        app = _make_app()
        result = est._compute(app)
        for key in [
            "estimated_downloads_daily", "estimated_downloads_monthly",
            "downloads_range_low", "downloads_range_high",
            "estimation_confidence", "confidence_label",
            "factor_breakdown", "estimation_notes",
        ]:
            assert key in result, f"Missing key: {key}"

    def test_range_low_less_than_monthly_less_than_range_high(self):
        est = self._make_estimator_with_signals()
        app = _make_app()
        result = est._compute(app)
        assert result["downloads_range_low"] <= result["estimated_downloads_monthly"]
        assert result["estimated_downloads_monthly"] <= result["downloads_range_high"]

    def test_floor_is_at_least_1_daily(self):
        """App with no rank, no velocity, no keywords, no reviews → still gets conservative floor."""
        est = self._make_estimator_with_signals({
            "rank": None, "has_rank": False,
            "velocity": 0.0, "has_velocity": False,
            "keyword_count": 0, "has_keywords": False,
            "has_momentum": False,
            "review_count": 0,
            "ranking_history_days": 0,
        })
        app = _make_app()
        result = est._compute(app)
        assert result["estimated_downloads_daily"] >= 1, "Floor should be at least 1 download/day"

    def test_higher_rank_more_monthly_downloads(self):
        est_rank10 = self._make_estimator_with_signals({"rank": 10, "has_rank": True})
        est_rank200 = self._make_estimator_with_signals({"rank": 200, "has_rank": True})
        app = _make_app()
        r10 = est_rank10._compute(app)["estimated_downloads_monthly"]
        r200 = est_rank200._compute(app)["estimated_downloads_monthly"]
        assert r10 > r200

    def test_anti_manipulation_cap_applies(self):
        """Insanely high velocity should be capped."""
        est = self._make_estimator_with_signals({
            "velocity": 10_000.0,  # far above 500/day cap
            "has_velocity": True,
            "rank": 1,
            "has_rank": True,
        })
        app = _make_app(primary_category="games")
        result = est._compute(app)
        # Max plausible for games is 2M/day → 60M/month
        assert result["estimated_downloads_monthly"] <= 60_000_000 * 1.3  # with uncertainty

    def test_low_confidence_wider_range(self):
        """Low confidence signals → wider uncertainty band."""
        low_conf_signals = {
            "ranking_history_days": 0,
            "has_rank": False, "has_velocity": False,
            "has_keywords": False, "has_momentum": False,
            "data_age_days": 90, "review_count": 1,
        }
        high_conf_signals = {
            "ranking_history_days": 30,
            "has_rank": True, "has_velocity": True,
            "has_keywords": True, "has_momentum": True,
            "data_age_days": 0, "review_count": 5000,
        }
        est_low = self._make_estimator_with_signals(low_conf_signals)
        est_high = self._make_estimator_with_signals(high_conf_signals)
        app = _make_app()

        r_low = est_low._compute(app)
        r_high = est_high._compute(app)

        low_spread = r_low["downloads_range_high"] - r_low["downloads_range_low"]
        high_spread = r_high["downloads_range_high"] - r_high["downloads_range_low"]

        # Low confidence should result in relatively wider range as fraction of monthly
        low_monthly = max(r_low["estimated_downloads_monthly"], 1)
        high_monthly = max(r_high["estimated_downloads_monthly"], 1)
        low_ratio = low_spread / low_monthly
        high_ratio = high_spread / high_monthly
        assert low_ratio >= high_ratio, (
            f"Low confidence should have wider relative range: {low_ratio:.2f} vs {high_ratio:.2f}"
        )

    def test_compute_and_save_writes_to_app(self):
        est = self._make_estimator_with_signals()
        app = _make_app()
        min_dl, max_dl, conf = est.compute_and_save(app)
        assert app.estimated_installs_min == min_dl
        assert app.estimated_installs_max == max_dl
        assert app.install_confidence == conf
        assert min_dl > 0
        assert conf > 0.0


# ===========================================================================
# 8. Revenue Estimator — ARPU profiles integration
# ===========================================================================

class TestRevenueEstimatorArpuProfiles:
    def _make_rev_estimator(self):
        from app.services.revenue_estimator import RevenueEstimator
        db = MagicMock()
        return RevenueEstimator(db)

    def test_finance_more_revenue_than_games_same_installs(self):
        """Finance ARPU is higher than Games → higher revenue for same installs."""
        est = self._make_rev_estimator()
        app_finance = _make_app(primary_category="Finance", in_app_purchases=["Premium"])
        app_games = _make_app(primary_category="Games", in_app_purchases=["Coins"])

        rev_finance = est._compute_from_installs(app_finance, 10_000, 30_000)
        rev_games = est._compute_from_installs(app_games, 10_000, 30_000)

        assert rev_finance["estimated_revenue_monthly_max"] > rev_games["estimated_revenue_monthly_max"], (
            "Finance should generate more revenue than Games at same installs"
        )

    def test_monetization_hint_in_result(self):
        est = self._make_rev_estimator()
        app = _make_app(primary_category="Productivity", in_app_purchases=["Pro"])
        result = est._compute_from_installs(app, 5_000, 15_000)
        assert "monetization_model_hint" in result
        assert result["monetization_model_hint"] is not None

    def test_revenue_range_keys_present(self):
        est = self._make_rev_estimator()
        app = _make_app(primary_category="Health & Fitness", in_app_purchases=["Premium"])
        result = est._compute_from_installs(app, 5_000, 15_000)
        assert "revenue_range_low" in result
        assert "revenue_range_high" in result

    def test_paid_app_revenue_from_price(self):
        est = self._make_rev_estimator()
        app = _make_app(primary_category="Utilities", is_free=False, price=4.99)
        result = est._compute_from_installs(app, 1_000, 5_000)
        assert result["model"].startswith("paid_")
        # Revenue = installs × price × 0.7
        expected_min = 1_000 * 4.99 * 0.7
        assert result["estimated_revenue_monthly_min"] == pytest.approx(expected_min, rel=0.01)

    def test_free_app_no_iap_uses_ads_model(self):
        est = self._make_rev_estimator()
        app = _make_app(primary_category="News", is_free=True, in_app_purchases=None)
        result = est._compute_from_installs(app, 10_000, 50_000)
        assert result["model"] == "free_ads_only"

    def test_revenue_min_max_correct_ordering(self):
        est = self._make_rev_estimator()
        app = _make_app(primary_category="Productivity", in_app_purchases=["Pro"])
        result = est._compute_from_installs(app, 10_000, 30_000)
        assert result["estimated_revenue_monthly_min"] <= result["estimated_revenue_monthly_max"]

    def test_empty_returns_sensible_defaults(self):
        from app.services.revenue_estimator import RevenueEstimator
        result = RevenueEstimator._empty()
        assert result["estimated_revenue_monthly_min"] == 0.0
        assert result["monetization_model_hint"] == "unknown"


# ===========================================================================
# 9. DownloadEstimateResponse schema
# ===========================================================================

class TestDownloadEstimateResponseSchema:
    def test_schema_roundtrip(self):
        from app.models.schemas import DownloadEstimateResponse, FactorBreakdown
        data = {
            "app_id": 42,
            "estimated_downloads_daily": 5000,
            "estimated_downloads_monthly": 150_000,
            "downloads_range_low": 100_000,
            "downloads_range_high": 200_000,
            "estimated_revenue_monthly": 25_000.0,
            "revenue_range_low": 15_000.0,
            "revenue_range_high": 35_000.0,
            "estimation_confidence": 0.72,
            "confidence_label": "high",
            "monetization_model_hint": "subscription",
            "factor_breakdown": {
                "rank_baseline": 4800,
                "review_velocity_estimate": 3000,
                "visibility_estimate": 200,
                "momentum_adjustment_pct": 5.0,
                "weights_used": {"rank": 0.45, "review": 0.25, "visibility": 0.20},
                "confidence_factors": {"ranking_history": 0.8},
            },
            "estimation_notes": "Rank #42 in charts. Confidence: high (72%).",
        }
        response = DownloadEstimateResponse(**data)
        assert response.app_id == 42
        assert response.confidence_label == "high"
        assert response.factor_breakdown.rank_baseline == 4800

    def test_schema_optional_revenue_fields(self):
        from app.models.schemas import DownloadEstimateResponse, FactorBreakdown
        data = {
            "app_id": 1,
            "estimated_downloads_daily": 100,
            "estimated_downloads_monthly": 3000,
            "downloads_range_low": 1000,
            "downloads_range_high": 5000,
            "estimation_confidence": 0.30,
            "confidence_label": "low",
            "factor_breakdown": {},
            "estimation_notes": "No data.",
        }
        response = DownloadEstimateResponse(**data)
        assert response.estimated_revenue_monthly is None
        assert response.monetization_model_hint is None


# ===========================================================================
# 10. Realistic Estimates — shrinkage, conservative floors, overestimation guards
# ===========================================================================

class TestRealisticEstimates:
    """Verify that the shrinkage pipeline prevents gross overestimation for
    low-signal apps, and that confidence numerically affects the estimate."""

    def _make_estimator_with_signals(self, signals_override=None):
        from app.services.download_estimator import DownloadEstimator
        db = MagicMock()
        est = DownloadEstimator(db)
        base_signals = _make_signals()
        if signals_override:
            base_signals.update(signals_override)
        est._gather_signals = MagicMock(return_value=base_signals)
        return est

    def test_low_signal_app_estimates_conservatively(self):
        """No rank, few reviews, minimal keywords → daily estimate ≤ 30."""
        est = self._make_estimator_with_signals({
            "rank": None, "has_rank": False,
            "velocity": 0.033,       # ~1 review/month
            "review_count": 30,
            "keyword_count": 10, "avg_traffic_score": 30.0, "has_keywords": True,
            "has_momentum": False,
            "ranking_history_days": 0,
            "data_age_days": 5,
        })
        result = est._compute(_make_app(primary_category="utilities"))
        assert result["estimated_downloads_daily"] <= 30, (
            f"Low-signal app should estimate ≤30/day, got {result['estimated_downloads_daily']}"
        )

    def test_confidence_shrinkage_reduces_estimate(self):
        """Same raw signals; lower data quality (confidence) → lower or equal estimate."""
        base = {
            "rank": None, "has_rank": False,
            "velocity": 2.0, "review_count": 200,
            "keyword_count": 30, "avg_traffic_score": 60.0,
            "has_keywords": True, "has_momentum": False,
        }
        high_conf = dict(base)
        high_conf.update({"ranking_history_days": 14, "data_age_days": 1})
        low_conf = dict(base)
        low_conf.update({"ranking_history_days": 0, "data_age_days": 90, "review_count": 2})

        est_high = self._make_estimator_with_signals(high_conf)
        est_low = self._make_estimator_with_signals(low_conf)
        app = _make_app()

        result_high = est_high._compute(app)
        result_low = est_low._compute(app)

        assert result_high["estimated_downloads_daily"] >= result_low["estimated_downloads_daily"], (
            "Lower data quality (confidence) should not produce a higher estimate"
        )

    def test_revenue_zero_for_low_install_free_app(self):
        """Free app with no IAP and < 100 monthly installs → $0 ad revenue."""
        from app.services.revenue_estimator import RevenueEstimator
        est = RevenueEstimator(MagicMock())
        app = _make_app(primary_category="News", is_free=True, in_app_purchases=None)
        result = est._compute_from_installs(app, 20, 50)
        assert result["model"] == "free_ads_only"
        assert result["estimated_revenue_monthly_min"] == 0.0, (
            f"Low-install free app should have $0 ad revenue, got {result['estimated_revenue_monthly_min']}"
        )

    def test_visibility_l3_no_base_boost(self):
        """L3 with very few keywords should produce a small estimate (no 100/day additive base)."""
        from app.services.download_estimator import DownloadEstimator
        est = DownloadEstimator.__new__(DownloadEstimator)
        from app.services.confidence_engine import ConfidenceEngine
        est._confidence = ConfidenceEngine()

        signals = _make_signals(keyword_count=3, avg_traffic_score=10.0)
        result = est._layer3_visibility(signals)
        assert result < 10.0, (
            f"L3 with 3 low-traffic keywords should produce < 10/day, got {result}"
        )

    def test_review_scaling_reduces_l2_for_low_review_count(self):
        """L2 should be meaningfully smaller for apps with few total reviews."""
        from app.services.download_estimator import DownloadEstimator
        est = DownloadEstimator.__new__(DownloadEstimator)
        from app.services.confidence_engine import ConfidenceEngine
        est._confidence = ConfidenceEngine()

        low_reviews = _make_signals(velocity=1.0, review_count=5)
        high_reviews = _make_signals(velocity=1.0, review_count=500)

        l2_low = est._layer2_review_velocity(low_reviews)
        l2_high = est._layer2_review_velocity(high_reviews)

        assert l2_high > l2_low * 2, (
            f"L2 should be at least 2× larger at review_count=500 vs 5. "
            f"Low: {l2_low:.1f}, High: {l2_high:.1f}"
        )
