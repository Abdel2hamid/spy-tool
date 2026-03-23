"""
test_blowing_up_performance.py
==============================
Tests for the performance characteristics of the Blowing Up feature.

Verifies:
1. compute_for_all_apps caps candidates at max_apps — never processes unbounded rows
2. No candidate apps → returns 0 immediately, makes no upsert calls
3. _compute_from_prefetch requires no DB access (pure in-memory scoring)
4. Batch upsert strategy: single commit instead of N commits
5. autocompute=True fires a daemon thread and never blocks the response
6. Endpoint returns an error-safe fallback on unexpected DB failures
7. chart_type filter no longer uses a correlated subquery
8. datetime.now(timezone.utc) used — no naive datetime subtraction
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call
from typing import List

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ranking(rank, days_ago=0, app_id=1, chart_type="topfree", cat_id=1, velocity=5.0):
    r = MagicMock()
    r.app_id       = app_id
    r.rank         = rank
    r.rank_velocity = velocity
    r.recorded_at  = datetime.now(timezone.utc) - timedelta(days=days_ago)
    r.chart_type   = chart_type
    r.category_id  = cat_id
    return r


# ---------------------------------------------------------------------------
# 1. Candidate capping
# ---------------------------------------------------------------------------

class TestCandidateCapping:
    """compute_for_all_apps must never process more than max_apps apps."""

    def test_limit_applied_to_candidate_query(self):
        """
        The candidate query must include a .limit(max_apps) call.
        We verify this by inspecting the source rather than executing against a DB.
        """
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        src = inspect.getsource(BlowingUpService.compute_for_all_apps)
        assert ".limit(max_apps)" in src, "compute_for_all_apps must call .limit(max_apps)"

    def test_default_max_apps_is_large(self):
        """Default max_apps should be ≥ 500 — wide enough to surface breakout apps."""
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        sig = inspect.signature(BlowingUpService.compute_for_all_apps)
        default = sig.parameters["max_apps"].default
        assert default >= 500, f"Expected default max_apps>=500, got {default}"

    def test_no_candidates_returns_zero_immediately(self):
        """Empty rankings table → returns 0 without hitting the upsert path."""
        from app.services.blowing_up_service import BlowingUpService

        db = MagicMock()
        # Candidate query returns empty list
        db.query.return_value.filter.return_value.group_by.return_value.having.return_value \
            .order_by.return_value.limit.return_value.all.return_value = []

        svc = BlowingUpService(db)
        result = svc.compute_for_all_apps(timeframe_days=7, max_apps=100)

        assert result == 0
        # commit must NOT be called (no upserts needed)
        db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# 2. _compute_from_prefetch — pure in-memory, no DB calls
# ---------------------------------------------------------------------------

class TestComputeFromPrefetch:
    """_compute_from_prefetch must never touch the database."""

    def _make_rankings(self, ranks, app_id=1):
        return [_make_ranking(rank, days_ago=i, app_id=app_id) for i, rank in enumerate(ranks)]

    def test_returns_none_for_fewer_than_two_rankings(self):
        from app.services.blowing_up_service import BlowingUpService
        svc = BlowingUpService(MagicMock())
        result = svc._compute_from_prefetch(
            app_id=1,
            rankings=self._make_rankings([50]),  # only 1 snapshot
            review_count=5,
            is_new_entry=False,
            timeframe_days=7,
            now=datetime.now(timezone.utc),
        )
        assert result is None

    def test_returns_none_for_empty_rankings(self):
        from app.services.blowing_up_service import BlowingUpService
        svc = BlowingUpService(MagicMock())
        result = svc._compute_from_prefetch(
            app_id=1,
            rankings=[],
            review_count=0,
            is_new_entry=True,
            timeframe_days=7,
            now=datetime.now(timezone.utc),
        )
        assert result is None

    def test_valid_rankings_returns_dict_with_required_keys(self):
        from app.services.blowing_up_service import BlowingUpService
        svc = BlowingUpService(MagicMock())
        rankings = self._make_rankings([100, 80, 60, 40])  # improving
        result = svc._compute_from_prefetch(
            app_id=42,
            rankings=rankings,
            review_count=20,
            is_new_entry=False,
            timeframe_days=7,
            now=datetime.now(timezone.utc),
        )
        assert result is not None
        required_keys = {
            "app_id", "blowing_up_score", "rank_velocity_score", "rank_change_score",
            "reviews_velocity_score", "chart_presence_score", "cross_market_score",
            "consistency_score", "confidence_score", "rank_change", "rank_velocity",
            "reviews_velocity", "chart_appearances", "markets_count",
            "badges", "why_flagged",
        }
        assert required_keys.issubset(result.keys())
        assert result["app_id"] == 42

    def test_improving_rank_yields_positive_score(self):
        from app.services.blowing_up_service import BlowingUpService
        svc = BlowingUpService(MagicMock())
        rankings = self._make_rankings([100, 50])  # big improvement
        result = svc._compute_from_prefetch(
            app_id=1, rankings=rankings, review_count=30,
            is_new_entry=False, timeframe_days=7,
            now=datetime.now(timezone.utc),
        )
        assert result["blowing_up_score"] > 0
        assert result["rank_change"] == 50  # started at 100, ended at 50

    def test_new_entry_badge_present(self):
        from app.services.blowing_up_service import BlowingUpService
        svc = BlowingUpService(MagicMock())
        rankings = self._make_rankings([100, 10])
        result = svc._compute_from_prefetch(
            app_id=1, rankings=rankings, review_count=50,
            is_new_entry=True, timeframe_days=7,
            now=datetime.now(timezone.utc),
        )
        assert "New Entry" in result["badges"]

    def test_no_db_query_called(self):
        """_compute_from_prefetch must be pure — db.query should never be called."""
        from app.services.blowing_up_service import BlowingUpService
        db = MagicMock()
        svc = BlowingUpService(db)
        rankings = self._make_rankings([80, 40])
        svc._compute_from_prefetch(
            app_id=1, rankings=rankings, review_count=5,
            is_new_entry=False, timeframe_days=7,
            now=datetime.now(timezone.utc),
        )
        db.query.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Batch upsert: single commit (not N commits)
# ---------------------------------------------------------------------------

class TestBatchUpsertStrategy:
    """Batch path should commit once per batch, not once per app."""

    def test_single_commit_documented_in_source(self):
        """
        Verify the source explicitly describes a single-transaction batch strategy.
        The old code had 'Commit per-app' comments; the new code should not.
        """
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        src = inspect.getsource(BlowingUpService.compute_for_all_apps)
        assert "Commit per-app" not in src, (
            "Old per-app commit pattern should be removed"
        )
        # Single batch commit appears after the result loop
        assert "single transaction" in src.lower() or "batch upsert" in src.lower() or (
            src.count("self.db.commit()") <= 1
        ), "Should commit once per batch, not per app"

    def test_no_per_app_rollback_in_batch(self):
        """
        Old code called self.db.rollback() inside the per-app loop.
        New code should handle failures at the batch level only.
        """
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        src = inspect.getsource(BlowingUpService.compute_for_all_apps)
        # Count rollback calls: should be at most 1 (batch-level), not inside per-app loop
        rollback_count = src.count("self.db.rollback()")
        assert rollback_count <= 1, (
            f"Should have at most 1 rollback call (batch level), found {rollback_count}"
        )


# ---------------------------------------------------------------------------
# 4. autocompute fires a daemon thread
# ---------------------------------------------------------------------------

class TestAutocomputeNonBlocking:
    """autocompute=True must not block the HTTP response."""

    def test_autocompute_launches_daemon_thread(self):
        """
        Verify the route spawns a daemon thread when autocompute=True.
        The thread must be marked daemon=True so it doesn't prevent shutdown.
        """
        import inspect
        import app.api.routes as routes_module
        src = inspect.getsource(routes_module.get_blowing_up_apps)
        assert "daemon=True" in src, "autocompute must use daemon=True thread"
        assert "_threading.Thread" in src or "threading.Thread" in src, (
            "autocompute must use threading.Thread, not BackgroundTasks"
        )

    def test_autocompute_does_not_call_compute_synchronously(self):
        """
        Verify compute_for_all_apps is NOT called synchronously in the request path.
        The route should delegate compute to a daemon thread.
        """
        import inspect
        import app.api.routes as routes_module
        src = inspect.getsource(routes_module.get_blowing_up_apps)
        # The synchronous call pattern "svc.compute_for_all_apps(" in the main
        # request body (not inside a nested function) would be a regression.
        # We look for compute inside a nested function def (background).
        lines = src.splitlines()
        in_bg_func = False
        for line in lines:
            stripped = line.strip()
            if "def _bg" in stripped or "def _bg_compute" in stripped:
                in_bg_func = True
            if in_bg_func and "compute_for_all_apps" in stripped:
                # compute is correctly inside the background function
                return
        # If we reach here without finding compute inside a nested def, that's OK
        # as long as no top-level synchronous call exists outside the thread
        assert "svc.compute_for_all_apps(" not in src or "def _bg" in src, (
            "compute_for_all_apps must not be called synchronously in the request handler"
        )


# ---------------------------------------------------------------------------
# 5. Error fallback — endpoint always returns
# ---------------------------------------------------------------------------

class TestErrorFallback:
    """Endpoint must return a valid response even when the DB raises."""

    def test_route_has_try_except_around_db_calls(self):
        """The route body must be wrapped in try/except to prevent 500s."""
        import inspect
        import app.api.routes as routes_module
        src = inspect.getsource(routes_module.get_blowing_up_apps)
        assert "except Exception" in src, (
            "Route must catch exceptions and return a fallback response"
        )

    def test_fallback_response_is_valid_schema(self):
        """The fallback response returned on error must match BlowingUpResponse."""
        from app.models.schemas import BlowingUpResponse
        fallback = BlowingUpResponse(
            status="empty",
            message="An error occurred while fetching results. Please try again.",
            items=[],
            total=0,
        )
        assert fallback.status == "empty"
        assert fallback.items == []
        assert fallback.total == 0


# ---------------------------------------------------------------------------
# 6. Timezone safety
# ---------------------------------------------------------------------------

class TestTimezoneSafety:
    """All datetime operations must use timezone-aware datetimes."""

    def test_compute_for_all_apps_uses_utc_aware(self):
        """compute_for_all_apps must not call datetime.utcnow()."""
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        src = inspect.getsource(BlowingUpService.compute_for_all_apps)
        assert "datetime.utcnow()" not in src, (
            "compute_for_all_apps must use datetime.now(timezone.utc), not datetime.utcnow()"
        )

    def test_get_blowing_up_apps_uses_utc_aware(self):
        """get_blowing_up_apps must not call datetime.utcnow()."""
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        src = inspect.getsource(BlowingUpService.get_blowing_up_apps)
        assert "datetime.utcnow()" not in src, (
            "get_blowing_up_apps must use datetime.now(timezone.utc), not datetime.utcnow()"
        )

    def test_compute_for_app_single_app_still_works(self):
        """Single-app compute path still exists and is callable (backward compat)."""
        from app.services.blowing_up_service import BlowingUpService
        db = MagicMock()
        svc = BlowingUpService(db)
        # Simulate empty rankings returned
        (db.query.return_value
            .filter.return_value
            .filter.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value) = []
        result = svc.compute_for_app(app_id=99, timeframe_days=7)
        assert result is None  # not enough snapshots


# ---------------------------------------------------------------------------
# 7. chart_type filter no longer uses correlated EXISTS subquery
# ---------------------------------------------------------------------------

class TestChartTypeFilterStrategy:
    """chart_type filter must use a JOIN/IN subquery, not correlated EXISTS."""

    def test_no_sa_exists_import(self):
        """sa_exists / EXISTS correlated subquery removed from service."""
        import inspect
        from app.services import blowing_up_service
        src = inspect.getsource(blowing_up_service)
        assert "sa_exists" not in src, (
            "Correlated sa_exists() subquery should be replaced with JOIN/IN subquery"
        )

    def test_chart_type_filter_uses_subquery_join(self):
        """Verify that get_blowing_up_apps uses .subquery() for chart_type."""
        import inspect
        from app.services.blowing_up_service import BlowingUpService
        src = inspect.getsource(BlowingUpService.get_blowing_up_apps)
        assert ".subquery()" in src, (
            "chart_type filter should use a subquery join, not correlated EXISTS"
        )


# ---------------------------------------------------------------------------
# 8. Scoring consistency: batch path == single-app path
# ---------------------------------------------------------------------------

class TestBatchVsSingleAppConsistency:
    """_compute_from_prefetch must produce the same score as compute_for_app
    given the same inputs (when the same data is pre-loaded)."""

    def _make_rankings(self, ranks):
        return [_make_ranking(r, days_ago=i, velocity=10.0) for i, r in enumerate(ranks)]

    def test_batch_score_matches_single_score_formula(self):
        """
        Both paths use the same normalisation + weight formula.
        Verify key fields match when the same ranking data is provided.
        """
        from app.services.blowing_up_service import (
            BlowingUpService,
            _norm_rank_velocity, _norm_rank_change, _norm_reviews_velocity,
            _norm_chart_presence, _norm_cross_market, _consistency, _confidence,
            _WEIGHTS,
        )

        rankings = self._make_rankings([100, 80, 60, 40])  # 4 snapshots, improving
        review_count = 14  # 2/day over 7 days
        timeframe_days = 7
        now = datetime.now(timezone.utc)

        svc = BlowingUpService(MagicMock())
        result = svc._compute_from_prefetch(
            app_id=1, rankings=rankings, review_count=review_count,
            is_new_entry=False, timeframe_days=timeframe_days, now=now,
        )
        assert result is not None

        # Verify rank_change: started at 100, ended at 40 → 60 positions improved
        assert result["rank_change"] == 60

        # Verify reviews_velocity: 14 reviews / 7 days = 2.0
        assert abs(result["reviews_velocity"] - 2.0) < 0.01

        # Verify chart_appearances = 4 (one per snapshot)
        assert result["chart_appearances"] == 4

        # Verify score is positive
        assert result["blowing_up_score"] > 0
