"""
Tests for refined keyword hard gate logic.

Verifies:
1. Valuable single-word keyword ("meditation") → accepted.
2. Generic word ("best") → rejected.
3. Short token ("app") → rejected.
4. Strong multi-word phrase still preferred over single-word.
5. Single-word keyword with high signal passes.
6. Single-word keyword with weak signal rejected.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.keyword_quality_engine import KeywordQualityEngine


class TestHardGateSingleWord:
    """Tests for single-word keyword hard gate."""

    def test_valuable_single_word_accepted(self):
        """Valuable single-word keywords like 'meditation' should be accepted."""
        result, reason = KeywordQualityEngine.passes_hard_gate("meditation")
        assert result == True
        assert reason == ""

    def test_valuable_single_word_budgeting_accepted(self):
        """'budgeting' should be accepted."""
        result, reason = KeywordQualityEngine.passes_hard_gate("budgeting")
        assert result == True
        assert reason == ""

    def test_valuable_single_word_recipes_accepted(self):
        """'recipes' should be accepted."""
        result, reason = KeywordQualityEngine.passes_hard_gate("recipes")
        assert result == True
        assert reason == ""

    def test_valuable_single_word_fasting_accepted(self):
        """'fasting' should be accepted."""
        result, reason = KeywordQualityEngine.passes_hard_gate("fasting")
        assert result == True
        assert reason == ""

    def test_valuable_single_word_journaling_accepted(self):
        """'journaling' should be accepted."""
        result, reason = KeywordQualityEngine.passes_hard_gate("journaling")
        assert result == True
        assert reason == ""

    def test_generic_weak_word_rejected(self):
        """Generic weak words like 'best' should be rejected."""
        result, reason = KeywordQualityEngine.passes_hard_gate("best")
        assert result == False
        assert reason == "single_word_weak"

    def test_short_token_rejected(self):
        """Short tokens like 'app' should be rejected (also in weak words list)."""
        result, reason = KeywordQualityEngine.passes_hard_gate("app")
        assert result == False

    def test_free_rejected(self):
        """'free' should be rejected."""
        result, reason = KeywordQualityEngine.passes_hard_gate("free")
        assert result == False

    def test_smart_rejected(self):
        """'smart' should be rejected."""
        result, reason = KeywordQualityEngine.passes_hard_gate("smart")
        assert result == False

    def test_numeric_only_rejected(self):
        """Numeric-only keywords should be rejected."""
        result, reason = KeywordQualityEngine.passes_hard_gate("123")
        assert result == False
        assert reason == "single_word_numeric"


class TestHardGateMultiWord:
    """Tests for multi-word keyword hard gate (unchanged)."""

    def test_two_word_phrase_accepted(self):
        """Good two-word phrases should be accepted."""
        result, reason = KeywordQualityEngine.passes_hard_gate("fitness tracker")
        assert result == True

    def test_three_word_phrase_accepted(self):
        """Good three-word phrases should be accepted."""
        result, reason = KeywordQualityEngine.passes_hard_gate("personal budget tracker")
        assert result == True

    def test_stopword_phrase_rejected(self):
        """Phrases with all stopwords should be rejected."""
        result, reason = KeywordQualityEngine.passes_hard_gate("the app")
        assert result == False
        assert reason == "all_stopwords"

    def test_repeated_tokens_rejected(self):
        """Phrases with repeated tokens should be rejected."""
        result, reason = KeywordQualityEngine.passes_hard_gate("app app")
        assert result == False
        assert reason == "repeated_tokens"

    def test_junk_phrase_rejected(self):
        """Junk phrases should be rejected."""
        result, reason = KeywordQualityEngine.passes_hard_gate("best app")
        assert result == False
        assert reason == "junk_phrase"


class TestQualityScorePenalty:
    """Tests for quality score penalty on single-word keywords."""

    def test_single_word_gets_penalty(self):
        """Single-word keywords should receive a penalty."""
        q_score1, v_score1, r_score1 = KeywordQualityEngine.compute_quality_score(
            term="meditation",
            keyword_source="seed",
            apps_count=100,
            search_volume=80,
            trend_score=50,
        )
        
        q_score2, v_score2, r_score2 = KeywordQualityEngine.compute_quality_score(
            term="meditation app",
            keyword_source="seed",
            apps_count=100,
            search_volume=80,
            trend_score=50,
        )
        
        assert q_score2 > q_score1

    def test_multi_word_no_penalty(self):
        """Multi-word keywords should not receive a penalty."""
        q_score, _, _ = KeywordQualityEngine.compute_quality_score(
            term="fitness tracker",
            keyword_source="seed",
            apps_count=50,
            search_volume=50,
            trend_score=30,
        )
        
        base = 10 + 5 + 5 + 15 + 20 + 10 + 0 + 1.5 + 0
        expected = base * 10
        assert q_score <= expected + 5


class TestEdgeCases:
    """Tests for edge cases."""

    def test_very_short_rejected(self):
        """Very short terms should be rejected."""
        result, reason = KeywordQualityEngine.passes_hard_gate("a")
        assert result == False

    def test_four_chars_rejected(self):
        """4-character single words should be rejected."""
        result, reason = KeywordQualityEngine.passes_hard_gate("game")
        assert result == False

    def test_five_chars_rejected(self):
        """5-character single words should be rejected."""
        result, reason = KeywordQualityEngine.passes_hard_gate("photo")
        assert result == False

    def test_six_chars_accepted(self):
        """6-character single words should be accepted."""
        result, reason = KeywordQualityEngine.passes_hard_gate("camera")
        assert result == True

    def test_invoices_accepted(self):
        """'invoices' should be accepted."""
        result, reason = KeywordQualityEngine.passes_hard_gate("invoices")
        assert result == True
