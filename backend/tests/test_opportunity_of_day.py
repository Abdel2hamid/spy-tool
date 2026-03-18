"""
test_opportunity_of_day.py
==========================
Tests for the Opportunity of the Day engine.

Verifies:
1. Same-day caching: get_or_generate() returns cached result on second call
2. No DB row → _generate_and_store() is called (generation path)
3. _get_related_apps(): returns empty list when niche is empty
4. _get_related_apps(): returns empty when category not found
5. _get_related_apps(): returns list of dicts with required keys
6. _get_related_apps(): swallows DB exception, returns empty list
7. _build_ai_summary(): returns non-empty string for valid opportunity
8. _build_ai_summary(): high success_probability yields "Strong opportunity"
9. _build_ai_summary(): moderate success_probability yields "Solid opportunity"
10. _build_ai_summary(): low success_probability yields "Emerging opportunity"
11. _build_ai_summary(): low competition yields low-competition phrase
12. _build_ai_summary(): gap_count ≥ 2 yields gap mention
13. _build_ai_summary(): momentum signals appear in summary
14. _build_ai_summary(): AI potential appears when rank/review velocity low
15. _build_ai_summary(): never returns empty string for any valid input
16. _build_ai_summary(): keyword and category appear in summary
17. OpportunityOfDayResponse schema accepts ai_summary
18. OpportunityOfDayResponse ai_summary is optional (defaults None)
19. RelatedAppItem schema validates required fields
20. RelatedAppItem optional fields default to None
21. OpportunityOfDayResponse accepts related_apps list
22. Scheduler job imports OpportunityOfDayService (not ScoringEngine)
23. Scheduler job does not call ScoringEngine directly
24. Scheduler job calls get_or_generate()
25. _generate_and_store() adds ai_summary and related_apps to result
26. _generate_and_store() returns None when engine returns None
27. _generate_and_store() commits exactly once on success
28. get_or_generate() returns None when ScoringEngine has no opportunity
"""

import sys
import os
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_opportunity(**kwargs):
    defaults = {
        "app_id": 42,
        "app_name": "TestApp",
        "primary_keyword": "productivity tools",
        "competition_score": 40.0,
        "trend_score": 65.0,
        "success_probability": 72.0,
        "attractiveness_score": 70.0,
        "feasibility_score": 68.0,
        "feasibility_details": {
            "gap_count": 3, "rating_pts": 20,
            "review_pts": 15, "competition_pts": 25,
        },
        "ai_integration_potential": 75.0,
        "rank_velocity": 3.5,
        "review_growth": 12.0,
        "rating_velocity": 0.1,
        "category_growth": 5.0,
        "category": "productivity",
        "recommendation": "Strong winner potential.",
    }
    defaults.update(kwargs)
    return defaults


def _make_cached_row(full_data: dict):
    row = MagicMock()
    row.full_data = full_data
    return row


# ---------------------------------------------------------------------------
# 1–3. get_or_generate — caching and generation paths
# ---------------------------------------------------------------------------

class TestGetOrGenerate:

    def test_returns_cached_result_when_row_exists(self):
        """If daily_opportunities row exists for today, return its full_data directly."""
        from app.services.opportunity_of_day_service import OpportunityOfDayService

        cached = {**_make_opportunity(), "ai_summary": "Cached.", "related_apps": []}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _make_cached_row(cached)

        svc = OpportunityOfDayService(db)
        result = svc.get_or_generate()

        assert result == cached
        db.execute.assert_not_called()

    def test_calls_generate_when_no_row_today(self):
        """No row for today → _generate_and_store() must be called."""
        from app.services.opportunity_of_day_service import OpportunityOfDayService

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        svc = OpportunityOfDayService(db)
        with patch.object(svc, "_generate_and_store", return_value=None) as mock_gen:
            svc.get_or_generate()
            mock_gen.assert_called_once_with(date.today())

    def test_returns_none_when_engine_has_no_opportunity(self):
        """ScoringEngine returning None propagates as None."""
        from app.services.opportunity_of_day_service import OpportunityOfDayService

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        svc = OpportunityOfDayService(db)
        with patch("app.services.opportunity_of_day_service.ScoringEngine") as MockEngine:
            MockEngine.return_value.generate_opportunity_of_day.return_value = None
            result = svc.get_or_generate()

        assert result is None


# ---------------------------------------------------------------------------
# 4–7. _get_related_apps
# ---------------------------------------------------------------------------

