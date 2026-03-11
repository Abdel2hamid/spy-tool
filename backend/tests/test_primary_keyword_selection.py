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
