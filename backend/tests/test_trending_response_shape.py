"""
test_trending_response_shape.py
================================
Tests for:
1. /trending response schema — always returns { status, items } (never a bare array)
2. _read_precomputed_trending helper — returns [] when table is empty, list of dicts
   when rows exist
3. Frontend unwrapping contract — verifies items is always extractable via response["items"]
4. Missing / null field fallback safety
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# 1. Response schema — shape is always { status, items }
# ---------------------------------------------------------------------------

class TestTrendingResponseSchema:
    """TrendingAppsResponse must always expose status + items."""

    def test_success_response_has_items_list(self):
        from app.models.schemas import TrendingAppsResponse, TrendingAppV2Response
        item = TrendingAppV2Response(
            id=1, app_id="123456789", name="Test App",
            trend_score=55.0, momentum_3d=2.1, momentum_7d=1.8,
            consistency_score=60.0, confidence_factor=0.9,
            absolute_rank_bonus=10.0, review_momentum=3.5,
        )
        response = TrendingAppsResponse(status="success", items=[item])
        assert response.status == "success"
        assert isinstance(response.items, list)
        assert len(response.items) == 1
        assert response.items[0].trend_score == 55.0

    def test_empty_state_response_items_is_empty_list(self):
        from app.models.schemas import TrendingAppsResponse
        response = TrendingAppsResponse(
            status="empty",
            message="No apps in database.",
            required_signals=["apps"],
            items=[],
        )
        assert response.status == "empty"
        assert response.items == []

    def test_insufficient_data_response_items_is_empty_list(self):
        from app.models.schemas import TrendingAppsResponse
        response = TrendingAppsResponse(
            status="insufficient_data",
            message="No ranking history yet.",
            required_signals=["ranking_history"],
            items=[],
        )
        assert response.status == "insufficient_data"
        assert isinstance(response.items, list)

    def test_response_is_never_a_bare_array(self):
        """The schema must be a dict-like object, not a list."""
        from app.models.schemas import TrendingAppsResponse
        response = TrendingAppsResponse(status="success", items=[])
        d = response.model_dump()
        assert isinstance(d, dict)
        assert "items" in d
        assert "status" in d
        assert not isinstance(d, list)

    def test_items_always_present_when_status_success(self):
        from app.models.schemas import TrendingAppsResponse
        response = TrendingAppsResponse(status="success", items=[])
        assert hasattr(response, "items")
        assert response.items is not None


# ---------------------------------------------------------------------------
# 2. _read_precomputed_trending — helper returns [] when table empty
# ---------------------------------------------------------------------------

class TestReadPrecomputedTrending:
    """Unit-tests for the routes helper that reads from app_trending_scores."""

    def _make_db_empty(self):
        """Return a mock DB where app_trending_scores has no rows."""
        db = MagicMock()
        query_mock = MagicMock()
        query_mock.join.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = []
        db.query.return_value = query_mock
        return db

    def _make_db_with_rows(self, n: int = 2):
        """Return a mock DB with n trending score rows."""
        db = MagicMock()
        query_mock = MagicMock()
        query_mock.join.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock

        rows = []
        for i in range(n):
            score = MagicMock()
            score.trend_score = float(80 - i * 10)
            score.momentum_3d = 2.0
            score.momentum_7d = 1.5
            score.consistency_score = 55.0
            score.confidence_factor = 0.85
            score.absolute_rank_bonus = 8.0
            score.review_momentum = 3.0

            app = MagicMock()
            app.id = i + 1
            app.app_id = f"10000000{i}"
            app.name = f"App {i}"
            app.developer = "Dev"
            app.icon_url = None
            app.current_rank = 10 + i
            app.current_rating = 4.5
            app.current_reviews = 1000 + i * 100

            rows.append((score, app))

        query_mock.all.return_value = rows
        db.query.return_value = query_mock
        return db

    def test_empty_table_returns_empty_list(self):
        from app.api.routes import _read_precomputed_trending
        db = self._make_db_empty()
        result = _read_precomputed_trending(db, limit=10, category_id=None)
        assert result == []

    def test_rows_mapped_to_correct_fields(self):
        from app.api.routes import _read_precomputed_trending
        db = self._make_db_with_rows(2)
        result = _read_precomputed_trending(db, limit=10, category_id=None)
        assert len(result) == 2
        first = result[0]
        # All required TrendingAppV2Response fields must be present
        for field in (
            "id", "app_id", "name", "developer", "icon_url",
            "current_rank", "current_rating", "current_reviews",
            "trend_score", "momentum_3d", "momentum_7d",
            "consistency_score", "confidence_factor",
            "absolute_rank_bonus", "review_momentum",
        ):
            assert field in first, f"Missing field: {field}"

    def test_trend_score_preserved(self):
        from app.api.routes import _read_precomputed_trending
        db = self._make_db_with_rows(2)
        result = _read_precomputed_trending(db, limit=10, category_id=None)
        assert result[0]["trend_score"] == 80.0
        assert result[1]["trend_score"] == 70.0

    def test_limit_is_applied(self):
        from app.api.routes import _read_precomputed_trending
        db = self._make_db_with_rows(5)
        # The mock ignores limit but we verify the call chain includes limit()
        _read_precomputed_trending(db, limit=3, category_id=None)
        # query chain: query().join().filter().order_by().limit(3).all()
        q = db.query.return_value
        q.join.return_value.filter.return_value.order_by.return_value.limit.assert_called_with(3)


# ---------------------------------------------------------------------------
# 3. Frontend unwrapping contract (Python equivalent of the TS fix)
# ---------------------------------------------------------------------------

class TestFrontendUnwrappingLogic:
    """
    Simulate the getTrendingApps() unwrapping logic that was added to api.ts.
    These tests mirror the four cases the fix must handle.
    """

    @staticmethod
    def simulate_get_trending_apps(raw_response):
        """
        Python mirror of the fixed getTrendingApps() in api.ts:
          if Array.isArray(response) return response
          return response?.items ?? []
        """
        if isinstance(raw_response, list):
            return raw_response
        if isinstance(raw_response, dict):
            return raw_response.get("items") or []
        return []

    def test_valid_wrapped_response_extracts_items(self):
        raw = {"status": "success", "items": [{"id": 1, "name": "App"}]}
        result = self.simulate_get_trending_apps(raw)
        assert result == [{"id": 1, "name": "App"}]

    def test_empty_items_returns_empty_list(self):
        raw = {"status": "empty", "items": [], "message": "No apps"}
        result = self.simulate_get_trending_apps(raw)
        assert result == []

    def test_missing_items_key_returns_empty_list(self):
        """Handles a response that has no 'items' key at all."""
        raw = {"status": "error"}
        result = self.simulate_get_trending_apps(raw)
        assert result == []

    def test_legacy_bare_array_still_works(self):
        """Backward compat: if the endpoint ever returned a plain list, it still works."""
        raw = [{"id": 1}, {"id": 2}]
        result = self.simulate_get_trending_apps(raw)
        assert len(result) == 2

    def test_none_response_returns_empty_list(self):
        result = self.simulate_get_trending_apps(None)
        assert result == []

    def test_items_none_returns_empty_list(self):
        """items: null in JSON should not crash."""
        raw = {"status": "success", "items": None}
        result = self.simulate_get_trending_apps(raw)
        assert result == []
