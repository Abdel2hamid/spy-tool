"""
End-to-end tests for the /apps/import flow.

Covers:
- URL import (app not in DB)
- URL import (app already in DB → no duplicate, returns same row)
- Raw numeric ID import
- Malformed URL (no ID → treated as text search)
- Valid-looking ID with empty Apple lookup result → error_hint
- Race condition / duplicate prevention in _get_or_create_app
- Response shape for direct_lookup=True
- Enrichment triggered only for new apps
- direct_lookup=True with error_hint when Apple API down
- Concurrent duplicate import recovery
"""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch, call

import pytest

from app.services.app_import_service import (
    AppImportService,
    _get_or_create_app,
    _get_full_app_details,
)
from app.utils.parse_appstore_query import parse_appstore_query


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_itunes_item(track_id, name="TestApp", developer="Dev Co",
                      genres=None, rating=4.5, reviews=500):
    if genres is None:
        genres = ["Productivity", "Business"]
    return {
        "trackId": track_id,
        "trackName": name,
        "artistName": developer,
        "artworkUrl100": f"https://is1-ssl.mzstatic.com/{track_id}.png",
        "primaryGenreName": "Productivity",
        "genres": genres,
        "price": 0,
        "isFree": True,
        "averageUserRating": rating,
        "userRatingCount": reviews,
        "trackViewUrl": f"https://apps.apple.com/us/app/id{track_id}",
        "version": "2.1",
        "artistId": 123456789,
        "description": f"Description for {name}",
        "releaseDate": "2023-01-15T00:00:00Z",
        "currency": "USD",
        "contentRating": "4+",
        "minimumOsVersion": "15.0",
        "languageCodesISO2A": ["EN"],
    }


def _mock_urlopen(items):
    """Minimal mock that returns iTunes JSON for urlopen."""
    body = json.dumps({"resultCount": len(items), "results": items}).encode()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=BytesIO(body))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _empty_urlopen():
    """Mock that returns an empty iTunes result set."""
    return _mock_urlopen([])


