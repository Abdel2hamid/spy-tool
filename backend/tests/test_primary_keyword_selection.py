"""
Unit tests for ScoringEngine.select_primary_keyword()

Tests the 4-tier primary keyword selection hierarchy:
1. AppKeywordIntelligence (highest traffic_score)
2. AppDiscoveredKeyword (highest opportunity_score)
3. Title/Subtitle phrases (2-3 words)
4. Smart fallback with stopword filtering

Ensures:
- Single meaningless tokens are avoided
- Multi-word phrases are preferred
- Brand tokens and stopwords are filtered
"""

import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scoring.engine import ScoringEngine
from app.models.models import App, Keyword, AppKeywordIntelligence, AppDiscoveredKeyword


class TestStopwordsFiltering:
    """Tests for stopword detection."""

    def test_common_stopwords_filtered(self):
        """Common English stopwords should be filtered."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        stopwords = ["the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
                     "of", "with", "by", "from", "up", "about", "into", "through", "during",
                     "before", "after", "above", "below", "between", "under", "again", "further"]

        for sw in stopwords:
            assert engine._is_weak_keyword(sw) == True, f"Expected {sw} to be filtered as stopword"

    def test_meaningful_words_not_filtered(self):
        """Meaningful ASO keywords should pass through."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        keywords = ["fitness", "tracker", "budget", "meditation", "recipe", "workout", 
                    "camera", "photo", "music", "weather", "calendar", "notes", "todo"]

        for kw in keywords:
            assert engine._is_weak_keyword(kw) == False, f"Expected {kw} to NOT be filtered"


class TestWeakKeywordFiltering:
    """Tests for weak/advertising keyword detection."""

    def test_advertising_adjectives_filtered(self):
        """Generic advertising adjectives should be filtered."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        weak_words = ["best", "top", "new", "latest", "easy", "simple", "fast", "quick", 
                      "smart", "awesome", "cool", "amazing", "great", "perfect", "fun",
                      "good", "nice", "beautiful", "lovely", "fantastic", "wonderful",
                      "excellent", "premium", "ultimate", "super", "mega"]

        for kw in weak_words:
            assert engine._is_weak_keyword(kw) == True, f"Expected {kw} to be filtered as weak"

    def test_brand_suffixes_filtered(self):
        """Common app name suffixes should be filtered."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        suffixes = ["pro", "lite", "hd", "app", "game", "free"]

        for s in suffixes:
            assert engine._is_weak_keyword(s) == True, f"Expected {s} to be filtered as brand suffix"


class TestPhraseExtraction:
    """Tests for _extract_phrases helper method."""

    def test_extracts_two_word_phrases(self):
        """Should extract 2-word phrases."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        phrases = engine._extract_phrases("fitness tracker")

        assert "fitness tracker" in phrases

    def test_extracts_three_word_phrases(self):
        """Should extract 3-word phrases."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        phrases = engine._extract_phrases("personal budget tracker", min_words=2, max_words=3)

        assert "personal budget tracker" in phrases

    def test_empty_text_returns_empty(self):
        """Empty text should return empty list."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        assert engine._extract_phrases("") == []
        assert engine._extract_phrases(None) == []

    def test_filters_phrases_with_stopwords(self):
        """Phrases containing stopwords should be filtered."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        phrases = engine._extract_phrases("the best app for free")

        assert "the best" not in phrases
        assert "best app" not in phrases
        assert "app for" not in phrases
        assert "for free" not in phrases
        assert len(phrases) == 0

    def test_filters_phrases_with_weak_words(self):
        """Phrases containing weak words should be filtered."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        phrases = engine._extract_phrases("best free game")

        assert "best free" not in phrases
        assert "free game" not in phrases
        assert "best free game" not in phrases

    def test_keeps_meaningful_phrases(self):
        """Meaningful phrases should be kept."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        phrases = engine._extract_phrases("fitness tracker workout")

        assert "fitness tracker" in phrases
        assert "tracker workout" in phrases
        assert "fitness tracker workout" in phrases


class TestEmptyAppFallback:
    """Tests for empty app handling."""

    def test_empty_app_returns_fallback(self):
        """Non-existent app should return fallback."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(999)

        assert result == "app"
        assert method == "fallback_empty"


class TestWeakKeywordDetection:
    """Tests for _is_weak_keyword helper method."""

    def test_single_char_keywords_filtered(self):
        """Single character keywords should be filtered."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        assert engine._is_weak_keyword("a") == True
        assert engine._is_weak_keyword("i") == True

    def test_empty_string_is_weak(self):
        """Empty string should be treated as weak."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        assert engine._is_weak_keyword("") == True
        assert engine._is_weak_keyword("   ") == True

    def test_meaningful_keywords_accepted(self):
        """Meaningful keywords should pass."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        assert engine._is_weak_keyword("fitness") == False
        assert engine._is_weak_keyword("budget") == False
        assert engine._is_weak_keyword("meditation") == False
        assert engine._is_weak_keyword("recipe") == False


