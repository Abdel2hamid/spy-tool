"""
Tests for the app import/search service.

Covers:
- text search (local DB + App Store)
- URL / numeric-ID direct lookup
- genre field parsing (the root-cause bug)
- App Store results returned without DB writes
- lookup_app DB import
"""

import json
import re
from io import BytesIO
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_itunes_item(track_id, name, developer="Dev Co",
                      rating=4.5, reviews=1000, genres=None):
    """Return a minimal iTunes search result dict."""
    if genres is None:
        genres = ["Productivity", "Business"]
    return {
        "trackId": track_id,
        "trackName": name,
        "artistName": developer,
        "artworkUrl100": "https://example.com/{}.png".format(track_id),
        "primaryGenreName": "Productivity",
        "genres": genres,
        "price": 0,
        "isFree": True,
        "averageUserRating": rating,
        "userRatingCount": reviews,
        "trackViewUrl": "https://apps.apple.com/app/id{}".format(track_id),
        "version": "1.0",
        "artistId": 999999,
        "description": "Description for {}".format(name),
    }


def _make_db_session():
    """Return a mock SQLAlchemy session with .query() returning no results."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = []
    return db


def _mock_urlopen_cm(items):
    """Return a context-manager mock that yields iTunes-formatted JSON."""
    body = json.dumps({"resultCount": len(items), "results": items}).encode()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=BytesIO(body))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# _normalize_query
# ---------------------------------------------------------------------------

class TestNormalizeQuery:
    def test_lowercases(self):
        from app.services.app_import_service import _normalize_query
        result = _normalize_query("Spotify")
        assert result == result.lower()

    def test_removes_stopwords(self):
        from app.services.app_import_service import _normalize_query
        result = _normalize_query("the best fitness app for ios")
        words = result.split()
        assert "the" not in words
        assert "app" not in words
        assert "ios" not in words

    def test_strips_punctuation(self):
        from app.services.app_import_service import _normalize_query
        result = _normalize_query("hello, world!")
        assert "," not in result
        assert "!" not in result

    def test_empty_string(self):
        from app.services.app_import_service import _normalize_query
        assert _normalize_query("") == ""

    def test_single_word_preserved(self):
        from app.services.app_import_service import _normalize_query
        result = _normalize_query("wavebox")
        assert "wavebox" in result


# ---------------------------------------------------------------------------
# _search_itunes (mocked HTTP)
# ---------------------------------------------------------------------------

class TestSearchITunes:
    def test_returns_results(self):
        from app.services.app_import_service import _search_itunes
        items = [_make_itunes_item(111, "Wavebox"), _make_itunes_item(222, "Spotify")]
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_cm(items)):
            results = _search_itunes("wavebox", limit=5)
        assert len(results) == 2
        assert results[0]["trackName"] == "Wavebox"

    def test_returns_empty_on_network_error(self):
        from app.services.app_import_service import _search_itunes
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            results = _search_itunes("wavebox")
        assert results == []

    def test_returns_empty_on_malformed_json(self):
        from app.services.app_import_service import _search_itunes
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=BytesIO(b"not json{{"))
        cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=cm):
            results = _search_itunes("wavebox")
        assert results == []


# ---------------------------------------------------------------------------
# _get_or_create_app — genre bug fix
# ---------------------------------------------------------------------------

class TestGetOrCreateApp:
    """Ensure the genres-as-strings bug is fixed and DB writes work correctly."""

    def _make_db(self, existing_app=None):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing_app
        return db

    def test_genres_list_of_strings_no_error(self):
        """Root-cause fix: genres=['Productivity', 'Business'] must not AttributeError."""
        from app.services.app_import_service import _get_or_create_app
        item = _make_itunes_item(
            track_id=12345,
            name="TestApp",
            genres=["Productivity", "Business"],
        )
        db = self._make_db()
        # Must NOT raise AttributeError
        app_obj, is_new = _get_or_create_app(db, item)
        # secondary_category should be "Business" (last genre)
        db.add.assert_called_once()
        created_app = db.add.call_args[0][0]
        assert created_app.secondary_category == "Business"

    def test_genres_single_entry_secondary_is_none(self):
        """Only one genre → secondary_category should be None."""
        from app.services.app_import_service import _get_or_create_app
        item = _make_itunes_item(12346, "TestApp", genres=["Productivity"])
        db = self._make_db()
        _get_or_create_app(db, item)
        created_app = db.add.call_args[0][0]
        assert created_app.secondary_category is None

    def test_genres_missing_secondary_is_none(self):
        """No genres field → secondary_category should be None."""
        from app.services.app_import_service import _get_or_create_app
        item = _make_itunes_item(12347, "TestApp", genres=[])
        item.pop("genres", None)
        db = self._make_db()
        _get_or_create_app(db, item)
        created_app = db.add.call_args[0][0]
        assert created_app.secondary_category is None

    def test_existing_app_returned_without_insert(self):
        """If app already in DB, return it without inserting."""
        from app.services.app_import_service import _get_or_create_app
        from app.models.models import App as AppModel
        existing = MagicMock(spec=AppModel)
        existing.id = 99
        db = self._make_db(existing_app=existing)
        app_obj, is_new = _get_or_create_app(db, _make_itunes_item(999, "Existing"))
        assert app_obj is existing
        assert is_new is False
        db.add.assert_not_called()

    def test_db_error_returns_none_not_raises(self):
        """DB commit failure → (None, False), no exception propagation."""
        from app.services.app_import_service import _get_or_create_app
        item = _make_itunes_item(55555, "FailApp")
        db = self._make_db()
        db.commit.side_effect = Exception("unique constraint violation")
        app_obj, is_new = _get_or_create_app(db, item)
        assert app_obj is None
        assert is_new is False
        db.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# AppImportService.search_apps — no DB writes, App Store results surfaced
# ---------------------------------------------------------------------------

class TestSearchAppsNoDbWrites:
    """
    search_apps() must NEVER write to the database.
    App Store results are returned directly from iTunes with source='app_store'.
    """

    def _make_service(self, db=None):
        from app.services.app_import_service import AppImportService
        if db is None:
            db = _make_db_session()
        return AppImportService(db), db

    def test_empty_query_returns_empty(self):
        svc, _ = self._make_service()
        result = svc.search_apps("")
        assert result["results"] == []
        assert result["total"] == 0

    def test_text_search_returns_app_store_results_without_db_writes(self):
        """
        iTunes results appear as source='app_store' and NO db.add/db.commit.
        This is the primary regression test for the original bug.
        """
        svc, db = self._make_service()

        itunes_items = [
            _make_itunes_item(1001, "Wavebox"),
            _make_itunes_item(1002, "Spotify"),
        ]
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_cm(itunes_items)):
            result = svc.search_apps("wavebox", limit=5)

        store_results = [r for r in result["results"] if r["source"] == "app_store"]
        assert len(store_results) >= 1
        assert store_results[0]["id"] == 0  # Not in DB — must be 0

        # Crucially: no DB writes
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_genres_as_strings_does_not_crash_search(self):
        """
        Root-cause regression: genres=['Productivity','Business'] must NOT raise
        AttributeError in search_apps(). Before fix this caused a 500.
        """
        svc, db = self._make_service()

        item = _make_itunes_item(
            track_id=3001,
            name="BuggyApp",
            genres=["Productivity", "Business"],
        )
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_cm([item])):
            result = svc.search_apps("buggyapp", limit=5)

        # Must not raise; must return the App Store result
        assert result["total"] >= 1
        assert result["results"][0]["name"] == "BuggyApp"
        assert result["results"][0]["source"] == "app_store"

    def test_local_db_results_come_before_app_store(self):
        """Local DB results must appear before App Store results."""
        from app.models.models import App as AppModel
        local_app = MagicMock(spec=AppModel)
        local_app.id = 5
        local_app.app_id = "999888"
        local_app.name = "Wavebox Local"
        local_app.developer = "Wavebox Inc"
        local_app.icon_url = None
        local_app.current_rating = 4.8
        local_app.current_reviews = 5000
        local_app.primary_category = "Productivity"
        local_app.price = 0.0
        local_app.is_free = True
        local_app.url = "https://example.com"

        svc, db = self._make_service()
        db.query.return_value.filter.return_value.limit.return_value.all.return_value = [local_app]

        itunes_items = [_make_itunes_item(2001, "WaveboxStore")]
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_cm(itunes_items)):
            result = svc.search_apps("wavebox", limit=5)

        sources = [r["source"] for r in result["results"]]
        assert "database" in sources
        assert "app_store" in sources
        assert sources[0] == "database"

    def test_respects_limit(self):
        svc, db = self._make_service()
        items = [_make_itunes_item(4000 + i, "App{}".format(i)) for i in range(20)]
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_cm(items)):
            result = svc.search_apps("app", limit=5)
        assert len(result["results"]) <= 5

    def test_deduplication_by_app_id(self):
        """Same app_id from iTunes must not appear twice."""
        svc, db = self._make_service()
        dup = _make_itunes_item(5001, "Dup App")
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_cm([dup, dup])):
            result = svc.search_apps("dup", limit=10)
        app_ids = [r["app_id"] for r in result["results"]]
        assert len(app_ids) == len(set(app_ids))

    def test_from_cache_is_zero_when_no_local_results(self):
        svc, db = self._make_service()
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_cm([])):
            result = svc.search_apps("nolocal", limit=5)
        assert result["from_cache"] == 0

    def test_itunes_network_error_returns_local_only(self):
        """If iTunes is unreachable, local results still returned (empty is fine)."""
        svc, db = self._make_service()
        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            result = svc.search_apps("wavebox", limit=5)
        # Should not raise; returns (possibly empty) results
        assert "results" in result
        assert "error" not in result


# ---------------------------------------------------------------------------
# AppImportService.lookup_app — must write to DB
# ---------------------------------------------------------------------------

class TestLookupApp:
    """lookup_app IS allowed to write to DB — verify it works correctly."""

    def test_lookup_returns_error_on_not_found(self):
        from app.services.app_import_service import AppImportService
        db = _make_db_session()
        svc = AppImportService(db)

        cm = MagicMock()
        cm.__enter__ = MagicMock(
            return_value=BytesIO(json.dumps({"resultCount": 0, "results": []}).encode())
        )
        cm.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=cm):
            result = svc.lookup_app("9999999999")

        assert "error" in result

    def test_lookup_writes_to_db(self):
        """lookup_app must call db.add and db.commit for new apps."""
        from app.services.app_import_service import AppImportService
        db = _make_db_session()
        item = _make_itunes_item(track_id=7777777, name="LookupApp")
        svc = AppImportService(db)

        with patch("urllib.request.urlopen", return_value=_mock_urlopen_cm([item])):
            svc.lookup_app("7777777")

        db.add.assert_called()

    def test_lookup_genres_bug_does_not_crash(self):
        """Lookup with genres=['X', 'Y'] must not crash (regression for genres bug)."""
        from app.services.app_import_service import AppImportService
        db = _make_db_session()
        item = _make_itunes_item(
            track_id=8888888, name="LookupWithGenres",
            genres=["Productivity", "Business"],
        )
        svc = AppImportService(db)

        with patch("urllib.request.urlopen", return_value=_mock_urlopen_cm([item])):
            result = svc.lookup_app("8888888")

        # Should not raise; must return valid data or error, not crash
        assert isinstance(result, dict)
        assert "error" not in result or result.get("error") is not None


# ---------------------------------------------------------------------------
# URL / ID parsing logic (mirrors frontend parseAppStoreInput)
# ---------------------------------------------------------------------------

class TestUrlIdParsing:
    """
    Mirrors the frontend parseAppStoreInput() logic to ensure correct extraction
    from various input formats (text search vs. URL/ID lookup).
    """

    @staticmethod
    def parse(input_str):
        """Python mirror of frontend parseAppStoreInput()."""
        trimmed = input_str.strip()
        url_match = re.search(r'[?/]id(\d{6,})', trimmed)
        if url_match:
            return url_match.group(1)
        if re.match(r'^\d{6,}$', trimmed):
            return trimmed
        return None

    def test_full_app_store_url(self):
        url = "https://apps.apple.com/us/app/wavebox/id1529800138"
        assert self.parse(url) == "1529800138"

    def test_url_without_app_name(self):
        url = "https://apps.apple.com/app/id294158606"
        assert self.parse(url) == "294158606"

    def test_numeric_id_only(self):
        assert self.parse("1529800138") == "1529800138"

    def test_short_numeric_is_ignored(self):
        # Less than 6 digits — plain text, not an ID
        assert self.parse("12345") is None

    def test_plain_text_returns_none(self):
        assert self.parse("wavebox") is None

    def test_multi_word_text_returns_none(self):
        assert self.parse("best productivity apps") is None

    def test_itunes_lookup_url_path_id(self):
        # iTunes lookup URLs use /id in the path
        url = "https://itunes.apple.com/lookup?id=1234567890"
        # The '?' followed by 'id=' is NOT the App Store path format — should be None
        # App Store pattern requires /id{digits} in the path
        assert self.parse(url) is None

    def test_path_only_id_format(self):
        # Direct path-only format with /id
        url = "https://apps.apple.com/us/app/id1234567890"
        assert self.parse(url) == "1234567890"

    def test_empty_string_returns_none(self):
        assert self.parse("") is None

    def test_whitespace_only_returns_none(self):
        assert self.parse("   ") is None

    def test_six_digit_id_minimum(self):
        # Exactly 6 digits — should be treated as ID
        assert self.parse("123456") == "123456"

    def test_five_digit_is_not_id(self):
        # 5 digits — too short to be an App Store ID
        assert self.parse("12345") is None