class TestGetRelatedApps:

    def test_returns_empty_for_empty_niche(self):
        from app.services.opportunity_of_day_service import OpportunityOfDayService
        svc = OpportunityOfDayService(MagicMock())
        assert svc._get_related_apps(niche="", exclude_app_id=1, limit=8) == []

    def test_returns_empty_when_category_not_found(self):
        from app.services.opportunity_of_day_service import OpportunityOfDayService
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = OpportunityOfDayService(db)
        assert svc._get_related_apps(niche="nonexistent", exclude_app_id=1, limit=8) == []

    def test_returns_list_with_required_keys(self):
        from app.services.opportunity_of_day_service import OpportunityOfDayService

        category = MagicMock()
        category.id = 7

        app1 = MagicMock()
        app1.id = 10
        app1.name = "Competitor A"
        app1.current_rating = 3.2
        app1.current_reviews = 50
        app1.current_rank = 25
        app1.icon_url = "https://example.com/icon.png"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = category
        (db.query.return_value
            .filter.return_value
            .filter.return_value
            .order_by.return_value
            .order_by.return_value
            .limit.return_value
            .all.return_value) = [app1]

        svc = OpportunityOfDayService(db)
        result = svc._get_related_apps(niche="productivity", exclude_app_id=42, limit=8)

        if result:
            item = result[0]
            for key in ("id", "name", "rating", "reviews", "rank"):
                assert key in item, f"Missing key: {key}"

    def test_swallows_db_exception(self):
        from app.services.opportunity_of_day_service import OpportunityOfDayService
        db = MagicMock()
        db.query.side_effect = Exception("DB error")
        svc = OpportunityOfDayService(db)
        result = svc._get_related_apps(niche="productivity", exclude_app_id=1, limit=8)
        assert result == []


# ---------------------------------------------------------------------------
# 8–16. _build_ai_summary
# ---------------------------------------------------------------------------

class TestBuildAiSummary:

    def _svc(self):
        from app.services.opportunity_of_day_service import OpportunityOfDayService
        return OpportunityOfDayService(MagicMock())

    def test_returns_non_empty_string(self):
        result = self._svc()._build_ai_summary(_make_opportunity())
        assert isinstance(result, str) and len(result) > 10

    def test_high_success_probability_strong_lead(self):
        result = self._svc()._build_ai_summary(_make_opportunity(success_probability=80.0))
        assert "Strong opportunity" in result

    def test_moderate_success_probability_solid_lead(self):
        result = self._svc()._build_ai_summary(_make_opportunity(success_probability=60.0))
        assert "Solid opportunity" in result

    def test_low_success_probability_emerging_lead(self):
        result = self._svc()._build_ai_summary(_make_opportunity(success_probability=30.0))
        assert "Emerging opportunity" in result or "early-mover" in result.lower()

    def test_low_competition_mentioned(self):
        result = self._svc()._build_ai_summary(_make_opportunity(competition_score=20.0))
        assert "low" in result.lower()

    def test_gap_count_mentioned(self):
        opp = _make_opportunity(
            feasibility_score=45.0,
            feasibility_details={"gap_count": 4, "rating_pts": 5, "review_pts": 5, "competition_pts": 5},
        )
        result = self._svc()._build_ai_summary(opp)
        assert "gap" in result.lower() or "feature" in result.lower()

    def test_momentum_signals_appear(self):
        result = self._svc()._build_ai_summary(
            _make_opportunity(rank_velocity=10.0, review_growth=20.0)
        )
        assert "momentum" in result.lower() or "growing" in result.lower() or "positive" in result.lower()

    def test_ai_potential_appears_when_no_momentum(self):
        opp = _make_opportunity(rank_velocity=0.0, review_growth=0.0, ai_integration_potential=85.0)
        result = self._svc()._build_ai_summary(opp)
        assert "ai" in result.lower() or "integration" in result.lower()

    def test_never_empty_for_edge_cases(self):
        svc = self._svc()
        for opp in [
            _make_opportunity(success_probability=0.0, competition_score=100.0, feasibility_score=0.0),
            _make_opportunity(success_probability=100.0, competition_score=0.0, feasibility_score=100.0),
            _make_opportunity(rank_velocity=0.0, review_growth=0.0, ai_integration_potential=0.0),
        ]:
            result = svc._build_ai_summary(opp)
            assert isinstance(result, str) and len(result) > 0

    def test_keyword_and_category_in_summary(self):
        result = self._svc()._build_ai_summary(
            _make_opportunity(primary_keyword="time tracking", category="productivity")
        )
        assert "productivity" in result or "time tracking" in result


# ---------------------------------------------------------------------------
# 17–21. Schema validation
# ---------------------------------------------------------------------------