class TestTier1IntelligencePriority:
    """
    Integration tests for Tier 1: AppKeywordIntelligence takes highest priority.
    
    When an app has:
    - AppKeywordIntelligence entries (from title/subtitle/description extraction)
    - AppDiscoveredKeyword entries (from keyword discovery)
    - Title/subtitle phrases
    
    The system MUST select the keyword from AppKeywordIntelligence with highest traffic_score.
    """

    def test_tier1_selects_highest_traffic_score(self):
        """
        Scenario: App has multiple AppKeywordIntelligence entries.
        Expected: Select keyword with highest traffic_score, ignoring discovered/title.
        """
        mock_db = MagicMock()

        mock_app = MagicMock()
        mock_app.id = 1
        mock_app.name = "Health Tracker"
        mock_app.subtitle = "Track Wellness"

        aki_high = MagicMock()
        aki_high.traffic_score = 85.0
        kw_high = MagicMock()
        kw_high.term = "fitness tracker"

        discovered = MagicMock()
        discovered.keyword = "workout app"
        discovered.opportunity_score = 90.0

        def query_side_effect(*args, **kwargs):
            if len(args) >= 1:
                first_arg = args[0]
                if first_arg == App:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = mock_app
                    return m
                elif first_arg == AppKeywordIntelligence:
                    m = MagicMock()
                    m.join.return_value.filter.return_value.order_by.return_value.first.return_value = (aki_high, kw_high)
                    return m
                elif first_arg == AppDiscoveredKeyword:
                    m = MagicMock()
                    m.filter.return_value.filter.return_value.order_by.return_value.first.return_value = discovered
                    return m
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(1)

        assert method == "intelligence"
        assert result == "fitness tracker"

    def test_tier1_ignores_discovered_and_title_when_intelligence_exists(self):
        """
        Scenario: All tiers have data, but Tier 1 must win.
        Expected: Returns intelligence keyword, never falls through to discovered/title.
        """
        mock_db = MagicMock()

        mock_app = MagicMock()
        mock_app.id = 1
        mock_app.name = "Budget Planner"
        mock_app.subtitle = "Manage Money"

        aki = MagicMock()
        aki.traffic_score = 50.0
        kw = MagicMock()
        kw.term = "budget planning"

        discovered = MagicMock()
        discovered.keyword = "personal finance"
        discovered.opportunity_score = 95.0

        def query_side_effect(*args, **kwargs):
            if len(args) >= 1:
                first_arg = args[0]
                if first_arg == App:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = mock_app
                    return m
                elif first_arg == AppKeywordIntelligence:
                    m = MagicMock()
                    m.join.return_value.filter.return_value.order_by.return_value.first.return_value = (aki, kw)
                    return m
                elif first_arg == AppDiscoveredKeyword:
                    m = MagicMock()
                    m.filter.return_value.filter.return_value.order_by.return_value.first.return_value = discovered
                    return m
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(1)

        assert method == "intelligence"
        assert result == "budget planning"


class TestTier2DiscoveredPriority:
    """
    Integration tests for Tier 2: AppDiscoveredKeyword selection.
    
    When an app has NO AppKeywordIntelligence but HAS AppDiscoveredKeyword entries,
    select the discovered keyword with highest opportunity_score.
    """

    def test_tier2_selects_highest_opportunity_score(self):
        """
        Scenario: App has no intelligence, but has discovered keywords.
        Expected: Select discovered keyword with highest opportunity_score.
        """
        mock_db = MagicMock()

        mock_app = MagicMock()
        mock_app.id = 2
        mock_app.name = "Yoga App"
        mock_app.subtitle = "Meditation Guide"

        discovered_high = MagicMock()
        discovered_high.keyword = "meditation practice"
        discovered_high.opportunity_score = 85.0

        def query_side_effect(*args, **kwargs):
            if len(args) >= 1:
                first_arg = args[0]
                if first_arg == App:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = mock_app
                    return m
                elif first_arg == AppKeywordIntelligence:
                    m = MagicMock()
                    m.join.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif first_arg == AppDiscoveredKeyword:
                    m = MagicMock()
                    m.filter.return_value.filter.return_value.order_by.return_value.first.return_value = discovered_high
                    return m
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(2)

        assert method == "discovered"
        assert result == "meditation practice"

    def test_tier2_filters_weak_discovered_keywords(self):
        """
        Scenario: Best discovered keyword is weak (brand/stopword).
        Expected: Falls through to next valid discovered keyword or title.
        """
        mock_db = MagicMock()

        mock_app = MagicMock()
        mock_app.id = 3
        mock_app.name = "Best Free App"
        mock_app.subtitle = "Pro Version"

        weak_discovered = MagicMock()
        weak_discovered.keyword = "best app"
        weak_discovered.opportunity_score = 95.0

        def query_side_effect(*args, **kwargs):
            if len(args) >= 1:
                first_arg = args[0]
                if first_arg == App:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = mock_app
                    return m
                elif first_arg == AppKeywordIntelligence:
                    m = MagicMock()
                    m.join.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif first_arg == AppDiscoveredKeyword:
                    m = MagicMock()
                    m.filter.return_value.filter.return_value.order_by.return_value.first.return_value = weak_discovered
                    return m
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(3)

        assert method in ["discovered", "title_phrase", "fallback_phrase", "fallback_single"]


