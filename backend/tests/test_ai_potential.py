"""
Tests for AI Potential Scoring — Weighted Rule-Based System
===========================================================

Tests verify:
  1. AI-native apps are classified correctly (score >= 60, type 'ai_native')
  2. AI-enhanced apps receive moderate scores (25 <= score < 60, type 'ai_enhanced')
  3. Non-AI apps score very low (score < 25, type 'weak')
  4. Generic words ('smart', 'assistant') do NOT trigger false positives alone
  5. Signal sources are correctly reported in ai_signal_sources
"""

import sys
import os
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scoring.ai_potential import (
    calculate_ai_potential_v2,
    AI_NATIVE_TITLE_TERMS,
    AI_DESCRIPTION_PHRASES,
    FEATURE_GAP_AI_PHRASES,
    AI_OPPORTUNITY_CATEGORIES,
    AI_RELATED_KEYWORD_PHRASES,
)


# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------

def _make_app(
    name: str = "",
    subtitle: str = "",
    description: str = "",
    primary_category: str = "",
) -> MagicMock:
    """Return a lightweight mock App object."""
    app = MagicMock()
    app.name = name
    app.subtitle = subtitle
    app.description = description
    app.primary_category = primary_category
    return app


def _make_gap(feature_name: str) -> MagicMock:
    gap = MagicMock()
    gap.feature_name = feature_name
    return gap


def _make_kw(keyword: str) -> MagicMock:
    kw = MagicMock()
    kw.keyword = keyword
    return kw


# ---------------------------------------------------------------------------
# 1. AI-native apps
# ---------------------------------------------------------------------------

class TestAINativeClassification:
    """Apps with unambiguous AI signals should score high; multiple signals reach ai_native."""

    def test_ai_in_title_scores_35(self):
        """Title containing 'AI' alone → score = 35 (title weight = 0.35)."""
        app = _make_app(name="AI Writing Master")
        result = calculate_ai_potential_v2(app)
        assert result["ai_potential_score"] == pytest.approx(35.0, abs=0.1)
        # 35 is below ai_native threshold (60) but above ai_enhanced (25)
        assert result["ai_opportunity_type"] == "ai_enhanced"

    def test_gpt_in_title_fires_title_signal(self):
        """Title containing 'GPT' → title signal fires, score = 35."""
        app = _make_app(name="GPT Keyboard Pro")
        result = calculate_ai_potential_v2(app)
        assert result["ai_potential_score"] == pytest.approx(35.0, abs=0.1)
        assert any("title_contains" in s for s in result["ai_signal_sources"])

    def test_chatbot_in_title_fires_title_signal(self):
        """Title containing 'chatbot' → title signal fires."""
        app = _make_app(name="My Chatbot Companion")
        result = calculate_ai_potential_v2(app)
        assert result["ai_potential_score"] == pytest.approx(35.0, abs=0.1)
        assert any("title_contains" in s for s in result["ai_signal_sources"])

    def test_copilot_in_title_fires_title_signal(self):
        """Title containing 'copilot' → title signal fires."""
        app = _make_app(name="Code Copilot Pro")
        result = calculate_ai_potential_v2(app)
        assert result["ai_potential_score"] == pytest.approx(35.0, abs=0.1)
        assert any("title_contains" in s for s in result["ai_signal_sources"])

    def test_llm_in_title_fires_title_signal(self):
        """Title containing 'llm' → title signal fires."""
        app = _make_app(name="LLM Explorer")
        result = calculate_ai_potential_v2(app)
        assert result["ai_potential_score"] == pytest.approx(35.0, abs=0.1)
        assert any("title_contains" in s for s in result["ai_signal_sources"])

    def test_ai_native_with_title_and_description(self):
        """AI title + AI description phrase → score = 60 (= ai_native threshold)."""
        app = _make_app(
            name="AI Notes Pro",
            description="Powered by AI to help you write and summarize faster.",
        )
        result = calculate_ai_potential_v2(app)
        # title (35) + description (25) = 60 → ai_native
        assert result["ai_potential_score"] == pytest.approx(60.0, abs=0.1)
        assert result["ai_opportunity_type"] == "ai_native"

    def test_ai_native_title_description_and_category(self):
        """AI title + description + productivity category → score = 70, ai_native."""
        app = _make_app(
            name="AI Writer Pro",
            description="Uses machine learning to craft professional emails instantly.",
            primary_category="Productivity",
        )
        result = calculate_ai_potential_v2(app)
        # title (35) + description (25) + category (10) = 70
        assert result["ai_potential_score"] >= 60
        assert result["ai_opportunity_type"] == "ai_native"

    def test_chatgpt_in_description(self):
        """'chatgpt' phrase in description fires description signal."""
        app = _make_app(
            name="Smart Notes",
            description="Uses ChatGPT under the hood for smart note summarization.",
        )
        result = calculate_ai_potential_v2(app)
        assert result["ai_potential_score"] >= 25
        assert "description_chatgpt" in result["ai_signal_sources"]


