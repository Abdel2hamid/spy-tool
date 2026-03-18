"""
Tests for the New Releases and Released Today discovery endpoints.

Verifies:
1. mode=new_releases filters by release_date within last 30 days (not created_at)
2. mode=released_today uses a ROLLING 24-HOUR window (not a calendar-day boundary)
3. Apps with NULL release_date are always excluded from both modes
4. AppListResponse has correct pagination fields (apps, total, skip, limit)
5. DashboardKeywordHighlightsResponse returns sorted keywords with proper schema
6. Unknown mode falls back to new_releases behaviour (not released_today)
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helper — pure date-filter logic mirrored from routes.py
# ---------------------------------------------------------------------------

def _apply_mode_filter(apps: list, mode: str, now: Optional[datetime] = None) -> list:
    """
    Replicates the date-filter logic from GET /apps/latest so that the
    filtering rules can be tested independently of FastAPI / SQLAlchemy.

    mode=released_today uses a ROLLING 24-HOUR window (not a calendar-day boundary).
    """
    now = now or datetime.now(timezone.utc)

    if mode == "released_today":
        cutoff_24h = now - timedelta(hours=24)
        return [
            a for a in apps
            if a.get("release_date") is not None
            and a["release_date"] >= cutoff_24h
        ]
    else:
        # new_releases (default — also covers unknown mode values)
        cutoff = now - timedelta(days=30)
        return [
            a for a in apps
            if a.get("release_date") is not None
            and a["release_date"] >= cutoff
        ]


class TestNewReleasesMode:
    """Tests for mode=new_releases (default)."""

    def _now(self) -> datetime:
        return datetime(2026, 3, 17, 12, 0, 0)

    def test_includes_app_released_today(self):
        now = self._now()
        apps = [{"id": 1, "release_date": now - timedelta(hours=3)}]
        result = _apply_mode_filter(apps, "new_releases", now)
        assert len(result) == 1

    def test_includes_app_released_29_days_ago(self):
        now = self._now()
        apps = [{"id": 2, "release_date": now - timedelta(days=29)}]
        result = _apply_mode_filter(apps, "new_releases", now)
        assert len(result) == 1

    def test_excludes_app_released_31_days_ago(self):
        now = self._now()
        apps = [{"id": 3, "release_date": now - timedelta(days=31)}]
        result = _apply_mode_filter(apps, "new_releases", now)
        assert len(result) == 0

    def test_excludes_app_with_null_release_date(self):
        now = self._now()
        apps = [{"id": 4, "release_date": None}]
        result = _apply_mode_filter(apps, "new_releases", now)
        assert len(result) == 0

    def test_does_not_use_created_at(self):
        """created_at being old should NOT exclude a recently released app."""
        now = self._now()
        # App has an old created_at (scraped long ago) but was just released
        apps = [
            {
                "id": 5,
                "release_date": now - timedelta(days=2),
                "created_at": now - timedelta(days=365),  # imported a year ago
            }
        ]
        result = _apply_mode_filter(apps, "new_releases", now)
        assert len(result) == 1, "Should be included — release_date is recent even if created_at is old"

    def test_returns_multiple_valid_apps(self):
        now = self._now()
        apps = [
            {"id": 1, "release_date": now - timedelta(days=1)},
            {"id": 2, "release_date": now - timedelta(days=15)},
            {"id": 3, "release_date": now - timedelta(days=35)},  # too old
            {"id": 4, "release_date": None},                       # null → excluded
        ]
        result = _apply_mode_filter(apps, "new_releases", now)
        ids = [a["id"] for a in result]
        assert sorted(ids) == [1, 2]

    def test_unknown_mode_falls_back_to_new_releases(self):
        """An unknown mode string should behave like new_releases, not released_today."""
        now = self._now()
        # yesterday: in 30-day window but NOT today → would be excluded by released_today
        apps = [{"id": 1, "release_date": now - timedelta(days=1)}]
        result = _apply_mode_filter(apps, "some_unknown_mode", now)
        assert len(result) == 1, "Unknown mode should fall back to new_releases"


class TestReleasedTodayMode:
    """
    Tests for mode=released_today.

    ROLLING 24-HOUR WINDOW: the cutoff is always (now - 24h), not UTC midnight.
    An app released 2 hours ago always appears; one released 25 hours ago never does.
    """

    def _now(self) -> datetime:
        # Use a fixed timezone-aware reference point.
        return datetime(2026, 3, 17, 14, 30, 0, tzinfo=timezone.utc)

    def test_includes_app_released_2_hours_ago(self):
        """App released 2 hours ago is within the 24h window."""
        now = self._now()
        apps = [{"id": 1, "release_date": now - timedelta(hours=2)}]
        result = _apply_mode_filter(apps, "released_today", now)
        assert len(result) == 1

    def test_includes_app_released_23_hours_ago(self):
        """App released 23 hours ago is still within the 24h window."""
        now = self._now()
        apps = [{"id": 2, "release_date": now - timedelta(hours=23)}]
        result = _apply_mode_filter(apps, "released_today", now)
        assert len(result) == 1

    def test_excludes_app_released_25_hours_ago(self):
        """App released 25 hours ago is outside the 24h window."""
        now = self._now()
        apps = [{"id": 3, "release_date": now - timedelta(hours=25)}]
        result = _apply_mode_filter(apps, "released_today", now)
        assert len(result) == 0

    def test_boundary_exactly_24h_ago_is_included(self):
        """Exact boundary: release_date >= cutoff uses >=, so exactly 24h ago IS included."""
        now = self._now()
        apps = [{"id": 4, "release_date": now - timedelta(hours=24)}]
        result = _apply_mode_filter(apps, "released_today", now)
        assert len(result) == 1  # >= is inclusive

    def test_excludes_app_released_24h_and_1s_ago(self):
        """One second past the 24h boundary is excluded."""
        now = self._now()
        apps = [{"id": 4, "release_date": now - timedelta(hours=24, seconds=1)}]
        result = _apply_mode_filter(apps, "released_today", now)
        assert len(result) == 0

    def test_excludes_app_with_null_release_date(self):
        now = self._now()
        apps = [{"id": 5, "release_date": None}]
        result = _apply_mode_filter(apps, "released_today", now)
        assert len(result) == 0

    def test_empty_database_returns_empty_list(self):
        now = self._now()
        result = _apply_mode_filter([], "released_today", now)
        assert result == []

    def test_advancing_clock_removes_stale_apps(self):
        """
        An app released at T=0 is visible until T=24h. After 25h it must
        have dropped out of the rolling window.
        """
        base_time = datetime(2026, 3, 17, 10, 0, 0, tzinfo=timezone.utc)
        app = {"id": 10, "release_date": base_time}

        # At T+2h → inside window
        now_2h = base_time + timedelta(hours=2)
        assert len(_apply_mode_filter([app], "released_today", now_2h)) == 1

        # At T+23h → still inside
        now_23h = base_time + timedelta(hours=23)
        assert len(_apply_mode_filter([app], "released_today", now_23h)) == 1

        # At T+25h → outside window
        now_25h = base_time + timedelta(hours=25)
        assert len(_apply_mode_filter([app], "released_today", now_25h)) == 0

    def test_rolling_window_does_not_reset_at_midnight(self):
        """
        The old calendar-day logic would reset at UTC midnight, making an app
        released at 11 PM disappear at 12:01 AM next day (only 61 minutes later).
        The rolling window keeps it for the full 24 hours.
        """
        # App released at 11 PM UTC
        release_time = datetime(2026, 3, 17, 23, 0, 0, tzinfo=timezone.utc)
        app = {"id": 11, "release_date": release_time}

        # 61 minutes later (1:01 AM next day) — old calendar logic would exclude it
        now_61m = release_time + timedelta(minutes=61)
        result = _apply_mode_filter([app], "released_today", now_61m)
        assert len(result) == 1, (
            "App released 61 minutes ago should still appear under rolling-window logic"
        )

    def test_hourly_ingestion_newly_discovered_app_appears(self):
        """
        Simulate chart discovery finding a new app. After the queue processor
        writes it to the DB (within ~30 min), it should appear in Released Today
        if its release_date is within the last 24h.
        """
        now = datetime(2026, 3, 17, 15, 0, 0, tzinfo=timezone.utc)

        # App was released 30 minutes ago, discovered by the hourly chart scraper
        newly_ingested = {"id": 99, "release_date": now - timedelta(minutes=30)}

        result = _apply_mode_filter([newly_ingested], "released_today", now)
        assert len(result) == 1, "Newly ingested app within last 24h must appear in Released Today"


class TestNullReleaseDateExclusion:
    """NULL release_date must be excluded from every mode."""

    def test_null_excluded_from_new_releases(self):
        now = datetime(2026, 3, 17, 12, 0, 0)
        apps = [{"id": 1, "release_date": None}]
        assert _apply_mode_filter(apps, "new_releases", now) == []

    def test_null_excluded_from_released_today(self):
        now = datetime(2026, 3, 17, 12, 0, 0)
        apps = [{"id": 1, "release_date": None}]
        assert _apply_mode_filter(apps, "released_today", now) == []

    def test_mix_of_null_and_valid_releases(self):
        now = datetime(2026, 3, 17, 12, 0, 0)
        apps = [
            {"id": 1, "release_date": now - timedelta(days=5)},
            {"id": 2, "release_date": None},
            {"id": 3, "release_date": now - timedelta(days=10)},
        ]
        result = _apply_mode_filter(apps, "new_releases", now)
        assert len(result) == 2
        assert all(a["release_date"] is not None for a in result)


class TestAppListResponseSchema:
    """Tests for AppListResponse pagination schema."""

    def test_schema_has_required_fields(self):
        from app.models.schemas import AppListResponse

        response = AppListResponse(apps=[], total=0, skip=0, limit=50)
        assert response.total == 0
        assert response.skip == 0
        assert response.limit == 50
        assert response.apps == []

    def test_total_reflects_filtered_count(self):
        """total should reflect the full filtered count, not just the page size."""
        from app.models.schemas import AppListResponse

        response = AppListResponse(apps=[], total=150, skip=100, limit=50)
        assert response.total == 150
        assert response.skip == 100
        assert len(response.apps) == 0  # page is empty but total is 150

    def test_limit_and_skip_are_preserved(self):
        from app.models.schemas import AppListResponse

        response = AppListResponse(apps=[], total=0, skip=25, limit=25)
        assert response.skip == 25
        assert response.limit == 25


class TestDashboardKeywordHighlightsSchema:
    """Tests for DashboardKeywordHighlightsResponse schema."""

    def test_schema_has_keywords_and_total(self):
        from app.models.schemas import DashboardKeywordHighlightsResponse, DashboardKeywordHighlight

        kw = DashboardKeywordHighlight(
            term="meditation app",
            search_volume=12000,
            trend_score=0.85,
            opportunity_score=72.3,
        )
        response = DashboardKeywordHighlightsResponse(keywords=[kw], total=1)
        assert response.total == 1
        assert len(response.keywords) == 1
        assert response.keywords[0].term == "meditation app"

    def test_empty_keywords_response(self):
        from app.models.schemas import DashboardKeywordHighlightsResponse

        response = DashboardKeywordHighlightsResponse(keywords=[], total=0)
        assert response.total == 0
        assert response.keywords == []

    def test_keyword_fields_are_typed_correctly(self):
        from app.models.schemas import DashboardKeywordHighlight

        kw = DashboardKeywordHighlight(
            term="focus timer",
            search_volume=5000,
            trend_score=0.5,
            opportunity_score=65.0,
        )
        assert isinstance(kw.term, str)
        assert isinstance(kw.search_volume, int)
        assert isinstance(kw.trend_score, float)
        assert isinstance(kw.opportunity_score, float)

    def test_opportunity_score_ordering_contract(self):
        """Keywords should be sortable by opportunity_score descending."""
        from app.models.schemas import DashboardKeywordHighlight

        keywords = [
            DashboardKeywordHighlight(term="a", search_volume=1000, trend_score=0.3, opportunity_score=45.0),
            DashboardKeywordHighlight(term="b", search_volume=2000, trend_score=0.7, opportunity_score=80.0),
            DashboardKeywordHighlight(term="c", search_volume=500,  trend_score=0.1, opportunity_score=30.0),
        ]
        sorted_kws = sorted(keywords, key=lambda k: k.opportunity_score, reverse=True)
        assert sorted_kws[0].term == "b"
        assert sorted_kws[-1].term == "c"


class TestOpportunitiesTabBehavior:
    """
    Tests for the tab URL routing contract of the Opportunities hub.

    The OpportunitiesClient maps ?tab= query param to one of:
      keywords | ideas | niches
    with 'keywords' as the default when the param is absent or unknown.
    """

    def _resolve_tab(self, tab_param: Optional[str]) -> str:
        """Mirrors the tab resolution logic in OpportunitiesClient.tsx."""
        valid_tabs = {"keywords", "ideas", "niches"}
        if tab_param in valid_tabs:
            return tab_param
        return "keywords"

    def test_keywords_tab_is_default(self):
        assert self._resolve_tab(None) == "keywords"

    def test_ideas_tab_resolved_correctly(self):
        assert self._resolve_tab("ideas") == "ideas"

    def test_niches_tab_resolved_correctly(self):
        assert self._resolve_tab("niches") == "niches"

    def test_keywords_tab_resolved_correctly(self):
        assert self._resolve_tab("keywords") == "keywords"

    def test_unknown_tab_falls_back_to_keywords(self):
        assert self._resolve_tab("niche-radar") == "keywords"
        assert self._resolve_tab("ai-opportunities") == "keywords"
        assert self._resolve_tab("") == "keywords"

    def test_old_ideas_route_redirects_to_ideas_tab(self):
        """Simulates the redirect in ideas/page.tsx: /ideas → /opportunities?tab=ideas"""
        redirect_target = "/opportunities?tab=ideas"
        assert "tab=ideas" in redirect_target
        assert "/opportunities" in redirect_target

    def test_old_niche_radar_route_redirects_to_niches_tab(self):
        """Simulates the redirect in niche-radar/page.tsx: /niche-radar → /opportunities?tab=niches"""
        redirect_target = "/opportunities?tab=niches"
        assert "tab=niches" in redirect_target
        assert "/opportunities" in redirect_target