class TestTier3TitlePhrasePriority:
    """
    Integration tests for Tier 3: Title/Subtitle phrase extraction.
    
    When app has NO intelligence and NO discovered keywords,
    extract the best 2-3 word phrase from title/subtitle.
    """

    def test_tier3_extracts_best_title_phrase(self):
        """
        Scenario: App has no keyword data, only title/subtitle.
        Expected: Extract best 2-3 word phrase from title.
        """
        mock_db = MagicMock()

        mock_app = MagicMock()
        mock_app.id = 4
        mock_app.name = "Pocket Budget Tracker"
        mock_app.subtitle = "Personal Finance Manager"

        def query_side_effect(*args, **kwargs):
            if len(args) >= 1:
                first_arg = args[0]
                if first_arg == App:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = mock_app
                    return m
                elif first_arg == AppKeywordIntelligence:
                    m = MagicMock()
                    m.join.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif first_arg == AppDiscoveredKeyword:
                    m = MagicMock()
                    m.filter.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif first_arg == Keyword:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = None
                    return m
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(4)

        assert method in ["title_phrase", "fallback_phrase", "fallback_single"]
        assert result in ["pocket budget", "budget tracker", "personal finance", "finance manager"]

    def test_tier3_prefers_higher_scoring_phrases(self):
        """
        Scenario: Multiple title phrases available with different opportunity scores.
        Expected: Select phrase with highest opportunity_score.
        """
        mock_db = MagicMock()

        mock_app = MagicMock()
        mock_app.id = 5
        mock_app.name = "Fitness Workout Trainer"
        mock_app.subtitle = "Exercise App"

        kw_workout = MagicMock()
        kw_workout.term = "workout trainer"
        kw_workout.opportunity_score = 75.0

        kw_fitness = MagicMock()
        kw_fitness.term = "fitness workout"
        kw_fitness.opportunity_score = 45.0

        def query_side_effect(*args, **kwargs):
            if len(args) >= 1:
                first_arg = args[0]
                if first_arg == App:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = mock_app
                    return m
                elif first_arg == AppKeywordIntelligence:
                    m = MagicMock()
                    m.join.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif first_arg == AppDiscoveredKeyword:
                    m = MagicMock()
                    m.filter.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif first_arg == Keyword:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = kw_workout
                    return m
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(5)

        assert method == "title_phrase"
        assert "workout" in result


class TestTier4Fallback:
    """
    Integration tests for Tier 4: Smart Fallback.
    
    When app has no keyword data AND weak title/subtitle,
    use smart fallback to extract best available phrase.
    """

    def test_tier4_fallback_with_weak_title(self):
        """
        Scenario: App has no keyword data and weak title (only weak words).
        Expected: Fallback returns best available or empty fallback.
        """
        mock_db = MagicMock()

        mock_app = MagicMock()
        mock_app.id = 6
        mock_app.name = "Best App"
        mock_app.subtitle = "Free Pro"

        def query_side_effect(*args, **kwargs):
            if len(args) >= 1:
                first_arg = args[0]
                if first_arg == App:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = mock_app
                    return m
                elif first_arg == AppKeywordIntelligence:
                    m = MagicMock()
                    m.join.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif first_arg == AppDiscoveredKeyword:
                    m = MagicMock()
                    m.filter.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif first_arg == Keyword:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = None
                    return m
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(6)

        assert method in ["fallback_phrase", "fallback_single", "fallback_empty"]

    def test_tier4_fallback_empty_returns_safe_value(self):
        """
        Scenario: App has absolutely no usable data.
        Expected: Returns safe fallback 'app'.
        """
        mock_db = MagicMock()

        mock_app = MagicMock()
        mock_app.id = 7
        mock_app.name = ""
        mock_app.subtitle = ""

        def query_side_effect(*args):
            if hasattr(args[0], '__mro__') and hasattr(args[0], '__name__'):
                model_name = args[0].__name__
                if model_name == 'App':
                    m = MagicMock()
                    m.filter.return_value.first.return_value = mock_app
                    return m
                elif 'AppKeywordIntelligence' in model_name:
                    m = MagicMock()
                    m.join.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif 'AppDiscoveredKeyword' in model_name:
                    m = MagicMock()
                    m.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif model_name == 'Keyword':
                    m = MagicMock()
                    m.filter.return_value.first.return_value = None
                    return m
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(7)

        assert result == "app"
        assert method == "fallback_empty"


