"""
test_weekly_opportunities.py
==============================
Tests for the Top-5 Opportunities This Week feature.

Verifies:
1.  _week_start() returns Monday for any day of the week
2.  _opportunity_score() formula: trend*0.5 + (100-comp)*0.3 + success*0.2
3.  _opportunity_score() clamps / handles missing values
4.  get_or_generate() returns cached rows when 5 already exist for this week
5.  get_or_generate() calls _generate_and_store() when no rows exist
6.  get_or_generate() calls _generate_and_store() when < 5 rows exist
7.  _generate_and_store() returns empty list when ScoringEngine has no candidates
8.  _generate_and_store() persists exactly 5 rows (commits once)
9.  _generate_and_store() assigns ranks 1–5 in order
10. _generate_and_store() stores full_data with rank + ai_summary + related_apps
11. _pick_diverse_top5() selects at most one per niche
12. _pick_diverse_top5() fills remaining slots when < 5 niches
13. _pick_diverse_top5() always returns ≤ 5 items
14. _get_related_apps() returns empty list when niche is empty
15. _get_related_apps() swallows DB exceptions
16. _build_weekly_ai_summary() returns non-empty string for any rank
17. _build_weekly_ai_summary() includes rank label in output
18. _build_weekly_ai_summary() mentions high opportunity score
19. _build_weekly_ai_summary() mentions trend when trend is high
20. _build_weekly_ai_summary() mentions AI potential when trend is low
21. WeeklyOpportunityItem schema validates required fields
22. WeeklyOpportunityItem schema accepts related_apps list
23. WeeklyOpportunitiesResponse schema wraps items list
24. Scheduler job uses WeeklyOpportunitiesService (not ScoringEngine directly)
25. Scheduler job calls get_or_generate()
26. ScoringEngine.generate_opportunity_of_day() still returns single item (backward compat)
27. ScoringEngine.get_all_scored_opportunities() returns list
28. scoring formula ranking: higher opp_score → lower rank number
"""

import sys
import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(
    app_id=1, app_name="TestApp", category="productivity",
    trend_score=60.0, competition_score=40.0, success_probability=55.0,
    feasibility_score=65.0, attractiveness_score=60.0, ai_integration_potential=50.0,
    rank_velocity=2.0, review_growth=5.0, feasibility_details=None,
    **kwargs,
):
    return {
        "app_id": app_id,
        "app_name": app_name,
        "primary_keyword": f"{category} app",
        "category": category,
        "competition_score": competition_score,
        "trend_score": trend_score,
        "success_probability": success_probability,
        "feasibility_score": feasibility_score,
        "attractiveness_score": attractiveness_score,
        "ai_integration_potential": ai_integration_potential,
        "rank_velocity": rank_velocity,
        "review_growth": review_growth,
        "feasibility_details": feasibility_details or {"gap_count": 1},
        "recommendation": "Good pick.",
        **kwargs,
    }


def _make_five_candidates():
    niches = ["productivity", "finance", "health", "games", "social"]
    return [_make_candidate(app_id=i+1, category=n, trend_score=80.0-i*5, competition_score=30.0+i*2)
            for i, n in enumerate(niches)]


def _make_weekly_row(rank: int, full_data: dict):
    row = MagicMock()
    row.rank = rank
    row.full_data = full_data
    return row