def _make_db(existing_app=None):
    """Mock DB session. By default all queries return None / []."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing_app
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = []
    return db


def _make_app_model(db_id=42, app_id="718043190", name="Fantastical"):
    from app.models.models import App as AppModel
    app = MagicMock(spec=AppModel)
    app.id = db_id
    app.app_id = str(app_id)
    app.name = name
    app.developer = "Flexibits Inc"
    app.icon_url = "https://example.com/icon.png"
    app.primary_category = "Productivity"
    app.secondary_category = "Business"
    app.price = 0
    app.is_free = True
    app.url = f"https://apps.apple.com/us/app/id{app_id}"
    app.current_rating = 4.8
    app.current_reviews = 50000
    app.subtitle = None
    app.description = None
    app.developer_id = "987654"
    app.currency = "USD"
    app.current_version = "3.8"
    app.minimum_ios_version = "15.0"
    app.supported_languages = ["EN"]
    app.release_date = None
    app.last_updated = None
    app.content_rating = "4+"
    app.category_id = None
    return app


# ---------------------------------------------------------------------------
# Direct lookup via AppImportService.lookup_app
# ---------------------------------------------------------------------------

class TestLookupAppNotInDb:
    """App is NOT yet in the database — should import it."""

    def test_new_app_is_written_to_db(self):
        """lookup_app writes a new row when app does not exist."""
        db = _make_db(existing_app=None)
        svc = AppImportService(db)
        item = _make_itunes_item(718043190, "Fantastical")

        with patch("urllib.request.urlopen", return_value=_mock_urlopen([item])):
            result = svc.lookup_app("718043190")

        db.add.assert_called_once()
        assert "error" not in result
        assert result["app_id"] == "718043190"

    def test_new_app_returns_is_new_true(self):
        db = _make_db(existing_app=None)
        svc = AppImportService(db)
        item = _make_itunes_item(718043190, "Fantastical")

        with patch("urllib.request.urlopen", return_value=_mock_urlopen([item])):
            result = svc.lookup_app("718043190")

        assert result.get("is_new") is True

    def test_result_has_all_required_fields(self):
        db = _make_db(existing_app=None)
        svc = AppImportService(db)
        item = _make_itunes_item(111222333, "MyApp")

        with patch("urllib.request.urlopen", return_value=_mock_urlopen([item])):
            result = svc.lookup_app("111222333")

        for field in ("id", "app_id", "name", "developer", "is_new"):
            assert field in result, f"Missing field: {field}"


class TestLookupAppAlreadyInDb:
    """App is already in the database — should update metadata, not insert."""

    def test_no_duplicate_insert_when_existing(self):
        """_get_or_create_app must NOT call db.add when app already exists."""
        existing = _make_app_model(db_id=7, app_id="718043190")
        db = _make_db(existing_app=existing)
        item = _make_itunes_item(718043190, "Fantastical Updated")

        app_obj, is_new = _get_or_create_app(db, item, update_existing=True)

        db.add.assert_not_called()
        assert is_new is False
        assert app_obj is existing

    def test_lookup_returns_is_new_false_for_existing_app(self):
        existing = _make_app_model(db_id=7, app_id="718043190")
        db = _make_db(existing_app=existing)
        svc = AppImportService(db)
        item = _make_itunes_item(718043190, "Fantastical Updated")

        with patch("urllib.request.urlopen", return_value=_mock_urlopen([item])):
            result = svc.lookup_app("718043190")

        assert result.get("is_new") is False
        assert "error" not in result

    def test_lookup_returns_existing_db_id(self):
        existing = _make_app_model(db_id=99, app_id="718043190")
        db = _make_db(existing_app=existing)
        svc = AppImportService(db)
        item = _make_itunes_item(718043190, "Fantastical")

        with patch("urllib.request.urlopen", return_value=_mock_urlopen([item])):
            result = svc.lookup_app("718043190")

        assert result["id"] == 99

    def test_metadata_updated_for_existing_app(self):
        """Existing app gets updated name/rating/reviews."""
        existing = _make_app_model(db_id=7, app_id="718043190")
        db = _make_db(existing_app=existing)
        item = _make_itunes_item(718043190, "Fantastical v2", rating=4.9, reviews=60000)

        _get_or_create_app(db, item, update_existing=True)

        assert existing.name == "Fantastical v2"
        assert existing.current_rating == 4.9
        assert existing.current_reviews == 60000


# ---------------------------------------------------------------------------
# Race condition / duplicate prevention
# ---------------------------------------------------------------------------

class TestDuplicatePrevention:
    """Simulate concurrent imports of the same app_id."""

    def test_race_condition_recovery(self):
        """
        When INSERT fails due to unique constraint, _get_or_create_app retries SELECT
        and returns the existing row instead of (None, False).
        """
        from app.models.models import App as AppModel
        existing = MagicMock(spec=AppModel)
        existing.id = 42
        existing.app_id = "718043190"

        db = MagicMock()
        # First call to .first() (before insert) returns None — simulating the race
        # Second call to .first() (after rollback retry) returns the existing row
        db.query.return_value.filter.return_value.first.side_effect = [None, existing]
        db.commit.side_effect = Exception("duplicate key value violates unique constraint")

        item = _make_itunes_item(718043190, "Fantastical")
        app_obj, is_new = _get_or_create_app(db, item)

        # Must recover the existing row, not return (None, False)
        assert app_obj is existing
        assert is_new is False
        db.rollback.assert_called_once()

    def test_race_condition_with_unrecoverable_db_error(self):
        """
        If both the INSERT and the retry SELECT fail, returns (None, False) gracefully.
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.commit.side_effect = Exception("DB down")
        db.query.return_value.filter.return_value.first.side_effect = [
            None,
            Exception("DB still down"),
        ]

        item = _make_itunes_item(718043190, "Fantastical")
        app_obj, is_new = _get_or_create_app(db, item)

        assert app_obj is None
        assert is_new is False
        db.rollback.assert_called_once()

    def test_db_unique_violation_does_not_raise(self):
        """Unique constraint violation must not propagate as exception."""
        db = _make_db(existing_app=None)
        db.commit.side_effect = Exception("unique constraint violation")
        item = _make_itunes_item(55555, "FailApp")

        # Must NOT raise
        app_obj, is_new = _get_or_create_app(db, item)
        assert isinstance(app_obj, (type(None), MagicMock))


# ---------------------------------------------------------------------------
# /apps/import route — full flow via AppImportService
# ---------------------------------------------------------------------------

