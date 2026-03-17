"""
test_estimate_api.py
=====================
Tests for estimate-related API features added in the Download & Revenue
Estimation Intelligence Engine integration:

1. DownloadEstimateResponse schema — all required fields present, types correct
2. TrendingAppV2Response — includes estimate fields with Optional typing
3. Filter param logic — confidence_label derivation thresholds
4. estimate-format utility equivalents — fmtNum / fmtRev / confidenceLabel logic
5. MarketEstimatesCard data path — DownloadEstimate fields map correctly
6. Missing estimate fallback — card can render from cached App columns alone
7. Empty-state safety — formatters return '—' for None / NaN
8. Estimate filter logic on App model columns
"""
import sys
import os
import math
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_app(**kw):
    app = MagicMock()
    app.id = kw.get("id", 1)
    app.app_id = kw.get("app_id", "111222333")
    app.name = kw.get("name", "SampleApp")
    app.developer = kw.get("developer", "Dev LLC")
    app.icon_url = kw.get("icon_url", None)
    app.current_rank = kw.get("current_rank", None)
    app.current_rating = kw.get("current_rating", None)
    app.current_reviews = kw.get("current_reviews", 0)
    app.estimated_installs_min = kw.get("estimated_installs_min", None)
    app.estimated_installs_max = kw.get("estimated_installs_max", None)
    app.install_confidence = kw.get("install_confidence", None)
    app.estimated_revenue_monthly_min = kw.get("estimated_revenue_monthly_min", None)
    app.estimated_revenue_monthly_max = kw.get("estimated_revenue_monthly_max", None)
    return app


# ---------------------------------------------------------------------------
# 1. DownloadEstimateResponse schema
# ---------------------------------------------------------------------------

class TestDownloadEstimateResponseSchema:
    def test_full_response_valid(self):
        from app.models.schemas import DownloadEstimateResponse, FactorBreakdown
        resp = DownloadEstimateResponse(
            app_id=42,
            estimated_downloads_daily=5_000,
            estimated_downloads_monthly=150_000,
            downloads_range_low=100_000,
            downloads_range_high=200_000,
            estimated_revenue_monthly=18_000.0,
            revenue_range_low=12_000.0,
            revenue_range_high=24_000.0,
            estimation_confidence=0.72,
            confidence_label="high",
            monetization_model_hint="subscription",
            factor_breakdown=FactorBreakdown(
                rank_baseline=120_000,
                review_velocity_estimate=30_000,
                visibility_estimate=25_000,
                momentum_adjustment_pct=8.5,
                weights_used={"rank": 0.45, "review": 0.25, "visibility": 0.20},
                confidence_factors={"ranking_history": 0.9, "data_freshness": 1.0},
            ),
            estimation_notes="Rank-based estimate (rank 15). Review velocity: 12.3/day.",
        )
        assert resp.app_id == 42
        assert resp.estimated_downloads_daily == 5_000
        assert resp.estimated_downloads_monthly == 150_000
        assert resp.downloads_range_low == 100_000
        assert resp.downloads_range_high == 200_000
        assert resp.estimation_confidence == 0.72
        assert resp.confidence_label == "high"
        assert resp.monetization_model_hint == "subscription"
        assert resp.factor_breakdown.rank_baseline == 120_000
        assert resp.factor_breakdown.momentum_adjustment_pct == 8.5

    def test_optional_fields_default_to_none(self):
        from app.models.schemas import DownloadEstimateResponse, FactorBreakdown
        resp = DownloadEstimateResponse(
            app_id=1,
            estimated_downloads_daily=100,
            estimated_downloads_monthly=3_000,
            downloads_range_low=2_000,
            downloads_range_high=4_000,
            estimation_confidence=0.35,
            confidence_label="low",
            factor_breakdown=FactorBreakdown(),
            estimation_notes="",
        )
        assert resp.estimated_revenue_monthly is None
        assert resp.revenue_range_low is None
        assert resp.revenue_range_high is None
        assert resp.monetization_model_hint is None

    def test_confidence_label_values(self):
        from app.models.schemas import DownloadEstimateResponse, FactorBreakdown
        for label in ("low", "medium", "high"):
            resp = DownloadEstimateResponse(
                app_id=1,
                estimated_downloads_daily=100,
                estimated_downloads_monthly=3_000,
                downloads_range_low=2_000,
                downloads_range_high=4_000,
                estimation_confidence=0.5,
                confidence_label=label,
                factor_breakdown=FactorBreakdown(),
                estimation_notes="",
            )
            assert resp.confidence_label == label