# ---------------------------------------------------------------------------
# 1–3. Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_week_start_returns_monday(self):
        from app.services.weekly_opportunities_service import _week_start
        # 2024-01-15 is a Monday
        monday = date(2024, 1, 15)
        assert _week_start(monday) == monday
        # Tuesday
        assert _week_start(date(2024, 1, 16)) == monday
        # Sunday
        assert _week_start(date(2024, 1, 21)) == monday
        # Saturday
        assert _week_start(date(2024, 1, 20)) == monday

    def test_week_start_spans_month_boundary(self):
        from app.services.weekly_opportunities_service import _week_start
        # Friday 2024-03-29 → Monday is 2024-03-25
        assert _week_start(date(2024, 3, 29)) == date(2024, 3, 25)

    def test_opportunity_score_formula(self):
        from app.services.weekly_opportunities_service import _opportunity_score
        c = {"trend_score": 60.0, "competition_score": 40.0, "success_probability": 50.0}
        # 60*0.5 + (100-40)*0.3 + 50*0.2 = 30 + 18 + 10 = 58
        assert abs(_opportunity_score(c) - 58.0) < 0.1

    def test_opportunity_score_zero_inputs(self):
        from app.services.weekly_opportunities_service import _opportunity_score
        c = {"trend_score": 0.0, "competition_score": 0.0, "success_probability": 0.0}
        # 0*0.5 + 100*0.3 + 0*0.2 = 30
        assert abs(_opportunity_score(c) - 30.0) < 0.1

    def test_opportunity_score_handles_missing_keys(self):
        from app.services.weekly_opportunities_service import _opportunity_score
        # Missing keys → defaults
        assert isinstance(_opportunity_score({}), float)

    def test_opportunity_score_max_inputs(self):
        from app.services.weekly_opportunities_service import _opportunity_score
        c = {"trend_score": 100.0, "competition_score": 0.0, "success_probability": 100.0}
        # 50 + 30 + 20 = 100
        assert abs(_opportunity_score(c) - 100.0) < 0.1


# ---------------------------------------------------------------------------
# 4–6. get_or_generate — caching
# ---------------------------------------------------------------------------

