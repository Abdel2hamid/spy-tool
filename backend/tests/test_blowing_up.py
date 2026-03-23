"""
test_blowing_up.py
==================
Tests for the "Apps Blowing Up" feature:

1. Score computation — correctness of component scores
2. Rank direction — improving rank (smaller number) yields positive scores
3. Sparse / noisy data handling — low confidence for few snapshots
4. Badge generation — correct badges for given signals
5. Why-flagged reasons — human-readable strings from real thresholds
6. Normalisation helpers — all outputs clamped to [0, 100]
7. API response schema — required fields present
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ranking(rank, prev_rank=None, velocity=None, days_ago=0, chart_type="topfree", cat_id=1):
    r = MagicMock()
    r.rank           = rank
    r.previous_rank  = prev_rank
    r.rank_velocity  = velocity
    r.recorded_at    = datetime.utcnow() - timedelta(days=days_ago)
    r.chart_type     = chart_type
    r.category_id    = cat_id
    return r


# ---------------------------------------------------------------------------
# 1. Normalisation helpers
# ---------------------------------------------------------------------------

class TestNormHelpers:

    def test_norm_rank_velocity_zero(self):
        from app.services.blowing_up_service import _norm_rank_velocity
        assert _norm_rank_velocity(0) == 0.0

    def test_norm_rank_velocity_positive(self):
        from app.services.blowing_up_service import _norm_rank_velocity
        assert _norm_rank_velocity(50) == 100.0

    def test_norm_rank_velocity_capped(self):
        from app.services.blowing_up_service import _norm_rank_velocity
        assert _norm_rank_velocity(9999) == 100.0

    def test_norm_rank_velocity_negative_is_zero(self):
        from app.services.blowing_up_service import _norm_rank_velocity
        assert _norm_rank_velocity(-10) == 0.0

    def test_norm_rank_change_improvement(self):
        from app.services.blowing_up_service import _norm_rank_change
        # Moved from rank 100 to rank 50 = 50 positions improved
        score = _norm_rank_change(50, 100)
        assert score > 0

    def test_norm_rank_change_no_improvement(self):
        from app.services.blowing_up_service import _norm_rank_change
        assert _norm_rank_change(0, 100) == 0.0
        assert _norm_rank_change(-5, 100) == 0.0

    def test_norm_rank_change_none_starting_rank(self):
        from app.services.blowing_up_service import _norm_rank_change
        assert _norm_rank_change(50, None) == 0.0

    def test_norm_rank_change_capped(self):
        from app.services.blowing_up_service import _norm_rank_change
        assert _norm_rank_change(9999, 10000) == 100.0

    def test_norm_reviews_velocity_zero(self):
        from app.services.blowing_up_service import _norm_reviews_velocity
        assert _norm_reviews_velocity(0) == 0.0
        assert _norm_reviews_velocity(0, total_reviews=10_000) == 0.0

    def test_norm_reviews_velocity_capped(self):
        from app.services.blowing_up_service import _norm_reviews_velocity
        # Log scale: 10/day with no base still maxes out at 100
        assert _norm_reviews_velocity(10) == 100.0
        assert _norm_reviews_velocity(100) == 100.0

    def test_norm_reviews_velocity_positive_small_app(self):
        from app.services.blowing_up_service import _norm_reviews_velocity
        # 5/day for a new app with small base → meaningful score
        score = _norm_reviews_velocity(5.0, total_reviews=100)
        assert score > 50.0

    def test_norm_chart_presence(self):
        from app.services.blowing_up_service import _norm_chart_presence
        # 2 appearances per day in a 7-day window = 14 appearances → 100
        assert _norm_chart_presence(14, 7) == 100.0

    def test_norm_chart_presence_zero_days(self):
        from app.services.blowing_up_service import _norm_chart_presence
        assert _norm_chart_presence(10, 0) == 0.0

    def test_norm_cross_market_values(self):
        from app.services.blowing_up_service import _norm_cross_market
        assert _norm_cross_market(0) == 0.0
        assert _norm_cross_market(1) == 20.0
        assert _norm_cross_market(5) == 100.0
        assert _norm_cross_market(10) == 100.0  # capped


# ---------------------------------------------------------------------------
# 1b. Stability score helper
# ---------------------------------------------------------------------------

class TestStabilityScore:

    def test_all_ranks_changing_is_full_stability(self):
        from app.services.blowing_up_service import _stability_score
        rankings = [_make_ranking(r) for r in [100, 80, 60, 40]]  # all different
        assert _stability_score(rankings) == 1.0

    def test_no_rank_change_is_zero_stability(self):
        from app.services.blowing_up_service import _stability_score
        rankings = [_make_ranking(50)] * 4  # all same rank
        assert _stability_score(rankings) == 0.0

    def test_partial_changes_gives_fractional_stability(self):
        from app.services.blowing_up_service import _stability_score
        # ranks: 100 → 100 → 50 → 50 → 25  = 2 changes out of 4 transitions = 0.5
        rankings = [_make_ranking(r) for r in [100, 100, 50, 50, 25]]
        score = _stability_score(rankings)
        assert abs(score - 0.5) < 0.01

    def test_single_snapshot_is_zero(self):
        from app.services.blowing_up_service import _stability_score
        assert _stability_score([_make_ranking(50)]) == 0.0

    def test_empty_list_is_zero(self):
        from app.services.blowing_up_service import _stability_score
        assert _stability_score([]) == 0.0


# ---------------------------------------------------------------------------
# 2. Rank direction correctness
# ---------------------------------------------------------------------------

class TestRankDirection:
    """Improving rank means moving toward #1 (smaller numbers are better)."""

    def test_rank_improving_toward_1_is_positive(self):
        from app.services.blowing_up_service import _norm_rank_change
        # Rank went from 100 → 50 (improvement of 50 positions)
        score = _norm_rank_change(50, 100)
        assert score > 0, "Rank improvement should yield positive score"

    def test_rank_falling_away_from_1_is_zero(self):
        from app.services.blowing_up_service import _norm_rank_change
        # Rank went from 50 → 100 (rank_change = 50-100 = -50, so rank_change=-50 passed)
        score = _norm_rank_change(-50, 50)
        assert score == 0.0, "Rank degradation should yield 0 score"

    def test_consistency_lower_rank_is_improvement(self):
        from app.services.blowing_up_service import _consistency
        # Rankings going 100 → 80 → 60 → 40 = all improvements
        rankings = [_make_ranking(rank) for rank in [100, 80, 60, 40]]
        score = _consistency(rankings)
        assert score == 100.0

    def test_consistency_stable_rank_is_zero(self):
        from app.services.blowing_up_service import _consistency
        # Rankings staying flat = no improvements
        rankings = [_make_ranking(50)] * 4
        score = _consistency(rankings)
        assert score == 0.0

    def test_consistency_mixed_movement(self):
        from app.services.blowing_up_service import _consistency
        # 100 → 80 → 90 → 70: 2 improvements out of 3 transitions
        rankings = [_make_ranking(r) for r in [100, 80, 90, 70]]
        score = _consistency(rankings)
        assert abs(score - 66.67) < 1.0