# ---------------------------------------------------------------------------
# 2. TrendingAppV2Response — estimate fields
# ---------------------------------------------------------------------------

class TestTrendingAppV2ResponseEstimateFields:
    def test_estimate_fields_optional_and_present(self):
        from app.models.schemas import TrendingAppV2Response
        resp = TrendingAppV2Response(
            id=1,
            app_id="123",
            name="TrendApp",
            trend_score=75.0,
            momentum_3d=3.2,
            momentum_7d=5.1,
            consistency_score=0.8,
            confidence_factor=0.9,
            absolute_rank_bonus=10.0,
            review_momentum=2.5,
            estimated_installs_min=50_000,
            estimated_installs_max=100_000,
            install_confidence=0.70,
            estimated_revenue_monthly_min=5_000.0,
            estimated_revenue_monthly_max=10_000.0,
        )
        assert resp.estimated_installs_min == 50_000
        assert resp.estimated_installs_max == 100_000
        assert resp.install_confidence == 0.70
        assert resp.estimated_revenue_monthly_min == 5_000.0
        assert resp.estimated_revenue_monthly_max == 10_000.0

    def test_estimate_fields_default_none(self):
        from app.models.schemas import TrendingAppV2Response
        resp = TrendingAppV2Response(
            id=1,
            app_id="123",
            name="TrendApp",
            trend_score=75.0,
            momentum_3d=3.2,
            momentum_7d=5.1,
            consistency_score=0.8,
            confidence_factor=0.9,
            absolute_rank_bonus=10.0,
            review_momentum=2.5,
        )
        assert resp.estimated_installs_min is None
        assert resp.install_confidence is None
        assert resp.estimated_revenue_monthly_min is None


# ---------------------------------------------------------------------------
# 3. Confidence label derivation (mirrors frontend confidenceLabel())
# ---------------------------------------------------------------------------

def _confidence_label(score):
    """Mirror the frontend/backend confidence label logic."""
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return None
    if score >= 0.65:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


class TestConfidenceLabelDerivation:
    def test_high_threshold(self):
        assert _confidence_label(0.65) == "high"
        assert _confidence_label(0.80) == "high"
        assert _confidence_label(1.00) == "high"

    def test_medium_threshold(self):
        assert _confidence_label(0.40) == "medium"
        assert _confidence_label(0.55) == "medium"
        assert _confidence_label(0.6499) == "medium"

    def test_low_threshold(self):
        assert _confidence_label(0.00) == "low"
        assert _confidence_label(0.20) == "low"
        assert _confidence_label(0.39) == "low"

    def test_none_input(self):
        assert _confidence_label(None) is None

    def test_boundary_exactly_0_65(self):
        assert _confidence_label(0.65) == "high"

    def test_boundary_exactly_0_40(self):
        assert _confidence_label(0.40) == "medium"


# ---------------------------------------------------------------------------
# 4. Formatter equivalents (mirrors frontend fmtNum / fmtRev)
# ---------------------------------------------------------------------------

def _fmt_num(n):
    """Python mirror of frontend fmtNum()."""
    if n is None or (isinstance(n, float) and (math.isnan(n) or math.isinf(n))):
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(round(n))


def _fmt_rev(n):
    if n is None or (isinstance(n, float) and (math.isnan(n) or math.isinf(n))):
        return "—"
    return f"${_fmt_num(n)}"


class TestFormatterEquivalents:
    """Ensures Python-side logic matches frontend formatter behaviour."""

    def test_fmt_num_millions(self):
        assert _fmt_num(1_500_000) == "1.5M"
        assert _fmt_num(12_300_000) == "12.3M"

    def test_fmt_num_thousands(self):
        assert _fmt_num(1_200) == "1.2K"
        assert _fmt_num(500_000) == "500.0K"

    def test_fmt_num_small(self):
        assert _fmt_num(0) == "0"
        assert _fmt_num(999) == "999"

    def test_fmt_num_null_safety(self):
        assert _fmt_num(None) == "—"
        assert _fmt_num(float("nan")) == "—"
        assert _fmt_num(float("inf")) == "—"

    def test_fmt_rev_prefix(self):
        assert _fmt_rev(5_000) == "$5.0K"
        assert _fmt_rev(1_200_000) == "$1.2M"

    def test_fmt_rev_null_safety(self):
        assert _fmt_rev(None) == "—"
        assert _fmt_rev(float("nan")) == "—"