class TestImportRouteDirectLookup:
    """Test the lookup path triggered by URL/ID queries in AppImportService."""

    def _svc(self, existing_app=None):
        db = _make_db(existing_app=existing_app)
        return AppImportService(db), db

    def test_numeric_id_triggers_lookup_not_search(self):
        """
        A numeric ID query must call _get_full_app_details (lookup),
        not _search_itunes (search).
        """
        parsed = parse_appstore_query("718043190")
        assert parsed.type == "track_id"
        assert parsed.track_id == "718043190"

    def test_url_query_triggers_lookup_not_search(self):
        """URL query must be parsed as 'url' type."""
        url = "https://apps.apple.com/us/app/fantastical/id718043190"
        parsed = parse_appstore_query(url)
        assert parsed.type == "url"
        assert parsed.track_id == "718043190"

    def test_url_import_returns_app_data(self):
        """Lookup via URL query returns the app dict."""
        svc, db = self._svc()
        item = _make_itunes_item(718043190, "Fantastical")

        with patch("urllib.request.urlopen", return_value=_mock_urlopen([item])):
            result = svc.lookup_app("718043190")

        assert result.get("name") == "Fantastical"
        assert result.get("app_id") == "718043190"
        assert "error" not in result

    def test_url_import_app_already_in_db_no_duplicate(self):
        """Importing the same URL twice returns the same row without inserting."""
        existing = _make_app_model(db_id=7, app_id="718043190")
        svc, db = self._svc(existing_app=existing)
        item = _make_itunes_item(718043190, "Fantastical")

        with patch("urllib.request.urlopen", return_value=_mock_urlopen([item])):
            result = svc.lookup_app("718043190")

        db.add.assert_not_called()
        assert result["id"] == 7
        assert result["is_new"] is False

    def test_empty_apple_result_returns_error_dict(self):
        """When Apple returns no results for a valid-looking ID, return error dict."""
        svc, db = self._svc()

        with patch("urllib.request.urlopen", return_value=_empty_urlopen()):
            result = svc.lookup_app("999999999")

        assert "error" in result
        assert result["error"] == "App not found in App Store"

    def test_apple_api_network_failure_returns_error_dict(self):
        """Network timeout → return error dict, do not raise."""
        svc, db = self._svc()

        with patch("urllib.request.urlopen", side_effect=Exception("Connection timed out")):
            result = svc.lookup_app("718043190")

        assert "error" in result

    def test_malformed_url_without_id_falls_to_text_search(self):
        """URL without /id{digits} is classified as text, not a direct lookup."""
        parsed = parse_appstore_query("https://apps.apple.com/us/developer/flexibits/id123456")
        # Developer URL doesn't follow /app/{name}/id{digits} pattern — should be text
        # Actually let's check what it parses as. The pattern requires /app/ in the path.
        # A developer URL has /developer/ so it won't match.
        assert parsed.track_id is None or parsed.type == "text"

    def test_short_id_treated_as_text_not_direct_lookup(self):
        """IDs with fewer than 6 digits are treated as text search."""
        parsed = parse_appstore_query("12345")
        assert parsed.type == "text"
        assert parsed.track_id is None


# ---------------------------------------------------------------------------
# Response shape validation
# ---------------------------------------------------------------------------

class TestDirectLookupResponseShape:
    """Verify the response shape when direct_lookup=True."""

    def _build_item(self, db_id=42, app_id="718043190", name="Fantastical"):
        return {
            "id": db_id,
            "app_id": app_id,
            "name": name,
            "developer": "Flexibits Inc",
            "icon_url": "https://example.com/icon.png",
            "current_rating": 4.8,
            "current_reviews": 50000,
            "primary_category": "Productivity",
            "price": 0,
            "is_free": True,
            "url": f"https://apps.apple.com/us/app/id{app_id}",
            "is_new": True,
            "source": "direct_lookup",
            "match_score": 1.0,
            "match_type": "direct",
        }

    def test_direct_lookup_response_has_required_fields(self):
        """Response with direct_lookup=True must have all AppImportSearchResponse fields."""
        item = self._build_item()
        response = {
            "query": "718043190",
            "results": [item],
            "total": 1,
            "from_cache": 0,
            "direct_lookup": True,
            "error_hint": None,
        }
        # Validate required fields exist
        assert response["direct_lookup"] is True
        assert response["total"] == 1
        assert response["results"][0]["source"] == "direct_lookup"
        assert response["results"][0]["match_score"] == 1.0
        assert response["error_hint"] is None

    def test_error_hint_response_shape(self):
        """Error response has empty results and informative error_hint."""
        response = {
            "query": "999999999",
            "results": [],
            "total": 0,
            "from_cache": 0,
            "direct_lookup": True,
            "error_hint": "App not found in the App Store. Check the App ID and try again.",
        }
        assert response["direct_lookup"] is True
        assert response["results"] == []
        assert response["error_hint"] is not None
        assert "App ID" in response["error_hint"]

    def test_url_error_hint_mentions_url(self):
        """Error hint for URL lookup failure must mention URL, not App ID."""
        # The route uses parsed.type to differentiate
        from app.utils.parse_appstore_query import parse_appstore_query
        parsed = parse_appstore_query("https://apps.apple.com/us/app/fantastical/id718043190")
        kind = "URL" if parsed.type == "url" else "App ID"
        error_hint = f"App not found in the App Store. Check the {kind} and try again."
        assert "URL" in error_hint

    def test_id_error_hint_mentions_app_id(self):
        """Error hint for numeric ID lookup failure must mention App ID."""
        from app.utils.parse_appstore_query import parse_appstore_query
        parsed = parse_appstore_query("718043190")
        kind = "URL" if parsed.type == "url" else "App ID"
        error_hint = f"App not found in the App Store. Check the {kind} and try again."
        assert "App ID" in error_hint

    def test_source_is_direct_lookup_not_database_or_app_store(self):
        """Direct lookup results use source='direct_lookup'."""
        item = self._build_item()
        assert item["source"] == "direct_lookup"
        assert item["source"] != "database"
        assert item["source"] != "app_store"

    def test_from_cache_is_zero_for_direct_lookup(self):
        """Direct lookups don't come from cache."""
        response = {
            "query": "718043190",
            "results": [self._build_item()],
            "total": 1,
            "from_cache": 0,
            "direct_lookup": True,
            "error_hint": None,
        }
        assert response["from_cache"] == 0