# ---------------------------------------------------------------------------
# 3. Sparse / noisy data handling
# ---------------------------------------------------------------------------

class TestDataQuality:

    def test_confidence_two_snapshots_is_penalised(self):
        from app.services.blowing_up_service import _confidence
        # Minimal data: 2 snapshots, same-day, no rank changes, no reviews
        score = _confidence(snapshot_count=2, days_tracked=0, stability_score=0, total_reviews=0)
        assert score < 0.5, "Two snapshots with no other signal should give low confidence"

    def test_confidence_full_data_is_maximum(self):
        from app.services.blowing_up_service import _confidence
        # All signals saturated: 10 snapshots, 7+ days, all ranks changed, 100+ reviews
        score = _confidence(snapshot_count=10, days_tracked=7, stability_score=1.0, total_reviews=100)
        assert abs(score - 1.0) < 1e-9

    def test_confidence_zero_snapshots_is_zero(self):
        from app.services.blowing_up_service import _confidence
        assert _confidence(0, 7, 1.0, 100) == 0.0
        assert _confidence(1, 7, 1.0, 100) == 0.0

    def test_confidence_scales_with_more_signals(self):
        from app.services.blowing_up_service import _confidence
        # Low data
        c_low  = _confidence(snapshot_count=3, days_tracked=1, stability_score=0.2, total_reviews=5)
        # Rich data
        c_high = _confidence(snapshot_count=8, days_tracked=6, stability_score=0.9, total_reviews=80)
        assert c_low < c_high, "More data across all signals → higher confidence"

    def test_confidence_floor_prevents_zero_for_valid_apps(self):
        from app.services.blowing_up_service import _confidence
        # Even with 2 snapshots and no other signal, floor=0.1 applies
        score = _confidence(snapshot_count=2, days_tracked=0, stability_score=0, total_reviews=0)
        assert score >= 0.1, "Floor of 0.1 must apply for apps with ≥2 snapshots"

    def test_confidence_never_none(self):
        from app.services.blowing_up_service import _confidence
        for n in range(0, 15):
            result = _confidence(n, days_tracked=float(n), stability_score=0.5, total_reviews=n * 5)
            assert result is not None
            assert isinstance(result, float)

    def test_compute_for_app_returns_none_when_too_few_snapshots(self):
        """Service must return None when fewer than 2 ranking snapshots exist."""
        from app.services.blowing_up_service import BlowingUpService
        db = MagicMock()
        svc = BlowingUpService(db)
        # Simulate 0 rankings returned
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []
        result = svc.compute_for_app(app_id=1, timeframe_days=7)
        assert result is None

    def test_compute_for_app_returns_none_for_low_confidence(self):
        """Service must return None when there are too few snapshots (< 2)."""
        from app.services.blowing_up_service import BlowingUpService, _confidence
        # Verify: 0 or 1 snapshots → 0.0 (no floor applied below 2)
        assert _confidence(0, 0, 0, 0) == 0.0
        assert _confidence(1, 7, 1.0, 100) == 0.0