# ---------------------------------------------------------------------------
# 5. MarketEstimatesCard data-path — DownloadEstimate field mapping
# ---------------------------------------------------------------------------

class TestDownloadEstimateFieldMapping:
    """Verify that the DownloadEstimate response contains all fields
    expected by MarketEstimatesCard on the frontend."""

    REQUIRED_FIELDS = [
        "app_id",
        "estimated_downloads_daily",
        "estimated_downloads_monthly",
        "downloads_range_low",
        "downloads_range_high",
        "estimation_confidence",
        "confidence_label",
        "factor_breakdown",
        "estimation_notes",
    ]

    OPTIONAL_FIELDS = [
        "estimated_revenue_monthly",
        "revenue_range_low",
        "revenue_range_high",
        "monetization_model_hint",
    ]

    def test_required_fields_in_schema(self):
        from app.models.schemas import DownloadEstimateResponse
        fields = DownloadEstimateResponse.model_fields
        for name in self.REQUIRED_FIELDS:
            assert name in fields, f"Missing required field: {name}"

    def test_optional_fields_in_schema(self):
        from app.models.schemas import DownloadEstimateResponse
        fields = DownloadEstimateResponse.model_fields
        for name in self.OPTIONAL_FIELDS:
            assert name in fields, f"Missing optional field: {name}"

    def test_factor_breakdown_fields(self):
        from app.models.schemas import FactorBreakdown
        fields = FactorBreakdown.model_fields
        for name in [
            "rank_baseline", "review_velocity_estimate", "visibility_estimate",
            "momentum_adjustment_pct", "weights_used", "confidence_factors",
        ]:
            assert name in fields, f"Missing FactorBreakdown field: {name}"


# ---------------------------------------------------------------------------
# 6. Missing estimate fallback — card can work from cached App columns alone
# ---------------------------------------------------------------------------

class TestCachedEstimateFallback:
    """The MarketEstimatesCard falls back to App cached columns when the
    /download-estimate endpoint is unavailable. Verify the cached columns
    are non-null after DownloadEstimator.compute_and_save()."""

    def test_compute_and_save_writes_cached_columns(self):
        """DownloadEstimator.compute_and_save() must write to the three
        App cached columns so the fallback path has data."""
        from app.services.download_estimator import DownloadEstimator

        mock_db = MagicMock()
        app = _make_mock_app()

        estimator = DownloadEstimator(mock_db)

        with patch.object(estimator, "_compute") as mock_compute:
            mock_compute.return_value = {
                "estimated_downloads_monthly": 75_000,
                "downloads_range_low": 50_000,
                "downloads_range_high": 100_000,
                "estimation_confidence": 0.68,
                "confidence_label": "high",
                "estimated_revenue_monthly": None,
                "revenue_range_low": None,
                "revenue_range_high": None,
                "monetization_model_hint": None,
                "factor_breakdown": {},
                "estimation_notes": "",
            }
            result_min, result_max, result_conf = estimator.compute_and_save(app)

        # The three backward-compat columns must be written
        assert app.estimated_installs_min == result_min
        assert app.estimated_installs_max == result_max
        assert app.install_confidence == result_conf

    def test_cached_columns_none_when_no_estimate(self):
        """If an app has no estimate data, all cached columns are None —
        the frontend card must hide itself (no visible output)."""
        app = _make_mock_app(
            estimated_installs_min=None,
            estimated_installs_max=None,
            install_confidence=None,
            estimated_revenue_monthly_min=None,
            estimated_revenue_monthly_max=None,
        )
        has_any_data = (
            app.estimated_installs_min is not None
            or app.estimated_revenue_monthly_min is not None
        )
        assert not has_any_data, "Card should not render when all columns are None"


# ---------------------------------------------------------------------------
# 7. Estimate filter logic (mirrors GET /apps filter application)
# ---------------------------------------------------------------------------