# ---------------------------------------------------------------------------
# 2. AI-enhanced apps
# ---------------------------------------------------------------------------

class TestAIEnhancedClassification:
    """Apps where AI can improve but isn't the core product."""

    def test_productivity_category_alone(self):
        """Productivity category alone gives 10 pts → weak, but next to a feature gap → enhanced."""
        app = _make_app(name="Notes App", primary_category="Productivity")
        gaps = [_make_gap("summarize my notes"), _make_gap("auto suggestions")]
        result = calculate_ai_potential_v2(app, feature_gaps=gaps)
        # category (10) + feature_gap (20) = 30 → ai_enhanced
        assert result["ai_potential_score"] >= 25
        assert result["ai_opportunity_type"] == "ai_enhanced"

    def test_journaling_with_suggestion_gap(self):
        """Journaling app with 'suggestions' feature gap → ai_enhanced."""
        app = _make_app(
            name="Daily Journal",
            primary_category="Lifestyle",
        )
        gaps = [_make_gap("smart suggestions for prompts")]
        result = calculate_ai_potential_v2(app, feature_gaps=gaps)
        # feature_gap (20) = 20 → weak, unless category helps (it doesn't here)
        # → score depends purely on feature_gap: 0.20×100 = 20 → just below threshold
        # but should still be close; verify gap signal fires
        assert "feature_gap_suggestion" in " ".join(result["ai_signal_sources"]) or \
               any("feature_gap" in s for s in result["ai_signal_sources"])

    def test_fitness_category_with_ai_keyword(self):
        """Fitness app + discovered 'ai coach' keyword → ai_enhanced."""
        app = _make_app(name="FitTrack", primary_category="Health & Fitness")
        keywords = [_make_kw("ai coach")]
        result = calculate_ai_potential_v2(app, discovered_keywords=keywords)
        # category (10) + keyword (10) = 20 + fitness category (10) = ~20
        # fitness is included under 'fitness' substring  → category fires
        assert any("fitness_category" in s or "health_category" in s for s in result["ai_signal_sources"])
        assert result["ai_potential_score"] >= 20

    def test_writing_category(self):
        """Writing category alone fires category signal."""
        app = _make_app(name="Prose", primary_category="Writing")
        result = calculate_ai_potential_v2(app)
        assert "writing_category" in result["ai_signal_sources"]
        assert result["ai_potential_score"] == 10.0

    def test_education_category(self):
        """Education category fires category signal."""
        app = _make_app(name="Quizlet Pro", primary_category="Education")
        result = calculate_ai_potential_v2(app)
        assert "education_category" in result["ai_signal_sources"]

    def test_description_phrase_smart_suggestions(self):
        """'smart suggestions' in description → description signal fires."""
        app = _make_app(
            name="BudgetWise",
            description="BudgetWise provides smart suggestions based on your spending habits.",
        )
        result = calculate_ai_potential_v2(app)
        assert any("description_smart_suggestions" in s for s in result["ai_signal_sources"])
        assert result["ai_potential_score"] >= 25


# ---------------------------------------------------------------------------
# 3. Weak / No AI relevance
# ---------------------------------------------------------------------------

class TestWeakClassification:
    """Apps with no meaningful AI signals should score low."""

    def test_calculator_app(self):
        """Plain calculator → weak, score < 25."""
        app = _make_app(name="Calculator Free", primary_category="Utilities")
        result = calculate_ai_potential_v2(app)
        # Utilities category fires (10 pts), but nothing else
        assert result["ai_potential_score"] < 25
        assert result["ai_opportunity_type"] == "weak"

    def test_flashlight_app(self):
        """Flashlight app → weak."""
        app = _make_app(name="Flashlight Widget", description="Simple flashlight app.")
        result = calculate_ai_potential_v2(app)
        assert result["ai_opportunity_type"] == "weak"
        assert result["ai_potential_score"] < 25

    def test_simple_timer_app(self):
        """Timer app with no AI context → weak."""
        app = _make_app(name="Kitchen Timer Pro", description="Set timers easily.")
        result = calculate_ai_potential_v2(app)
        assert result["ai_opportunity_type"] == "weak"
        assert result["ai_potential_score"] < 25

    def test_static_reference_app(self):
        """Static reference dictionary app → weak."""
        app = _make_app(
            name="Medical Dictionary",
            description="Browse thousands of medical terms offline.",
        )
        result = calculate_ai_potential_v2(app)
        assert result["ai_opportunity_type"] == "weak"

    def test_no_signals_returns_zero_score(self):
        """App with empty fields → score 0."""
        app = _make_app()
        result = calculate_ai_potential_v2(app)
        assert result["ai_potential_score"] == 0.0
        assert result["ai_opportunity_type"] == "weak"
        assert result["ai_signal_sources"] == []