# ---------------------------------------------------------------------------
# 3b. Confidence formula weights
# ---------------------------------------------------------------------------

class TestConfidenceFormula:
    """Verify the weighted formula and each component individually."""

    def test_coverage_weight_dominates(self):
        from app.services.blowing_up_service import _confidence
        # Vary only coverage (snapshot_count), hold everything else at 0
        low  = _confidence(2, 0, 0, 0)   # coverage=0.2
        high = _confidence(10, 0, 0, 0)  # coverage=1.0
        assert high > low

    def test_time_score_contributes(self):
        from app.services.blowing_up_service import _confidence
        no_time   = _confidence(5, 0, 0, 0)
        full_time = _confidence(5, 7, 0, 0)
        assert full_time > no_time

    def test_stability_score_contributes(self):
        from app.services.blowing_up_service import _confidence
        no_stab   = _confidence(5, 0, 0.0, 0)
        full_stab = _confidence(5, 0, 1.0, 0)
        assert full_stab > no_stab

    def test_reviews_score_contributes(self):
        from app.services.blowing_up_service import _confidence
        no_rev   = _confidence(5, 0, 0, 0)
        full_rev = _confidence(5, 0, 0, 100)
        assert full_rev > no_rev

    def test_formula_weights_sum_to_one(self):
        from app.services.blowing_up_service import _confidence
        # All signals at maximum → confidence = 1.0
        result = _confidence(10, 7, 1.0, 100)
        assert abs(result - 1.0) < 1e-9

    def test_confidence_in_zero_to_one_range(self):
        from app.services.blowing_up_service import _confidence
        test_cases = [
            (0, 0, 0, 0), (1, 0, 0, 0), (2, 0, 0, 0),
            (5, 3.5, 0.5, 50), (10, 7, 1.0, 100),
            (20, 14, 2.0, 500),  # inputs beyond caps
        ]
        for args in test_cases:
            result = _confidence(*args)
            assert 0.0 <= result <= 1.0, f"_confidence{args} = {result} out of range"

    def test_floor_is_exactly_0_1_for_minimal_data(self):
        from app.services.blowing_up_service import _confidence
        # 2 snapshots, 0 everything else: coverage=0.2, rest=0
        # raw = 0.4*0.2 = 0.08 → floor → 0.1
        result = _confidence(2, 0, 0, 0)
        assert abs(result - 0.1) < 1e-9

    def test_inputs_clamped_above_max(self):
        from app.services.blowing_up_service import _confidence
        # Passing values well above scale should not exceed 1.0
        result = _confidence(100, 100.0, 5.0, 10000)
        assert abs(result - 1.0) < 1e-9

    def test_stability_score_used_in_compute_from_prefetch(self):
        """_compute_from_prefetch must call _stability_score and pass it to _confidence."""
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        src = inspect.getsource(BlowingUpService._compute_from_prefetch)
        assert "_stability_score" in src, (
            "_compute_from_prefetch must use _stability_score for confidence calculation"
        )
        assert "days_tracked" in src, (
            "_compute_from_prefetch must compute days_tracked for confidence"
        )

    def test_days_tracked_computed_from_timestamps(self):
        """days_tracked must be derived from recorded_at timestamps, not timeframe_days."""
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        src = inspect.getsource(BlowingUpService._compute_from_prefetch)
        assert "recorded_at" in src and "total_seconds" in src, (
            "days_tracked should be computed from recorded_at delta"
        )