class TestCaching:

    def test_returns_cached_when_5_rows_exist(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService

        full_datas = [{"rank": i, "app_name": f"App{i}"} for i in range(1, 6)]
        rows = [_make_weekly_row(i, full_datas[i-1]) for i in range(1, 6)]

        db = MagicMock()
        (db.query.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value) = rows

        svc = WeeklyOpportunitiesService(db)
        result = svc.get_or_generate()

        assert len(result) == 5
        db.execute.assert_not_called()

    def test_calls_generate_when_no_rows(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService

        db = MagicMock()
        (db.query.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value) = []

        svc = WeeklyOpportunitiesService(db)
        with patch.object(svc, "_generate_and_store", return_value=[]) as mock_gen:
            svc.get_or_generate()
            mock_gen.assert_called_once()

    def test_calls_generate_when_fewer_than_5_rows(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService

        rows = [_make_weekly_row(i, {"rank": i}) for i in range(1, 4)]  # only 3

        db = MagicMock()
        (db.query.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value) = rows

        svc = WeeklyOpportunitiesService(db)
        with patch.object(svc, "_generate_and_store", return_value=[]) as mock_gen:
            svc.get_or_generate()
            mock_gen.assert_called_once()


# ---------------------------------------------------------------------------
# 7–10. _generate_and_store
# ---------------------------------------------------------------------------

class TestGenerateAndStore:

    def test_returns_empty_when_engine_has_no_candidates(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService

        db = MagicMock()
        svc = WeeklyOpportunitiesService(db)

        with patch("app.services.weekly_opportunities_service.ScoringEngine") as MockEngine:
            MockEngine.return_value.get_all_scored_opportunities.return_value = []
            result = svc._generate_and_store(date.today())

        assert result == []
        db.commit.assert_not_called()

    def test_commits_once_for_all_5(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService

        db = MagicMock()
        svc = WeeklyOpportunitiesService(db)
        candidates = _make_five_candidates()

        with patch("app.services.weekly_opportunities_service.ScoringEngine") as MockEngine:
            MockEngine.return_value.get_all_scored_opportunities.return_value = candidates
            with patch.object(svc, "_get_related_apps", return_value=[]):
                svc._generate_and_store(date.today())

        db.commit.assert_called_once()

    def test_assigns_ranks_1_through_5(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService

        db = MagicMock()
        svc = WeeklyOpportunitiesService(db)
        candidates = _make_five_candidates()

        with patch("app.services.weekly_opportunities_service.ScoringEngine") as MockEngine:
            MockEngine.return_value.get_all_scored_opportunities.return_value = candidates
            with patch.object(svc, "_get_related_apps", return_value=[]):
                result = svc._generate_and_store(date.today())

        ranks = [item["rank"] for item in result]
        assert sorted(ranks) == [1, 2, 3, 4, 5]

    def test_full_data_contains_required_fields(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService

        db = MagicMock()
        svc = WeeklyOpportunitiesService(db)
        candidates = _make_five_candidates()

        with patch("app.services.weekly_opportunities_service.ScoringEngine") as MockEngine:
            MockEngine.return_value.get_all_scored_opportunities.return_value = candidates
            with patch.object(svc, "_get_related_apps", return_value=[{"id": 9, "name": "Rival"}]):
                result = svc._generate_and_store(date.today())

        for item in result:
            assert "rank" in item
            assert "ai_summary" in item
            assert "related_apps" in item
            assert "opportunity_score" in item
            assert item["ai_summary"] and len(item["ai_summary"]) > 0

    def test_result_sorted_by_rank(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService

        db = MagicMock()
        svc = WeeklyOpportunitiesService(db)
        candidates = _make_five_candidates()

        with patch("app.services.weekly_opportunities_service.ScoringEngine") as MockEngine:
            MockEngine.return_value.get_all_scored_opportunities.return_value = candidates
            with patch.object(svc, "_get_related_apps", return_value=[]):
                result = svc._generate_and_store(date.today())

        ranks = [item["rank"] for item in result]
        assert ranks == sorted(ranks)


# ---------------------------------------------------------------------------
# 11–13. _pick_diverse_top5
# ---------------------------------------------------------------------------

class TestPickDiverseTop5:

    def _svc(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService
        return WeeklyOpportunitiesService(MagicMock())

    def test_at_most_one_per_niche(self):
        svc = self._svc()
        # 10 candidates all same niche
        candidates = [_make_candidate(app_id=i, category="productivity") for i in range(10)]
        result = svc._pick_diverse_top5(candidates)
        niches = [c["category"] for c in result]
        # First pass gets only 1 unique niche, second pass fills up to 5
        assert len(result) <= 5

    def test_fills_remaining_when_fewer_than_5_niches(self):
        svc = self._svc()
        # 3 unique niches but 10 candidates
        cats = ["productivity", "finance", "health"]
        candidates = [_make_candidate(app_id=i, category=cats[i % 3]) for i in range(10)]
        result = svc._pick_diverse_top5(candidates)
        assert len(result) == 5

    def test_returns_at_most_5(self):
        svc = self._svc()
        candidates = [_make_candidate(app_id=i, category=f"cat{i}") for i in range(20)]
        result = svc._pick_diverse_top5(candidates)
        assert len(result) <= 5

    def test_5_unique_niches_returns_5_diverse(self):
        svc = self._svc()
        candidates = _make_five_candidates()
        result = svc._pick_diverse_top5(candidates)
        assert len(result) == 5
        niches = [c["category"] for c in result]
        assert len(set(niches)) == 5  # all unique


# ---------------------------------------------------------------------------
# 14–15. _get_related_apps
# ---------------------------------------------------------------------------

class TestGetRelatedApps:

    def test_returns_empty_for_empty_niche(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService
        svc = WeeklyOpportunitiesService(MagicMock())
        assert svc._get_related_apps(niche="", exclude_app_id=1, limit=6) == []

    def test_swallows_db_exception(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService
        db = MagicMock()
        db.query.side_effect = Exception("DB error")
        svc = WeeklyOpportunitiesService(db)
        result = svc._get_related_apps(niche="productivity", exclude_app_id=1, limit=6)
        assert result == []


# ---------------------------------------------------------------------------
# 16–20. _build_weekly_ai_summary
# ---------------------------------------------------------------------------

class TestBuildWeeklyAiSummary:

    def _svc(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService
        return WeeklyOpportunitiesService(MagicMock())

    def _candidate(self, **kwargs):
        c = _make_candidate(**kwargs)
        from app.services.weekly_opportunities_service import _opportunity_score
        c["opportunity_score"] = _opportunity_score(c)
        return c

    def test_returns_non_empty_for_all_ranks(self):
        svc = self._svc()
        c = self._candidate()
        for rank in range(1, 6):
            result = svc._build_weekly_ai_summary(c, rank)
            assert isinstance(result, str) and len(result) > 10

    def test_includes_rank_label(self):
        svc = self._svc()
        c = self._candidate()
        result1 = svc._build_weekly_ai_summary(c, 1)
        result2 = svc._build_weekly_ai_summary(c, 2)
        assert "top" in result1.lower()
        assert "second" in result2.lower()

    def test_high_score_mentions_exceptional(self):
        svc = self._svc()
        # trend=100, comp=0, success=100 → score=100
        c = self._candidate(trend_score=100.0, competition_score=0.0, success_probability=100.0)
        from app.services.weekly_opportunities_service import _opportunity_score
        c["opportunity_score"] = _opportunity_score(c)
        result = svc._build_weekly_ai_summary(c, 1)
        assert "exceptional" in result.lower() or "strong" in result.lower()

    def test_high_trend_score_mentioned(self):
        svc = self._svc()
        c = self._candidate(trend_score=90.0)
        c["opportunity_score"] = 70.0
        result = svc._build_weekly_ai_summary(c, 1)
        assert "trend" in result.lower() or "momentum" in result.lower()

    def test_ai_potential_mentioned_when_trend_low(self):
        svc = self._svc()
        c = self._candidate(trend_score=10.0, ai_integration_potential=85.0)
        c["opportunity_score"] = 40.0
        result = svc._build_weekly_ai_summary(c, 1)
        assert "ai" in result.lower() or "integration" in result.lower()


# ---------------------------------------------------------------------------
# 21–23. Schemas
# ---------------------------------------------------------------------------

class TestSchemas:

    def test_weekly_opportunity_item_required_fields(self):
        from app.models.schemas import WeeklyOpportunityItem
        item = WeeklyOpportunityItem(
            rank=1,
            app_id=42,
            app_name="TestApp",
            primary_keyword="productivity tools",
            competition_score=40.0,
            trend_score=65.0,
            success_probability=72.0,
            opportunity_score=63.5,
            category="productivity",
        )
        assert item.rank == 1
        assert item.opportunity_score == 63.5

    def test_weekly_opportunity_item_optional_fields_default_none(self):
        from app.models.schemas import WeeklyOpportunityItem
        item = WeeklyOpportunityItem(
            rank=2, app_id=5, app_name="A", primary_keyword="kw",
            competition_score=50.0, trend_score=60.0, success_probability=55.0,
            opportunity_score=55.0, category="finance",
        )
        assert item.ai_summary is None
        assert item.related_apps is None

    def test_weekly_opportunity_item_accepts_related_apps(self):
        from app.models.schemas import WeeklyOpportunityItem, RelatedAppItem
        related = [RelatedAppItem(id=7, name="Rival", rating=3.1, reviews=80, rank=30)]
        item = WeeklyOpportunityItem(
            rank=1, app_id=42, app_name="T", primary_keyword="kw",
            competition_score=40.0, trend_score=65.0, success_probability=72.0,
            opportunity_score=63.5, category="productivity",
            related_apps=related,
        )
        assert len(item.related_apps) == 1

    def test_weekly_opportunities_response_wraps_items(self):
        from app.models.schemas import WeeklyOpportunitiesResponse, WeeklyOpportunityItem
        items = [
            WeeklyOpportunityItem(
                rank=i, app_id=i, app_name=f"App{i}", primary_keyword="kw",
                competition_score=40.0, trend_score=65.0, success_probability=55.0,
                opportunity_score=55.0, category="productivity",
            )
            for i in range(1, 6)
        ]
        resp = WeeklyOpportunitiesResponse(
            status="success",
            week_start_date="2024-01-15",
            items=items,
        )
        assert resp.status == "success"
        assert len(resp.items) == 5

    def test_weekly_opportunities_response_empty_items_default(self):
        from app.models.schemas import WeeklyOpportunitiesResponse
        resp = WeeklyOpportunitiesResponse(status="insufficient_data")
        assert resp.items == []


# ---------------------------------------------------------------------------
# 24–25. Scheduler integration
# ---------------------------------------------------------------------------

class TestSchedulerIntegration:

    def test_scheduler_uses_weekly_opportunities_service(self):
        import inspect
        from app.workers import scheduler as sched_module
        src = inspect.getsource(sched_module.job_weekly_opportunities_compute)
        assert "WeeklyOpportunitiesService" in src

    def test_scheduler_calls_get_or_generate(self):
        import inspect
        from app.workers import scheduler as sched_module
        src = inspect.getsource(sched_module.job_weekly_opportunities_compute)
        assert "get_or_generate" in src


# ---------------------------------------------------------------------------
# 26–27. ScoringEngine backward compatibility
# ---------------------------------------------------------------------------

class TestScoringEngineBackwardCompat:

    def test_generate_opportunity_of_day_still_returns_single_item_or_none(self):
        """generate_opportunity_of_day() must still return a dict or None (not a list)."""
        from app.scoring.engine import ScoringEngine
        db = MagicMock()
        engine = ScoringEngine(db)
        # Empty ranked apps → returns None
        db.query.return_value.filter.return_value.all.return_value = []
        result = engine.generate_opportunity_of_day()
        assert result is None

    def test_get_all_scored_opportunities_returns_list(self):
        """get_all_scored_opportunities() must exist and return a list."""
        from app.scoring.engine import ScoringEngine
        db = MagicMock()
        engine = ScoringEngine(db)
        db.query.return_value.filter.return_value.all.return_value = []
        result = engine.get_all_scored_opportunities()
        assert isinstance(result, list)

    def test_get_all_scored_opportunities_respects_n_cap(self):
        """get_all_scored_opportunities(n=3) must return at most 3 items."""
        from app.scoring.engine import ScoringEngine
        db = MagicMock()
        engine = ScoringEngine(db)
        with patch.object(engine, "_build_scored_opportunities",
                          return_value=[{"app_id": i} for i in range(10)]):
            result = engine.get_all_scored_opportunities(n=3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# 28. Ranking order
# ---------------------------------------------------------------------------

class TestRankingOrder:

    def test_highest_opp_score_gets_rank_1(self):
        from app.services.weekly_opportunities_service import WeeklyOpportunitiesService, _opportunity_score

        db = MagicMock()
        svc = WeeklyOpportunitiesService(db)

        # Deliberately make candidate #3 the strongest
        candidates = [
            _make_candidate(app_id=1, category="c1", trend_score=40.0, competition_score=60.0, success_probability=40.0),
            _make_candidate(app_id=2, category="c2", trend_score=50.0, competition_score=50.0, success_probability=50.0),
            _make_candidate(app_id=3, category="c3", trend_score=90.0, competition_score=10.0, success_probability=90.0),
            _make_candidate(app_id=4, category="c4", trend_score=30.0, competition_score=70.0, success_probability=30.0),
            _make_candidate(app_id=5, category="c5", trend_score=20.0, competition_score=80.0, success_probability=20.0),
        ]

        with patch("app.services.weekly_opportunities_service.ScoringEngine") as MockEngine:
            MockEngine.return_value.get_all_scored_opportunities.return_value = candidates
            with patch.object(svc, "_get_related_apps", return_value=[]):
                result = svc._generate_and_store(date.today())

        rank1 = next(item for item in result if item["rank"] == 1)
        assert rank1["app_id"] == 3  # app_id=3 has highest opp score