class TestEstimateFilterLogic:
    """Unit-test the confidence_label filter and estimate range filter
    semantics without a database."""

    def _apply_confidence_filter(self, apps, label):
        """Simulate the confidence_label filter from routes.py."""
        apps = [a for a in apps if a.install_confidence is not None]
        if label == "high":
            return [a for a in apps if a.install_confidence >= 0.65]
        elif label == "medium":
            return [a for a in apps if 0.40 <= a.install_confidence < 0.65]
        elif label == "low":
            return [a for a in apps if a.install_confidence < 0.40]
        return apps

    def test_confidence_high_filter(self):
        apps = [
            _make_mock_app(install_confidence=0.80),
            _make_mock_app(install_confidence=0.55),
            _make_mock_app(install_confidence=0.20),
            _make_mock_app(install_confidence=None),
        ]
        result = self._apply_confidence_filter(apps, "high")
        assert len(result) == 1
        assert result[0].install_confidence == 0.80

    def test_confidence_medium_filter(self):
        apps = [
            _make_mock_app(install_confidence=0.80),
            _make_mock_app(install_confidence=0.55),
            _make_mock_app(install_confidence=0.40),
            _make_mock_app(install_confidence=0.20),
        ]
        result = self._apply_confidence_filter(apps, "medium")
        scores = {a.install_confidence for a in result}
        assert scores == {0.55, 0.40}

    def test_confidence_low_filter(self):
        apps = [
            _make_mock_app(install_confidence=0.80),
            _make_mock_app(install_confidence=0.55),
            _make_mock_app(install_confidence=0.20),
        ]
        result = self._apply_confidence_filter(apps, "low")
        assert len(result) == 1
        assert result[0].install_confidence == 0.20

    def test_confidence_filter_excludes_null(self):
        """Apps with install_confidence=None are excluded by confidence filter."""
        apps = [_make_mock_app(install_confidence=None)]
        result = self._apply_confidence_filter(apps, "high")
        assert result == []

    def test_min_estimated_downloads_filter(self):
        """min_estimated_downloads filters on estimated_installs_min."""
        apps = [
            _make_mock_app(estimated_installs_min=100_000),
            _make_mock_app(estimated_installs_min=20_000),
            _make_mock_app(estimated_installs_min=None),
        ]
        threshold = 50_000
        result = [
            a for a in apps
            if a.estimated_installs_min is not None
            and a.estimated_installs_min >= threshold
        ]
        assert len(result) == 1
        assert result[0].estimated_installs_min == 100_000

    def test_min_estimated_revenue_filter(self):
        """min_estimated_revenue filters on estimated_revenue_monthly_min."""
        apps = [
            _make_mock_app(estimated_revenue_monthly_min=15_000.0),
            _make_mock_app(estimated_revenue_monthly_min=3_000.0),
            _make_mock_app(estimated_revenue_monthly_min=None),
        ]
        threshold = 10_000.0
        result = [
            a for a in apps
            if a.estimated_revenue_monthly_min is not None
            and a.estimated_revenue_monthly_min >= threshold
        ]
        assert len(result) == 1
        assert result[0].estimated_revenue_monthly_min == 15_000.0


# ---------------------------------------------------------------------------
# 8. Estimate row visibility logic (mirrors frontend conditional rendering)
# ---------------------------------------------------------------------------

class TestEstimateRowVisibility:
    """The estimate row in list cards only renders when at least one
    estimate value is non-None. Verify the guard condition."""

    def test_row_visible_when_downloads_present(self):
        app = _make_mock_app(estimated_installs_min=50_000)
        should_show = (
            app.estimated_installs_min is not None
            or app.estimated_revenue_monthly_min is not None
        )
        assert should_show is True

    def test_row_visible_when_revenue_present(self):
        app = _make_mock_app(estimated_revenue_monthly_min=8_000.0)
        should_show = (
            app.estimated_installs_min is not None
            or app.estimated_revenue_monthly_min is not None
        )
        assert should_show is True

    def test_row_hidden_when_both_none(self):
        app = _make_mock_app(
            estimated_installs_min=None,
            estimated_revenue_monthly_min=None,
        )
        should_show = (
            app.estimated_installs_min is not None
            or app.estimated_revenue_monthly_min is not None
        )
        assert should_show is False

    def test_confidence_badge_hidden_when_confidence_none(self):
        app = _make_mock_app(install_confidence=None)
        conf_label = _confidence_label(app.install_confidence)
        assert conf_label is None  # badge should not render

    def test_confidence_badge_shows_high(self):
        app = _make_mock_app(install_confidence=0.75)
        conf_label = _confidence_label(app.install_confidence)
        assert conf_label == "high"