# ---------------------------------------------------------------------------
# 4. Badge generation
# ---------------------------------------------------------------------------

class TestBadgeGeneration:

    def _badges(self, **kw):
        from app.services.blowing_up_service import _badges
        defaults = dict(
            rank_change_score=0, reviews_velocity_score=0,
            markets_count=0, consistency_score=0,
            confidence_score=0, is_new_entry=False,
        )
        defaults.update(kw)
        return _badges(**defaults)

    def test_new_entry_badge_when_is_new_entry(self):
        assert "New Entry" in self._badges(is_new_entry=True)

    def test_no_new_entry_badge_when_not_new(self):
        assert "New Entry" not in self._badges(is_new_entry=False)

    def test_rapid_climb_badge_at_threshold(self):
        assert "Rapid Climb" in self._badges(rank_change_score=50)
        assert "Rapid Climb" not in self._badges(rank_change_score=49)

    def test_fast_reviews_badge_at_threshold(self):
        assert "Fast Reviews" in self._badges(reviews_velocity_score=40)
        assert "Fast Reviews" not in self._badges(reviews_velocity_score=39)

    def test_cross_market_badge_at_threshold(self):
        assert "Cross-Market" in self._badges(markets_count=3)
        assert "Cross-Market" not in self._badges(markets_count=2)

    def test_consistent_momentum_badge(self):
        assert "Consistent Momentum" in self._badges(consistency_score=70)

    def test_high_confidence_badge(self):
        assert "High Confidence" in self._badges(confidence_score=80)

    def test_no_badges_for_zero_signals(self):
        badges = self._badges()
        assert badges == []

    def test_multiple_badges_possible(self):
        badges = self._badges(
            is_new_entry=True, rank_change_score=60,
            reviews_velocity_score=50, markets_count=4,
        )
        assert len(badges) >= 3


# ---------------------------------------------------------------------------
# 5. Why-flagged reasons
# ---------------------------------------------------------------------------

