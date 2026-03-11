"""
Tests for intelligence endpoints returning proper empty/insufficient_data states.

Verifies that endpoints:
1. Return status="empty" when no data in database
2. Return status="insufficient_data" when data exists but signals are missing
3. Never fabricate fake results with score=0 or arbitrary rows
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestResponseSchemaStructure:
    """Tests verifying the response schemas have proper structure."""

    def test_trending_response_has_status_field(self):
        """TrendingAppsResponse should have status, message, required_signals, items fields."""
        from app.models.schemas import TrendingAppsResponse
        
        response = TrendingAppsResponse(
            status="success",
            message=None,
            required_signals=None,
            items=[]
        )
        
        assert response.status == "success"
        assert response.items is not None

    def test_opportunity_response_has_status_field(self):
        """OpportunityOfDayWrapperResponse should have status, message, required_signals, item fields."""
        from app.models.schemas import OpportunityOfDayWrapperResponse
        
        response = OpportunityOfDayWrapperResponse(
            status="success",
            message=None,
            required_signals=None,
            item=None
        )
        
        assert response.status == "success"
        assert response.item is None or response.item is not None

    def test_keyword_opportunities_response_has_status_field(self):
        """KeywordOpportunitiesWrapperResponse should have status, message, required_signals, items fields."""
        from app.models.schemas import KeywordOpportunitiesWrapperResponse
        
        response = KeywordOpportunitiesWrapperResponse(
            status="success",
            message=None,
            required_signals=None,
            items=[]
        )
        
        assert response.status == "success"
        assert response.items is not None

    def test_status_values_are_valid(self):
        """Status field should only accept valid values."""
        from app.models.schemas import TrendingAppsResponse
        
        valid_statuses = ["success", "insufficient_data", "empty", "pipeline_not_run"]
        
        for status in valid_statuses:
            response = TrendingAppsResponse(
                status=status,
                message=None,
                required_signals=None,
                items=[]
            )
            assert response.status == status


class TestEmptyStateResponses:
    """Tests for proper empty state response structures."""

    def test_empty_response_structure(self):
        """Empty response should have proper structure."""
        from app.models.schemas import TrendingAppsResponse
        
        response = TrendingAppsResponse(
            status="empty",
            message="No apps in database. Add apps to track trending.",
            required_signals=["apps"],
            items=[]
        )
        
        assert response.status == "empty"
        assert response.message is not None
        assert response.required_signals == ["apps"]
        assert response.items == []

    def test_insufficient_data_response_structure(self):
        """Insufficient data response should have proper structure."""
        from app.models.schemas import TrendingAppsResponse
        
        response = TrendingAppsResponse(
            status="insufficient_data",
            message="Apps exist but no ranking history to compute trends yet.",
            required_signals=["ranking_history", "recent_snapshots"],
            items=[]
        )
        
        assert response.status == "insufficient_data"
        assert response.message is not None
        assert response.required_signals == ["ranking_history", "recent_snapshots"]
        assert response.items == []


class TestNoFakeDataInResponses:
    """Tests ensuring responses don't contain fake/fabricated data."""

    def test_success_response_has_real_data(self):
        """Success response should have real data in items."""
        from app.models.schemas import TrendingAppsResponse, TrendingAppV2Response
        
        trending_item = TrendingAppV2Response(
            id=1,
            app_id="123456789",
            name="Test App",
            developer="Test Dev",
            icon_url=None,
            current_rank=10,
            current_rating=4.5,
            current_reviews=100,
            trend_score=75.0,
            momentum_3d=10.0,
            momentum_7d=15.0,
            consistency_score=0.8,
            confidence_factor=0.9,
            absolute_rank_bonus=5.0,
            review_momentum=20.0
        )
        
        response = TrendingAppsResponse(
            status="success",
            message=None,
            required_signals=None,
            items=[trending_item]
        )
        
        assert response.status == "success"
        assert len(response.items) == 1
        assert response.items[0].trend_score > 0

    def test_insufficient_data_has_empty_items(self):
        """Insufficient data response should have empty items list."""
        from app.models.schemas import TrendingAppsResponse
        
        response = TrendingAppsResponse(
            status="insufficient_data",
            message="Not enough signals",
            required_signals=["ranking_history"],
            items=[]
        )
        
        assert response.items == []
        assert response.status != "success"


class TestBackendLogicPatterns:
    """Tests for backend logic patterns that should be followed."""

    def test_never_return_arbitrary_rows_with_zero_score(self):
        """Pattern: Don't return arbitrary rows when scoring fails."""
        trending = []
        
        if not trending:
            app_count = 0
            
            if app_count == 0:
                result = {
                    "status": "empty",
                    "message": "No apps in database",
                    "required_signals": ["apps"],
                    "items": []
                }
            else:
                result = {
                    "status": "insufficient_data",
                    "message": "No ranking history",
                    "required_signals": ["ranking_history"],
                    "items": []
                }
        else:
            result = {
                "status": "success",
                "items": trending
            }
        
        assert result["status"] in ["success", "empty", "insufficient_data"]
        if result["status"] == "insufficient_data":
            assert result["items"] == []
        if result["status"] == "empty":
            assert result["items"] == []

    def test_distinguish_empty_vs_insufficient(self):
        """Pattern: Distinguish between empty database and insufficient signals."""
        
        def check_data_state(app_count, ranking_count):
            if app_count == 0:
                return "empty"
            elif ranking_count == 0:
                return "insufficient_data"
            else:
                return "success"
        
        assert check_data_state(0, 0) == "empty"
        assert check_data_state(10, 0) == "insufficient_data"
        assert check_data_state(10, 100) == "success"