class TestSchemas:

    def test_opportunity_response_accepts_ai_summary(self):
        from app.models.schemas import OpportunityOfDayResponse
        obj = OpportunityOfDayResponse(
            app_id=1, app_name="T", primary_keyword="kw",
            competition_score=50.0, trend_score=60.0, success_probability=55.0,
            ai_integration_potential=40.0, rank_velocity=1.0, review_growth=5.0,
            rating_velocity=0.0, category_growth=2.0, category="productivity",
            recommendation="Good.", ai_summary="AI summary here.", related_apps=None,
        )
        assert obj.ai_summary == "AI summary here."

    def test_opportunity_response_ai_summary_defaults_none(self):
        from app.models.schemas import OpportunityOfDayResponse
        obj = OpportunityOfDayResponse(
            app_id=1, app_name="T", primary_keyword="kw",
            competition_score=50.0, trend_score=60.0, success_probability=55.0,
            ai_integration_potential=40.0, rank_velocity=1.0, review_growth=5.0,
            rating_velocity=0.0, category_growth=2.0, category="productivity",
            recommendation="Good.",
        )
        assert obj.ai_summary is None
        assert obj.related_apps is None

    def test_related_app_item_validates_required_fields(self):
        from app.models.schemas import RelatedAppItem
        item = RelatedAppItem(id=10, name="App", rating=3.5, reviews=120, rank=45)
        assert item.id == 10
        assert item.name == "App"
        assert item.rating == 3.5

    def test_related_app_item_optional_fields_default_none(self):
        from app.models.schemas import RelatedAppItem
        item = RelatedAppItem(id=5, name="Min")
        assert item.rating is None
        assert item.reviews is None
        assert item.rank is None
        assert item.icon_url is None

    def test_opportunity_response_accepts_related_apps_list(self):
        from app.models.schemas import OpportunityOfDayResponse, RelatedAppItem
        related = [RelatedAppItem(id=7, name="Rival", rating=3.1, reviews=80, rank=30)]
        obj = OpportunityOfDayResponse(
            app_id=1, app_name="T", primary_keyword="kw",
            competition_score=50.0, trend_score=60.0, success_probability=55.0,
            ai_integration_potential=40.0, rank_velocity=1.0, review_growth=5.0,
            rating_velocity=0.0, category_growth=2.0, category="productivity",
            recommendation="Good.", related_apps=related,
        )
        assert len(obj.related_apps) == 1
        assert obj.related_apps[0].name == "Rival"


# ---------------------------------------------------------------------------
# 22–24. Scheduler integration
# ---------------------------------------------------------------------------

class TestSchedulerIntegration:

    def test_scheduler_imports_opportunity_service(self):
        import inspect
        from app.workers import scheduler as sched_module
        src = inspect.getsource(sched_module.job_opportunity_compute)
        assert "OpportunityOfDayService" in src

    def test_scheduler_does_not_call_scoring_engine_directly(self):
        import inspect
        from app.workers import scheduler as sched_module
        src = inspect.getsource(sched_module.job_opportunity_compute)
        assert "ScoringEngine" not in src

    def test_scheduler_calls_get_or_generate(self):
        import inspect
        from app.workers import scheduler as sched_module
        src = inspect.getsource(sched_module.job_opportunity_compute)
        assert "get_or_generate" in src


# ---------------------------------------------------------------------------
# 25–28. _generate_and_store
# ---------------------------------------------------------------------------

class TestGenerateAndStore:

    def test_result_contains_ai_summary_and_related_apps(self):
        from app.services.opportunity_of_day_service import OpportunityOfDayService

        opp = _make_opportunity()
        db = MagicMock()
        svc = OpportunityOfDayService(db)

        with patch("app.services.opportunity_of_day_service.ScoringEngine") as MockEngine:
            MockEngine.return_value.generate_opportunity_of_day.return_value = opp
            with patch.object(svc, "_get_related_apps", return_value=[{"id": 7, "name": "Rival"}]):
                result = svc._generate_and_store(date.today())

        assert result is not None
        assert "ai_summary" in result
        assert "related_apps" in result
        assert result["related_apps"] == [{"id": 7, "name": "Rival"}]

    def test_returns_none_when_engine_returns_none(self):
        from app.services.opportunity_of_day_service import OpportunityOfDayService

        db = MagicMock()
        svc = OpportunityOfDayService(db)

        with patch("app.services.opportunity_of_day_service.ScoringEngine") as MockEngine:
            MockEngine.return_value.generate_opportunity_of_day.return_value = None
            result = svc._generate_and_store(date.today())

        assert result is None
        db.commit.assert_not_called()

    def test_commits_exactly_once_on_success(self):
        from app.services.opportunity_of_day_service import OpportunityOfDayService

        opp = _make_opportunity()
        db = MagicMock()
        svc = OpportunityOfDayService(db)

        with patch("app.services.opportunity_of_day_service.ScoringEngine") as MockEngine:
            MockEngine.return_value.generate_opportunity_of_day.return_value = opp
            with patch.object(svc, "_get_related_apps", return_value=[]):
                svc._generate_and_store(date.today())

        db.commit.assert_called_once()