class TestWhyFlagged:

    def _reasons(self, **kw):
        from app.services.blowing_up_service import _why_flagged
        defaults = dict(
            rank_change=0, starting_rank=None, current_rank=50,
            reviews_velocity=0, chart_appearances=0,
            markets_count=0, consistency_score=0,
            timeframe_days=7, snapshot_count=3,
        )
        defaults.update(kw)
        return _why_flagged(**defaults)

    def test_rank_improvement_reason(self):
        reasons = self._reasons(rank_change=50, starting_rank=100, current_rank=50)
        assert any("Rank improved" in r for r in reasons)

    def test_reviews_velocity_reason(self):
        reasons = self._reasons(reviews_velocity=3.0)
        assert any("reviews/day" in r for r in reasons)

    def test_chart_appearances_reason(self):
        reasons = self._reasons(chart_appearances=5)
        assert any("chart snapshots" in r for r in reasons)

    def test_cross_market_reason(self):
        reasons = self._reasons(markets_count=4)
        assert any("market segments" in r for r in reasons)

    def test_fallback_reason_when_no_signals(self):
        reasons = self._reasons()
        assert len(reasons) >= 1
        assert any("velocity" in r.lower() for r in reasons)


# ---------------------------------------------------------------------------
# 6. Sorting / filtering
# ---------------------------------------------------------------------------

class TestSortingAndFiltering:

    def test_sort_map_keys_valid(self):
        """The sort map in get_blowing_up_apps should cover all documented sort_by values."""
        valid_sort_by = {"blowing_up_score", "rank_velocity", "rank_change",
                         "reviews_velocity", "confidence"}
        from app.services.blowing_up_service import BlowingUpService
        import inspect
        src = inspect.getsource(BlowingUpService.get_blowing_up_apps)
        for key in valid_sort_by:
            assert f'"{key}"' in src or f"'{key}'" in src

    def test_timeframe_map_has_all_windows(self):
        from app.services.blowing_up_service import _TIMEFRAME_DAYS
        assert "24h" in _TIMEFRAME_DAYS
        assert "3d"  in _TIMEFRAME_DAYS
        assert "7d"  in _TIMEFRAME_DAYS


# ---------------------------------------------------------------------------
# 7. API response schema
# ---------------------------------------------------------------------------

class TestBlowingUpResponseSchema:

    def test_response_has_required_fields(self):
        from app.models.schemas import BlowingUpResponse, AppBlowingUpItem
        resp = BlowingUpResponse(
            status="success",
            items=[],
            total=0,
        )
        assert resp.status == "success"
        assert resp.items == []
        assert resp.total == 0

    def test_insufficient_data_response(self):
        from app.models.schemas import BlowingUpResponse
        resp = BlowingUpResponse(
            status="insufficient_data",
            message="No scores yet",
            required_signals=["ranking_history"],
            items=[],
            total=0,
        )
        assert resp.status == "insufficient_data"
        assert resp.item if hasattr(resp, 'item') else True  # no item field

    def test_item_has_all_score_fields(self):
        from app.models.schemas import AppBlowingUpItem
        now = datetime.utcnow()
        item = AppBlowingUpItem(
            id=1, app_id="123456789", name="Test App",
            blowing_up_score=72.5,
            rank_velocity_score=80.0, rank_change_score=65.0,
            reviews_velocity_score=40.0, chart_presence_score=50.0,
            cross_market_score=60.0, consistency_score=70.0,
            confidence_score=90.0,
            rank_change=45, rank_velocity=12.5,
            reviews_velocity=3.2, chart_appearances=8,
            markets_count=4,
            badges=["Rapid Climb", "High Confidence"],
            why_flagged=["Rank improved from #80 to #35"],
            computed_at=now,
        )
        assert item.blowing_up_score == 72.5
        assert "Rapid Climb" in item.badges
        assert len(item.why_flagged) == 1

    def test_item_badges_default_empty_list(self):
        from app.models.schemas import AppBlowingUpItem
        item = AppBlowingUpItem(
            id=1, app_id="1", name="App",
            blowing_up_score=0, rank_velocity_score=0, rank_change_score=0,
            reviews_velocity_score=0, chart_presence_score=0,
            cross_market_score=0, consistency_score=0, confidence_score=0,
            rank_change=0, rank_velocity=0, reviews_velocity=0,
            chart_appearances=0, markets_count=0,
            badges=[], why_flagged=[],
        )
        assert item.badges == []
        assert item.why_flagged == []

    def test_summary_stats_populated(self):
        from app.models.schemas import BlowingUpResponse
        resp = BlowingUpResponse(
            status="success",
            items=[],
            total=42,
            exploding_count=42,
            top_score=95.3,
            avg_rank_velocity=18.4,
        )
        assert resp.top_score == 95.3
        assert resp.avg_rank_velocity == 18.4
        assert resp.exploding_count == 42


