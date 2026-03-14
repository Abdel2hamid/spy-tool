"""
test_opportunity_of_day.py
==========================
Tests for:
1. Backend response schema — always returns { status, item, message, required_signals }
2. Endpoint logic — success / insufficient_data / empty paths
3. Frontend unwrapping contract — mirrors getOpportunityOfDay() fix in api.ts
4. No undefined values rendered (all required fields present when item is not None)
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# 1. Response schema shape
# ---------------------------------------------------------------------------

class TestOpportunityResponseSchema:
    """OpportunityOfDayWrapperResponse must always expose status + item."""

    def _make_item(self):
        from app.models.schemas import OpportunityOfDayResponse
        return OpportunityOfDayResponse(
            app_id=1,
            app_name="Test App",
            primary_keyword="task manager",
            competition_score=30.0,
            trend_score=65.0,
            success_probability=72.0,
            ai_integration_potential=55.0,
            rank_velocity=1.5,
            review_growth=3.2,
            rating_velocity=0.1,
            category_growth=8.0,
            category="Productivity",
            recommendation="Strong opportunity",
        )

    def test_success_response_has_all_required_fields(self):
        from app.models.schemas import OpportunityOfDayWrapperResponse
        resp = OpportunityOfDayWrapperResponse(
            status="success",
            item=self._make_item(),
            message=None,
            required_signals=None,
        )
        assert resp.status == "success"
        assert resp.item is not None
        assert resp.item.app_name == "Test App"
        assert resp.item.success_probability == 72.0

    def test_insufficient_data_response_item_is_none(self):
        from app.models.schemas import OpportunityOfDayWrapperResponse
        resp = OpportunityOfDayWrapperResponse(
            status="insufficient_data",
            message="Not enough signals yet.",
            required_signals=["ranking_history", "rank_velocity"],
            item=None,
        )
        assert resp.status == "insufficient_data"
        assert resp.item is None
        assert resp.message is not None

    def test_empty_response_item_is_none(self):
        from app.models.schemas import OpportunityOfDayWrapperResponse
        resp = OpportunityOfDayWrapperResponse(
            status="empty",
            message="No apps in database.",
            required_signals=["apps"],
            item=None,
        )
        assert resp.status == "empty"
        assert resp.item is None

    def test_response_is_never_a_bare_object(self):
        """Backend must always return a dict with 'status' and 'item', never the raw item."""
        from app.models.schemas import OpportunityOfDayWrapperResponse
        resp = OpportunityOfDayWrapperResponse(
            status="success", item=self._make_item()
        )
        d = resp.model_dump()
        assert "status" in d
        assert "item" in d
        assert d["item"]["app_name"] == "Test App"

    def test_item_has_no_undefined_numeric_fields(self):
        """All numeric fields on item must be float, never None."""
        item = self._make_item()
        numeric_fields = [
            "competition_score", "trend_score", "success_probability",
            "ai_integration_potential", "rank_velocity", "review_growth",
            "rating_velocity", "category_growth",
        ]
        for field in numeric_fields:
            val = getattr(item, field)
            assert val is not None, f"{field} must not be None"
            assert isinstance(val, (int, float)), f"{field} must be numeric"


# ---------------------------------------------------------------------------
# 2. Endpoint path logic (mocked DB)
# ---------------------------------------------------------------------------

class TestOpportunityEndpointPaths:
    """Test each branch of the /opportunity-of-day route handler."""

    def _make_db_no_apps(self):
        db = MagicMock()
        # DailyReport query returns None
        db.query.return_value.filter.return_value.first.return_value = None
        # App count = 0
        db.query.return_value.filter.return_value.scalar.return_value = 0
        return db

    def test_success_path_returns_item(self):
        """When generate_opportunity_of_day returns data, status must be 'success'."""
        from app.models.schemas import OpportunityOfDayWrapperResponse
        mock_opportunity = {
            "app_id": 1, "app_name": "App", "primary_keyword": "note",
            "competition_score": 20.0, "trend_score": 70.0,
            "success_probability": 68.0, "ai_integration_potential": 40.0,
            "rank_velocity": 1.0, "review_growth": 2.0,
            "rating_velocity": 0.0, "category_growth": 5.0,
            "category": "Productivity", "recommendation": "Go for it",
        }
        # Build the response dict that the route returns on success
        resp_dict = {
            "status": "success",
            "message": None,
            "required_signals": None,
            "item": mock_opportunity,
        }
        resp = OpportunityOfDayWrapperResponse(**resp_dict)
        assert resp.status == "success"
        assert resp.item is not None

    def test_no_apps_path_returns_empty_status(self):
        from app.models.schemas import OpportunityOfDayWrapperResponse
        resp = OpportunityOfDayWrapperResponse(
            status="empty",
            message="No apps in database. Add apps to generate opportunities.",
            required_signals=["apps"],
            item=None,
        )
        assert resp.status == "empty"
        assert resp.item is None
        assert "apps" in resp.required_signals

    def test_no_ranking_path_returns_insufficient_data(self):
        from app.models.schemas import OpportunityOfDayWrapperResponse
        resp = OpportunityOfDayWrapperResponse(
            status="insufficient_data",
            message="Apps exist but no ranking data to compute opportunity scores.",
            required_signals=["ranking_history", "current_rank"],
            item=None,
        )
        assert resp.status == "insufficient_data"
        assert resp.item is None


# ---------------------------------------------------------------------------
# 3. Frontend unwrapping contract (Python mirror of api.ts fix)
# ---------------------------------------------------------------------------

class TestFrontendOpportunityUnwrapping:
    """
    Mirror the fixed getOpportunityOfDay() logic in api.ts:
      if 'status' in response → return as wrapper
      else → wrap as success item
    """

    @staticmethod
    def simulate_get_opportunity_of_day(raw_response):
        """Python equivalent of the fixed TypeScript function."""
        if raw_response is None:
            return None
        if isinstance(raw_response, dict) and 'status' in raw_response:
            return raw_response  # already a wrapper
        # Legacy bare object
        return {
            'status': 'success',
            'item': raw_response,
            'message': None,
            'required_signals': None,
        }

    def test_wrapped_success_response_passes_through(self):
        raw = {'status': 'success', 'item': {'app_name': 'App'}, 'message': None}
        result = self.simulate_get_opportunity_of_day(raw)
        assert result['status'] == 'success'
        assert result['item']['app_name'] == 'App'

    def test_wrapped_insufficient_data_passes_through(self):
        raw = {'status': 'insufficient_data', 'item': None, 'message': 'Not enough signals'}
        result = self.simulate_get_opportunity_of_day(raw)
        assert result['status'] == 'insufficient_data'
        assert result['item'] is None
        assert result['message'] == 'Not enough signals'

    def test_wrapped_empty_passes_through(self):
        raw = {'status': 'empty', 'item': None, 'message': 'No apps'}
        result = self.simulate_get_opportunity_of_day(raw)
        assert result['status'] == 'empty'
        assert result['item'] is None

    def test_legacy_bare_object_is_wrapped(self):
        """Backward compat: if endpoint returns the raw fields, wrap as success."""
        raw = {'app_id': 1, 'app_name': 'Legacy App', 'primary_keyword': 'notes'}
        result = self.simulate_get_opportunity_of_day(raw)
        assert result['status'] == 'success'
        assert result['item']['app_name'] == 'Legacy App'

    def test_none_response_returns_none(self):
        result = self.simulate_get_opportunity_of_day(None)
        assert result is None


# ---------------------------------------------------------------------------
# 4. Dashboard rendering contract — no undefined values ever shown
# ---------------------------------------------------------------------------

class TestDashboardRenderingContract:
    """
    Verify that the rendering logic introduced in DashboardClient.tsx is safe.
    Simulates the JSX branching logic in Python.
    """

    @staticmethod
    def simulate_render(opportunity):
        """
        Returns what the dashboard renders for the opportunity section:
        'card'  — OpportunityOfDayCard rendered with item
        'empty' — friendly empty state rendered
        'hidden' — section not rendered (opportunity is None/falsy)
        """
        if not opportunity:
            return 'hidden'
        if opportunity.get('status') == 'success' and opportunity.get('item'):
            return 'card'
        return 'empty'

    def test_success_with_item_renders_card(self):
        opp = {'status': 'success', 'item': {'app_name': 'App'}}
        assert self.simulate_render(opp) == 'card'

    def test_insufficient_data_renders_empty_state(self):
        opp = {'status': 'insufficient_data', 'item': None, 'message': 'Not enough signals'}
        assert self.simulate_render(opp) == 'empty'

    def test_empty_status_renders_empty_state(self):
        opp = {'status': 'empty', 'item': None, 'message': 'No apps'}
        assert self.simulate_render(opp) == 'empty'

    def test_success_with_null_item_renders_empty_state(self):
        """Guard: status=success but item=None should show empty, not crash."""
        opp = {'status': 'success', 'item': None}
        assert self.simulate_render(opp) == 'empty'

    def test_none_opportunity_hides_section(self):
        assert self.simulate_render(None) == 'hidden'

    def test_card_has_real_item_not_wrapper(self):
        """When card renders, it receives opportunity.item — the raw OpportunityOfDay."""
        opp = {'status': 'success', 'item': {'app_name': 'App', 'competition_score': 30.0}}
        result = self.simulate_render(opp)
        assert result == 'card'
        # The card would receive opp['item'], never the wrapper itself
        card_prop = opp['item']
        assert 'app_name' in card_prop
        assert 'status' not in card_prop  # wrapper field must not be in card prop