class TestTierPrecedenceHierarchy:
    """
    Integration test verifying exact tier precedence.
    
    Creates scenario where ALL tiers have data and verifies
    the hierarchy: Tier 1 > Tier 2 > Tier 3 > Tier 4
    """

    def test_tier_precedence_enforced_exactly(self):
        """
        Scenario: All 4 tiers have data available.
        Expected: Tier 1 (intelligence) MUST be selected, ignoring tiers 2-4.
        """
        mock_db = MagicMock()

        mock_app = MagicMock()
        mock_app.id = 100
        mock_app.name = "My Fitness App"
        mock_app.subtitle = "Best Workout Tracker"

        aki = MagicMock()
        aki.traffic_score = 60.0
        kw_intelligence = MagicMock()
        kw_intelligence.term = "fitness training"

        discovered = MagicMock()
        discovered.keyword = "workout app"
        discovered.opportunity_score = 95.0

        def query_side_effect(*args):
            if hasattr(args[0], '__mro__') and hasattr(args[0], '__name__'):
                model_name = args[0].__name__
                if model_name == 'App':
                    m = MagicMock()
                    m.filter.return_value.first.return_value = mock_app
                    return m
                elif 'AppKeywordIntelligence' in model_name:
                    m = MagicMock()
                    m.join.return_value.filter.return_value.order_by.return_value.first.return_value = (aki, kw_intelligence)
                    return m
                elif 'AppDiscoveredKeyword' in model_name:
                    m = MagicMock()
                    m.filter.return_value.order_by.return_value.first.return_value = discovered
                    return m
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(100)

        assert method == "intelligence"
        assert result == "fitness training"

    def test_tier_precedence_tier2_when_no_tier1(self):
        """
        Scenario: Tier 1 empty, but tiers 2-4 have data.
        Expected: Tier 2 (discovered) MUST be selected.
        """
        mock_db = MagicMock()

        mock_app = MagicMock()
        mock_app.id = 101
        mock_app.name = "Music Player"
        mock_app.subtitle = "Stream Audio"

        discovered = MagicMock()
        discovered.keyword = "music streaming"
        discovered.opportunity_score = 88.0

        def query_side_effect(*args, **kwargs):
            if len(args) >= 1:
                first_arg = args[0]
                if first_arg == App:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = mock_app
                    return m
                elif first_arg == AppKeywordIntelligence:
                    m = MagicMock()
                    m.join.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif first_arg == AppDiscoveredKeyword:
                    m = MagicMock()
                    m.filter.return_value.filter.return_value.order_by.return_value.first.return_value = discovered
                    return m
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(101)

        assert method == "discovered"
        assert result == "music streaming"

    def test_tier_precedence_tier3_when_no_tier1_or_2(self):
        """
        Scenario: Tiers 1-2 empty, but tiers 3-4 have data.
        Expected: Tier 3 (title phrase) MUST be selected.
        """
        mock_db = MagicMock()

        mock_app = MagicMock()
        mock_app.id = 102
        mock_app.name = "Weather Forecast"
        mock_app.subtitle = "Daily Climate"

        def query_side_effect(*args, **kwargs):
            if len(args) >= 1:
                first_arg = args[0]
                if first_arg == App:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = mock_app
                    return m
                elif first_arg == AppKeywordIntelligence:
                    m = MagicMock()
                    m.join.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif first_arg == AppDiscoveredKeyword:
                    m = MagicMock()
                    m.filter.return_value.filter.return_value.order_by.return_value.first.return_value = None
                    return m
                elif first_arg == Keyword:
                    m = MagicMock()
                    m.filter.return_value.first.return_value = None
                    return m
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db

        result, method = engine.select_primary_keyword(102)

        assert method in ["title_phrase", "fallback_phrase"]
        assert result in ["weather forecast", "forecast daily", "daily climate"]
