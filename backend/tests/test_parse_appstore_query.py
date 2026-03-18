"""
Tests for parse_appstore_query utility.
"""
import pytest
from app.utils.parse_appstore_query import parse_appstore_query, ParsedQuery


# ---------------------------------------------------------------------------
# URL detection
# ---------------------------------------------------------------------------

class TestUrlDetection:
    def test_full_apps_apple_com_url(self):
        url = "https://apps.apple.com/us/app/fantastical-calendar-tasks/id718043190"
        result = parse_appstore_query(url)
        assert result.type == "url"
        assert result.track_id == "718043190"

    def test_apps_apple_com_without_name_segment(self):
        url = "https://apps.apple.com/us/app/id718043190"
        result = parse_appstore_query(url)
        assert result.type == "url"
        assert result.track_id == "718043190"

    def test_apps_apple_com_gb_country(self):
        url = "https://apps.apple.com/gb/app/things-3-for-iphone/id904237743"
        result = parse_appstore_query(url)
        assert result.type == "url"
        assert result.track_id == "904237743"

    def test_itunes_apple_com_url(self):
        url = "https://itunes.apple.com/us/app/my-app/id123456789"
        result = parse_appstore_query(url)
        assert result.type == "url"
        assert result.track_id == "123456789"

    def test_url_without_https_scheme(self):
        url = "apps.apple.com/us/app/fantastical/id718043190"
        result = parse_appstore_query(url)
        assert result.type == "url"
        assert result.track_id == "718043190"

    def test_url_with_query_string(self):
        url = "https://apps.apple.com/us/app/notion/id1232780281?mt=8"
        result = parse_appstore_query(url)
        assert result.type == "url"
        assert result.track_id == "1232780281"

    def test_url_case_insensitive(self):
        url = "HTTPS://APPS.APPLE.COM/US/APP/FANTASTICAL/ID718043190"
        result = parse_appstore_query(url)
        assert result.type == "url"
        assert result.track_id == "718043190"

    def test_url_extracts_correct_id_when_name_has_digits(self):
        # App name contains digits — ensure we match /id{digits} correctly
        url = "https://apps.apple.com/us/app/app-name-123/id456789012"
        result = parse_appstore_query(url)
        assert result.type == "url"
        assert result.track_id == "456789012"


# ---------------------------------------------------------------------------
# Track ID detection
# ---------------------------------------------------------------------------

class TestTrackIdDetection:
    def test_plain_numeric_id(self):
        result = parse_appstore_query("718043190")
        assert result.type == "track_id"
        assert result.track_id == "718043190"

    def test_id_prefixed_slug(self):
        result = parse_appstore_query("id718043190")
        assert result.type == "track_id"
        assert result.track_id == "718043190"

    def test_id_prefix_uppercase(self):
        result = parse_appstore_query("ID718043190")
        assert result.type == "track_id"
        assert result.track_id == "718043190"

    def test_short_numeric_id_6_digits(self):
        result = parse_appstore_query("123456")
        assert result.type == "track_id"
        assert result.track_id == "123456"

    def test_long_numeric_id_13_digits(self):
        result = parse_appstore_query("1234567890123")
        assert result.type == "track_id"
        assert result.track_id == "1234567890123"


# ---------------------------------------------------------------------------
# Text search detection (NOT URL or trackId)
# ---------------------------------------------------------------------------

class TestTextDetection:
    def test_plain_text_keyword(self):
        result = parse_appstore_query("focus timer productivity")
        assert result.type == "text"
        assert result.track_id is None

    def test_app_name_text(self):
        result = parse_appstore_query("Fantastical Calendar")
        assert result.type == "text"
        assert result.track_id is None

    def test_short_id_5_digits_is_text(self):
        # 5 digits is too short to be an Apple trackId
        result = parse_appstore_query("12345")
        assert result.type == "text"
        assert result.track_id is None

    def test_text_with_some_digits(self):
        result = parse_appstore_query("top 10 apps 2024")
        assert result.type == "text"
        assert result.track_id is None

    def test_empty_string(self):
        result = parse_appstore_query("")
        assert result.type == "text"
        assert result.track_id is None

    def test_whitespace_only(self):
        result = parse_appstore_query("   ")
        assert result.type == "text"
        assert result.track_id is None

    def test_id_slug_with_trailing_text_is_text(self):
        # "id718043190 extra" should not match as track_id
        result = parse_appstore_query("id718043190 extra")
        assert result.type == "text"
        assert result.track_id is None

    def test_developer_name_is_text(self):
        result = parse_appstore_query("Flexibits Inc")
        assert result.type == "text"
        assert result.track_id is None


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

class TestReturnType:
    def test_returns_parsed_query_dataclass(self):
        result = parse_appstore_query("718043190")
        assert isinstance(result, ParsedQuery)

    def test_url_type_has_track_id(self):
        result = parse_appstore_query("https://apps.apple.com/us/app/x/id718043190")
        assert result.type == "url"
        assert result.track_id is not None

    def test_text_type_has_no_track_id(self):
        result = parse_appstore_query("fantastical")
        assert result.type == "text"
        assert result.track_id is None