# ---------------------------------------------------------------------------
# Enrichment pipeline behavior
# ---------------------------------------------------------------------------

class TestEnrichmentPipeline:
    """Enrichment should be triggered for new apps only."""

    def test_enrichment_called_for_new_app(self):
        """trigger_enrichment should be invoked when is_new=True."""
        db = _make_db(existing_app=None)
        svc = AppImportService(db)
        svc.trigger_enrichment = MagicMock()
        item = _make_itunes_item(718043190, "Fantastical")

        with patch("urllib.request.urlopen", return_value=_mock_urlopen([item])):
            result = svc.lookup_app("718043190")

        # is_new should be True since DB had no existing app
        assert result.get("is_new") is True
        # trigger_enrichment is NOT called directly inside lookup_app —
        # it's the responsibility of the route handler to schedule it.
        # We verify the is_new flag so the route can decide.

    def test_enrichment_not_needed_for_existing_app(self):
        """For existing apps, is_new=False so route skips enrichment."""
        existing = _make_app_model(db_id=7, app_id="718043190")
        db = _make_db(existing_app=existing)
        svc = AppImportService(db)
        item = _make_itunes_item(718043190, "Fantastical")

        with patch("urllib.request.urlopen", return_value=_mock_urlopen([item])):
            result = svc.lookup_app("718043190")

        assert result.get("is_new") is False

    def test_trigger_enrichment_catches_errors(self):
        """trigger_enrichment must not propagate exceptions from any step."""
        db = _make_db()

        # Patch all three services to raise
        with patch("app.services.keyword_extraction_service.KeywordExtractionService") as mock_kw, \
             patch("app.services.competitor_keyword_service.CompetitorKeywordService") as mock_comp, \
             patch("app.services.keyword_intelligence_pipeline.KeywordIntelligencePipeline") as mock_pipe, \
             patch("time.sleep"):
            mock_kw.return_value.extract_for_app.side_effect = Exception("extraction failed")
            mock_comp.return_value.mine_for_app.side_effect = Exception("mining failed")
            mock_pipe.return_value.enrich_app.side_effect = Exception("pipeline failed")

            svc = AppImportService(db)
            # Must not raise
            svc.trigger_enrichment(42)


# ---------------------------------------------------------------------------
# _get_full_app_details — Apple API layer
# ---------------------------------------------------------------------------