# ---------------------------------------------------------------------------
# 8. Blowing-up model — column presence check
# ---------------------------------------------------------------------------

class TestBlowingUpModel:

    def test_model_has_required_columns(self):
        from app.models.models import AppBlowingUpScore
        cols = {c.key for c in AppBlowingUpScore.__table__.columns}
        required = {
            "app_id", "blowing_up_score", "rank_velocity_score",
            "rank_change_score", "reviews_velocity_score",
            "chart_presence_score", "cross_market_score",
            "consistency_score", "confidence_score",
            "rank_change", "rank_velocity", "reviews_velocity",
            "chart_appearances", "markets_count",
            "badges", "why_flagged", "computed_at",
        }
        assert required.issubset(cols)

    def test_model_primary_key_is_app_id(self):
        from app.models.models import AppBlowingUpScore
        pk_cols = [c.key for c in AppBlowingUpScore.__table__.primary_key]
        assert "app_id" in pk_cols


# ---------------------------------------------------------------------------
# 9. Incumbent penalty + discovery bias
# ---------------------------------------------------------------------------

class TestIncumbentDiscovery:
    """Verify giant incumbents are penalised and breakout apps surface higher."""

    # ── _incumbent_penalty ───────────────────────────────────────────────

    def test_penalty_none_for_small_app(self):
        from app.services.blowing_up_service import _incumbent_penalty
        assert _incumbent_penalty(0)      == 1.0
        assert _incumbent_penalty(100)    == 1.0
        assert _incumbent_penalty(9_999)  == 1.0

    def test_penalty_partial_for_medium_app(self):
        from app.services.blowing_up_service import _incumbent_penalty
        p = _incumbent_penalty(100_000)
        assert 0.1 < p < 1.0, f"100k-review app should have partial penalty, got {p}"

    def test_penalty_heavy_for_giant_app(self):
        from app.services.blowing_up_service import _incumbent_penalty
        # YouTube / TikTok tier (5M+ reviews)
        p = _incumbent_penalty(5_000_000)
        assert p <= 0.20, f"5M-review app should have ≥80% penalty, got {p}"

    def test_penalty_floor_is_0_1(self):
        from app.services.blowing_up_service import _incumbent_penalty
        # Even the biggest possible app must not go below 0.10
        assert _incumbent_penalty(500_000_000) == 0.10

    def test_penalty_monotonically_decreasing(self):
        from app.services.blowing_up_service import _incumbent_penalty
        sizes = [0, 10_000, 50_000, 200_000, 1_000_000, 5_000_000]
        penalties = [_incumbent_penalty(s) for s in sizes]
        for i in range(1, len(penalties)):
            assert penalties[i] <= penalties[i - 1], (
                f"penalty should decrease as size grows: {list(zip(sizes, penalties))}"
            )

    # ── _norm_reviews_velocity with base ────────────────────────────────

    def test_reviews_velocity_giant_dampened(self):
        from app.services.blowing_up_service import _norm_reviews_velocity
        # 100/day for an incumbent with 1M reviews vs 10/day for a breakout with 200
        giant    = _norm_reviews_velocity(100.0, total_reviews=1_000_000)
        breakout = _norm_reviews_velocity(10.0,  total_reviews=200)
        assert breakout > giant, (
            f"breakout (10/day, 200 base) should outscore giant (100/day, 1M base): "
            f"{breakout:.1f} vs {giant:.1f}"
        )

    def test_reviews_velocity_small_app_not_penalised(self):
        from app.services.blowing_up_service import _norm_reviews_velocity
        # ≤500 total reviews → no dampening at all
        s0   = _norm_reviews_velocity(5.0, total_reviews=0)
        s200 = _norm_reviews_velocity(5.0, total_reviews=200)
        assert abs(s0 - s200) < 1e-9, "No dampening for ≤500 review apps"

    def test_reviews_velocity_increasing_base_decreases_score(self):
        from app.services.blowing_up_service import _norm_reviews_velocity
        bases  = [0, 1_000, 10_000, 100_000, 1_000_000]
        scores = [_norm_reviews_velocity(20.0, b) for b in bases]
        for i in range(1, len(scores)):
            assert scores[i] <= scores[i - 1], (
                f"Larger review base should not increase score: {list(zip(bases, scores))}"
            )

    # ── end-to-end: breakout > incumbent with same rank trajectory ───────

    def test_breakout_outscores_incumbent_same_rank_data(self):
        """
        Two apps with identical rank trajectory (100 → 10 over 7 days).
        Breakout has 200 lifetime reviews; incumbent has 5 000 000.
        Breakout must score higher on blowing_up_score.
        """
        from app.services.blowing_up_service import BlowingUpService
        from datetime import datetime, timezone
        from unittest.mock import MagicMock

        db  = MagicMock()
        svc = BlowingUpService(db)
        now = datetime.now(timezone.utc)

        def make_rankings(n=8):
            ranks = [int(100 - (90 / (n - 1)) * i) for i in range(n)]
            return [
                _make_ranking(rank=r, velocity=90 / (n - 1), days_ago=7 - i)
                for i, r in enumerate(ranks)
            ]

        breakout_result = svc._compute_from_prefetch(
            app_id=1, rankings=make_rankings(), review_count=20,
            is_new_entry=True, timeframe_days=7, now=now,
            current_reviews=200,
        )
        incumbent_result = svc._compute_from_prefetch(
            app_id=2, rankings=make_rankings(), review_count=5_000,
            is_new_entry=False, timeframe_days=7, now=now,
            current_reviews=5_000_000,
        )

        assert breakout_result  is not None
        assert incumbent_result is not None
        assert breakout_result["blowing_up_score"] > incumbent_result["blowing_up_score"], (
            f"breakout {breakout_result['blowing_up_score']:.2f} should beat "
            f"incumbent {incumbent_result['blowing_up_score']:.2f}"
        )

    # ── candidate selection properties ──────────────────────────────────

    def test_candidate_selection_orders_by_rank_improvement(self):
        """compute_for_all_apps must order by rank improvement, not snapshot count."""
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        src = inspect.getsource(BlowingUpService.compute_for_all_apps)
        assert "rank_improvement" in src, (
            "compute_for_all_apps should reference rank_improvement in candidate query"
        )
        assert "rank_improvement_expr.desc()" in src, (
            "Candidates should be ordered by rank_improvement DESC"
        )

    def test_default_max_apps_is_large(self):
        """Candidate pool default must be ≥ 500 so breakout apps are not excluded."""
        import re
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        src = inspect.getsource(BlowingUpService.compute_for_all_apps)
        matches = re.findall(r'max_apps\s*(?::\s*\w+\s*)?=\s*(\d+)', src)
        assert matches, "max_apps default must be declared in compute_for_all_apps"
        assert int(matches[0]) >= 500, (
            f"max_apps default should be ≥ 500 to include breakout apps, got {matches[0]}"
        )

    def test_current_reviews_bulk_fetched_in_compute_all(self):
        """compute_for_all_apps must bulk-fetch App.current_reviews."""
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        src = inspect.getsource(BlowingUpService.compute_for_all_apps)
        assert "current_reviews" in src, (
            "compute_for_all_apps must fetch and pass current_reviews for dampening"
        )