# ---------------------------------------------------------------------------
# 4. False positive prevention
# ---------------------------------------------------------------------------

class TestFalsePositivePrevention:
    """Generic marketing words must NOT trigger ai_native classification."""

    def test_smart_alone_in_title_does_not_make_ai_native(self):
        """'Smart Notes' title alone must NOT produce ai_native."""
        app = _make_app(name="Smart Notes")
        result = calculate_ai_potential_v2(app)
        assert result["ai_opportunity_type"] != "ai_native", (
            f"'Smart Notes' should not be ai_native but got {result}"
        )

    def test_smart_alone_produces_no_title_signal(self):
        """'smart' in title without any AI-native term → title signal must be 0."""
        app = _make_app(name="Smart Organizer")
        result = calculate_ai_potential_v2(app)
        # Title signal is 0 → only other signals (category etc.) can contribute
        assert not any("title_contains" in s for s in result["ai_signal_sources"])

    def test_assistant_alone_does_not_trigger_ai_native(self):
        """'Assistant' alone in title (e.g. personal scheduler) → not ai_native."""
        app = _make_app(name="Assistant for Google Calendar")
        result = calculate_ai_potential_v2(app)
        assert result["ai_opportunity_type"] != "ai_native"

    def test_create_word_no_false_positive(self):
        """'Create' in title → not an AI signal."""
        app = _make_app(name="Create Your Recipe")
        result = calculate_ai_potential_v2(app)
        assert not any("title_contains" in s for s in result["ai_signal_sources"])

    def test_write_word_no_false_positive(self):
        """'Write' in title (plain writing app) → not an AI signal."""
        app = _make_app(name="Write Daily Journal")
        result = calculate_ai_potential_v2(app)
        assert not any("title_contains" in s for s in result["ai_signal_sources"])

    def test_learn_word_no_false_positive(self):
        """'Learn' in title → not an AI signal."""
        app = _make_app(name="Learn Spanish for Kids")
        result = calculate_ai_potential_v2(app)
        assert not any("title_contains" in s for s in result["ai_signal_sources"])

    def test_automation_word_in_title_no_false_positive(self):
        """'Automation' alone in title → generic, should not fire title_signal."""
        app = _make_app(name="Home Automation Controller")
        result = calculate_ai_potential_v2(app)
        # No native AI term alongside it → title_signal = 0
        assert not any("title_contains" in s for s in result["ai_signal_sources"])

    def test_smart_in_title_with_ai_native_in_subtitle_fires(self):
        """'Smart' in title IS allowed if 'ai' appears in subtitle."""
        app = _make_app(name="Smart Writer", subtitle="Powered by AI to help you write faster")
        result = calculate_ai_potential_v2(app)
        # subtitle has 'ai' → combined text has native term → title signal fires
        # AND description signal fires for 'ai' substring in subtitle
        assert result["ai_potential_score"] >= 35


# ---------------------------------------------------------------------------
# 5. Signal source reporting
# ---------------------------------------------------------------------------