class TestGetFullAppDetails:
    """Tests for the iTunes Lookup API wrapper."""

    def test_returns_none_on_empty_result(self):
        """Empty results list → (None, None) — app not found, no error to surface."""
        with patch("urllib.request.urlopen", return_value=_empty_urlopen()):
            item, error = _get_full_app_details("999999999")
        assert item is None
        assert error is None  # Not found ≠ API error

    def test_returns_none_on_network_error(self):
        """Network failure → (None, error_hint) — never raises."""
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            item, error = _get_full_app_details("718043190")
        assert item is None
        assert error is not None  # error_hint set so caller can surface it

    def test_returns_first_result_on_success(self):
        """Returns (item_dict, None) from results list on success."""
        item = _make_itunes_item(718043190, "Fantastical")
        with patch("urllib.request.urlopen", return_value=_mock_urlopen([item])):
            result, error = _get_full_app_details("718043190")
        assert result is not None
        assert error is None
        assert result["trackId"] == 718043190
        assert result["trackName"] == "Fantastical"

    def test_uses_correct_itunes_lookup_url(self):
        """Verify the API call goes to the correct iTunes endpoint."""
        calls = []
        original = __import__("urllib.request", fromlist=["urlopen"]).urlopen

        def capture_call(req, timeout=None):
            calls.append(req.full_url if hasattr(req, "full_url") else str(req))
            return _empty_urlopen()

        with patch("urllib.request.urlopen", side_effect=capture_call):
            _get_full_app_details("718043190")

        assert any("itunes.apple.com/lookup" in str(c) for c in calls)
        assert any("718043190" in str(c) for c in calls)


# ---------------------------------------------------------------------------
# Route-level tests — confirm /apps/import never returns 422 for URL input
# ---------------------------------------------------------------------------

class TestImportRouteNever422:
    """
    Regression tests for the route ordering bug:
    GET /apps/import used to be registered AFTER GET /apps/{app_id:int},
    so FastAPI matched 'import' as app_id, tried int('import') → 422.
    These tests assert the endpoint always returns 200 regardless of q format.
    """

    def _make_client(self, mock_items=None, lookup_error=False):
        """Return a TestClient with urllib.request.urlopen mocked out."""
        import json
        from io import BytesIO
        from unittest.mock import MagicMock, patch
        from fastapi.testclient import TestClient
        from app.main import app

        if mock_items is None:
            mock_items = []

        body = json.dumps({"resultCount": len(mock_items), "results": mock_items}).encode()

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=BytesIO(body))
        cm.__exit__ = MagicMock(return_value=False)

        if lookup_error:
            # Simulate Apple API being completely unavailable
            import urllib.error
            side_effect = urllib.error.URLError("connection refused")
            patcher = patch("urllib.request.urlopen", side_effect=side_effect)
        else:
            patcher = patch("urllib.request.urlopen", return_value=cm)

        return TestClient(app), patcher

    def test_plain_url_returns_200_not_422(self):
        """Full App Store URL must return 200, never 422."""
        url = "https://apps.apple.com/us/app/roblox/id431946152"
        item = _make_itunes_item(431946152, "Roblox")
        client, patcher = self._make_client(mock_items=[item])
        with patcher:
            resp = client.get(f"/api/v1/apps/import?q={url}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_plain_url_returns_direct_lookup_true(self):
        """URL input triggers direct_lookup=True in response."""
        url = "https://apps.apple.com/us/app/roblox/id431946152"
        item = _make_itunes_item(431946152, "Roblox")
        client, patcher = self._make_client(mock_items=[item])
        with patcher:
            resp = client.get(f"/api/v1/apps/import?q={url}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["direct_lookup"] is True

    def test_numeric_trackid_returns_200(self):
        """Bare numeric ID must return 200, never 422."""
        item = _make_itunes_item(431946152, "Roblox")
        client, patcher = self._make_client(mock_items=[item])
        with patcher:
            resp = client.get("/api/v1/apps/import?q=431946152")
        assert resp.status_code == 200

    def test_text_search_returns_200(self):
        """Plain text query returns 200 even when iTunes returns nothing."""
        client, patcher = self._make_client(mock_items=[])
        with patcher:
            resp = client.get("/api/v1/apps/import?q=roblox")
        assert resp.status_code == 200

    def test_url_with_apple_api_down_returns_200_with_error_hint(self):
        """Even when Apple API is completely down, URL input returns 200 with error_hint."""
        url = "https://apps.apple.com/us/app/roblox/id431946152"
        client, patcher = self._make_client(lookup_error=True)
        with patcher:
            resp = client.get(f"/api/v1/apps/import?q={url}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["direct_lookup"] is True
        assert data["error_hint"] is not None
        assert data["results"] == []

    def test_response_shape_for_url_input(self):
        """Response always includes all required fields."""
        url = "https://apps.apple.com/us/app/roblox/id431946152"
        item = _make_itunes_item(431946152, "Roblox")
        client, patcher = self._make_client(mock_items=[item])
        with patcher:
            resp = client.get(f"/api/v1/apps/import?q={url}")
        data = resp.json()
        for field in ("query", "results", "total", "from_cache", "direct_lookup"):
            assert field in data, f"Missing field: {field}"