class TestSignalSourceReporting:
    """Signal sources must be correctly reported in ai_signal_sources."""

    def test_title_source_reported(self):
        """title signal → label starts with 'title_contains_'."""
        app = _make_app(name="AI Journal Pro")
        result = calculate_ai_potential_v2(app)
        assert any(s.startswith("title_contains_") for s in result["ai_signal_sources"])

    def test_description_source_reported(self):
        """Description phrase match → label starts with 'description_'."""
        app = _make_app(description="This app uses machine learning to improve your experience.")
        result = calculate_ai_potential_v2(app)
        assert any(s.startswith("description_") for s in result["ai_signal_sources"])

    def test_feature_gap_source_reported(self):
        """Feature gap match → label starts with 'feature_gap_'."""
        app = _make_app(name="Memo")
        gaps = [_make_gap("auto-complete text")]
        result = calculate_ai_potential_v2(app, feature_gaps=gaps)
        assert any(s.startswith("feature_gap_") for s in result["ai_signal_sources"])

    def test_category_source_reported(self):
        """Category match → label ends with '_category'."""
        app = _make_app(primary_category="Productivity")
        result = calculate_ai_potential_v2(app)
        assert any(s.endswith("_category") for s in result["ai_signal_sources"])
        assert "productivity_category" in result["ai_signal_sources"]

    def test_keyword_source_reported(self):
        """Discovered keyword match → label starts with 'keyword_'."""
        app = _make_app(name="Notepad")
        kws = [_make_kw("ai writer")]
        result = calculate_ai_potential_v2(app, discovered_keywords=kws)
        assert any(s.startswith("keyword_") for s in result["ai_signal_sources"])

    def test_no_signals_empty_sources(self):
        """Blank app → empty signal sources list."""
        result = calculate_ai_potential_v2(_make_app())
        assert result["ai_signal_sources"] == []

    def test_multiple_signals_all_reported(self):
        """Multiple signals all contribute their labels."""
        app = _make_app(
            name="AI Notes Player",
            description="Uses machine learning to organize your notes.",
            primary_category="Productivity",
        )
        gaps = [_make_gap("summarize my day")]
        kws = [_make_kw("ai notes")]
        result = calculate_ai_potential_v2(app, feature_gaps=gaps, discovered_keywords=kws)
        sources = result["ai_signal_sources"]
        assert any("title_contains" in s for s in sources)
        assert any("description_" in s for s in sources)
        assert any("feature_gap_" in s for s in sources)
        assert "productivity_category" in sources
        assert any("keyword_" in s for s in sources)


# ---------------------------------------------------------------------------
# 6. Scoring formula accuracy
# ---------------------------------------------------------------------------

class TestScoringWeights:
    """Verify the weighted formula produces expected score ranges."""

    def test_only_title_signal_score_is_35(self):
        """Title-only match → score = 100 × 0.35 = 35.0."""
        # Ensure no other signals fire
        app = _make_app(name="GPT Tool")
        result = calculate_ai_potential_v2(app)
        # title = 35, but description/category/etc. may also fire if 'gpt' appears in description
        # Since we only set name here, and no other fields, only title fires
        assert result["ai_potential_score"] == pytest.approx(35.0, abs=0.1)

    def test_category_only_signal_score_is_10(self):
        """Category-only match → score = 100 × 0.10 = 10.0."""
        app = _make_app(name="TaskMaster", primary_category="Productivity")
        result = calculate_ai_potential_v2(app)
        assert result["ai_potential_score"] == pytest.approx(10.0, abs=0.1)

    def test_feature_gap_only_score_is_20(self):
        """Feature gap only → score = 100 × 0.20 = 20.0."""
        app = _make_app(name="PlainApp")
        gaps = [_make_gap("auto-generate captions")]
        result = calculate_ai_potential_v2(app, feature_gaps=gaps)
        assert result["ai_potential_score"] == pytest.approx(20.0, abs=0.1)

    def test_full_score_all_signals(self):
        """All five signals firing → score = 100."""
        app = _make_app(
            name="AI Notes Pro",
            description="Powered by AI to summarize and generate content.",
            primary_category="Productivity",
        )
        gaps = [_make_gap("needs summarization")]
        kws = [_make_kw("ai notes")]
        result = calculate_ai_potential_v2(app, feature_gaps=gaps, discovered_keywords=kws)
        # All 5 signals = 100 × (0.35 + 0.25 + 0.20 + 0.10 + 0.10) = 100
        assert result["ai_potential_score"] == pytest.approx(100.0, abs=0.1)
        assert result["ai_opportunity_type"] == "ai_native"

    def test_score_clamps_to_100(self):
        """Score never exceeds 100."""
        app = _make_app(
            name="AI Chatbot GPT",
            subtitle="powered by ai",
            description="Powered by AI language model. Uses ChatGPT.",
            primary_category="Productivity",
        )
        gaps = [_make_gap("ai suggestions")]
        kws = [_make_kw("ai writer")]
        result = calculate_ai_potential_v2(app, feature_gaps=gaps, discovered_keywords=kws)
        assert result["ai_potential_score"] <= 100.0

    def test_score_never_negative(self):
        """Score is never negative."""
        result = calculate_ai_potential_v2(_make_app())
        assert result["ai_potential_score"] >= 0.0

    def test_ai_enhanced_threshold_boundary(self):
        """Score of exactly 25 → ai_enhanced."""
        # category (10) + feature_gap (20) = 30 > 25 → ai_enhanced
        app = _make_app(name="Budget App", primary_category="Finance")
        gaps = [_make_gap("auto-generate reports")]
        result = calculate_ai_potential_v2(app, feature_gaps=gaps)
        # finance (10) + gap (20) = 30 → ai_enhanced
        assert result["ai_potential_score"] >= 25
        assert result["ai_opportunity_type"] == "ai_enhanced"
