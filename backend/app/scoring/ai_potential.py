"""
AI Potential Scoring — Weighted Rule-Based System
==================================================

Replaces the old keyword-count heuristic with a multi-signal scoring model that:
  - Clearly separates strong AI-native signals from weaker AI-enhancement ones
  - Uses configurable keyword/phrase constants (no magic strings in logic)
  - Returns an explainable list of signal sources alongside the score
  - Prevents generic words ("smart", "assistant") from triggering false positives

Output structure
----------------
{
    "ai_potential_score": float,        # 0-100
    "ai_opportunity_type": str,         # "ai_native" | "ai_enhanced" | "weak"
    "ai_signal_sources": list[str],     # human-readable labels of detected signals
}

Scoring weights
---------------
  title_signal       × 0.35   (strong — explicit AI naming in title)
  description_signal × 0.25   (medium — AI language in subtitle/description)
  feature_gap_signal × 0.20   (medium — user reviews demand AI-like features)
  category_signal    × 0.10   (context — category known for AI opportunity)
  keyword_signal     × 0.10   (context — discovered keywords contain AI phrases)
"""

from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Configurable constants — edit here to tune signal detection
# ---------------------------------------------------------------------------

# Strong AI indicators that belong in an app's *title*.
# These are unambiguous: if present the app is almost certainly AI-native.
AI_NATIVE_TITLE_TERMS: frozenset = frozenset({
    "ai",
    "gpt",
    "chatgpt",
    "llm",
    "chatbot",
    "copilot",
    "claude",
    "gemini ai",
    "neural",
    "diffusion",
    "midjourney",
    "dall-e",
    "dall·e",
    "stable diffusion",
    "generative",
})

# Slightly weaker title terms — only meaningful when we need multi-word context.
# These contribute only if they form part of a 2+ word phrase with another
# AI term, or appear alongside AI_NATIVE_TITLE_TERMS.
# Used as STANDALONE guards (see _title_signal).
_GENERIC_TITLE_TERMS: frozenset = frozenset({
    "smart",
    "assistant",
    "voice",
    "automate",
    "automated",
    "auto",
    "learn",
    "predict",
    "bot",
    "generate",
    "generator",
    "writer",
    "creator",
})

# Multi-word phrases we look for in subtitle and description text.
# More specific than single-word terms → medium weight.
AI_DESCRIPTION_PHRASES: tuple = (
    "powered by ai",
    "powered by artificial intelligence",
    "built with ai",
    "uses ai",
    "ai-powered",
    "ai powered",
    "machine learning",
    "large language model",
    "language model",
    "natural language",
    "generate automatically",
    "auto-generate",
    "smart suggestions",
    "intelligent suggestions",
    "automated insights",
    "ai insights",
    "ai assistant",
    "ai writer",
    "ai writing",
    "ai chat",
    "ai coach",
    "ai tutor",
    "ai detector",
    "ai analysis",
    "generative ai",
    "openai",
    "chatgpt",
    "gpt-4",
    "gpt-3",
    "llm",
)

# Phrases in feature-gap / review text that indicate users want AI features.
# Each pattern is checked as a substring of the feature_name stored in FeatureGap.
FEATURE_GAP_AI_PHRASES: tuple = (
    "summarize",
    "summarization",
    "summary",
    "suggest",
    "suggestion",
    "suggestions",
    "smart reply",
    "smart complete",
    "auto-complete",
    "autocomplete",
    "auto complete",
    "automation",
    "automate",
    "ai feature",
    "ai suggestion",
    "ai mode",
    "generate",
    "generation",
    "transcribe",
    "transcription",
    "translation",
    "translate",
    "rewrite",
    "paraphrase",
    "grammar check",
    "spell check",
    "writing assistant",
    "needs ai",
    "wish it had ai",
    "add ai",
)

# Category name substrings (case-insensitive) that indicate AI opportunity.
# Maps substring → signal label for the output.
AI_OPPORTUNITY_CATEGORIES: Dict[str, str] = {
    "productivity":     "productivity_category",
    "writing":          "writing_category",
    "education":        "education_category",
    "photo":            "photo_editing_category",
    "video":            "video_category",
    "finance":          "finance_category",
    "health":           "health_category",
    "fitness":          "fitness_category",
    "medical":          "medical_category",
    "business":         "business_category",
    "developer tool":   "developer_tools_category",
    "utilities":        "utilities_category",
    "news":             "news_category",
    "reference":        "reference_category",
    "food":             "food_category",
    "music":            "music_category",
}

# Keywords found in AppDiscoveredKeyword that indicate AI opportunity.
AI_RELATED_KEYWORD_PHRASES: tuple = (
    "ai writer",
    "ai generator",
    "ai notes",
    "ai planner",
    "ai chat",
    "ai assistant",
    "ai coach",
    "ai tutor",
    "ai detector",
    "ai editor",
    "ai summary",
    "ai translate",
    "chatgpt",
    "gpt",
    "llm",
    "copilot",
    "generative ai",
    "text generator",
    "image generator",
    "voice ai",
    "ai tool",
    "ai app",
)

# Score thresholds for opportunity type classification
_THRESHOLD_NATIVE: float = 60.0
_THRESHOLD_ENHANCED: float = 25.0

# Weights (must sum to 1.0)
_W_TITLE:        float = 0.35
_W_DESCRIPTION:  float = 0.25
_W_FEATURE_GAP:  float = 0.20
_W_CATEGORY:     float = 0.10
_W_KEYWORD:      float = 0.10

# ---------------------------------------------------------------------------
# Internal signal computers
# ---------------------------------------------------------------------------

def _title_signal(app_name: str, app_subtitle: str = "") -> tuple[float, List[str]]:
    """
    Compute title signal (0 or 100) and matching source labels.

    Rules:
      - If any AI_NATIVE_TITLE_TERMS token appears as a standalone word in the
        title → score 100, labelled "title_contains_<term>".
      - Generic terms (_GENERIC_TITLE_TERMS) in the title only count if AT LEAST
        ONE AI_NATIVE_TITLE_TERMS is also present in the combined title+subtitle.
        This prevents "Smart Notes" from firing the title signal alone.
    """
    sources: List[str] = []
    title_lower = (app_name or "").lower()
    # Word-boundary-aware: pad with spaces so "ai" doesn't match "train"
    padded = f" {title_lower} "

    # Check for native AI terms (strong signal — fire immediately)
    for term in AI_NATIVE_TITLE_TERMS:
        if f" {term} " in padded or padded.startswith(f"{term} ") or padded.endswith(f" {term}"):
            sources.append(f"title_contains_{term.replace(' ', '_')}")
            return 100.0, sources

    # Check for generic terms — only count if also appears alongside an AI term
    # somewhere in the combined title + subtitle text
    combined = f"{title_lower} {(app_subtitle or '').lower()}"
    has_ai_native_in_combined = any(
        f" {t} " in f" {combined} " or combined.startswith(f"{t} ") or combined.endswith(f" {t}")
        for t in AI_NATIVE_TITLE_TERMS
    )

    if has_ai_native_in_combined:
        for term in _GENERIC_TITLE_TERMS:
            if f" {term} " in padded or padded.startswith(f"{term} ") or padded.endswith(f" {term}"):
                sources.append(f"title_contains_{term.replace(' ', '_')}")
                return 100.0, sources

    return 0.0, []


def _description_signal(subtitle: str, description: str) -> tuple[float, List[str]]:
    """
    Compute description signal (0 or 100) based on AI phrases found in
    subtitle + description text.  Returns on first match.
    """
    sources: List[str] = []
    text = f"{(subtitle or '')} {(description or '')}".lower()

    for phrase in AI_DESCRIPTION_PHRASES:
        if phrase in text:
            label = phrase.replace(" ", "_").replace("-", "_")
            sources.append(f"description_{label}")
            return 100.0, sources

    return 0.0, []


def _feature_gap_signal(feature_gaps: List[Any]) -> tuple[float, List[str]]:
    """
    Compute feature-gap signal (0 or 100) based on AI-related feature requests
    found in FeatureGap rows (or plain dicts with a 'feature' key).

    Takes the first matching gap and returns immediately.
    """
    sources: List[str] = []
    for gap in feature_gaps:
        feature_name = (
            gap.feature_name if hasattr(gap, "feature_name") else gap.get("feature", "")
        ).lower()
        for phrase in FEATURE_GAP_AI_PHRASES:
            if phrase in feature_name:
                label = phrase.replace(" ", "_").replace("-", "_")
                sources.append(f"feature_gap_{label}")
                return 100.0, sources

    return 0.0, []


def _category_signal(primary_category: str) -> tuple[float, List[str]]:
    """
    Compute category signal (0 or 100) by checking if the app's primary_category
    name (string, NOT an ID) matches any known AI-opportunity category.
    """
    sources: List[str] = []
    cat = (primary_category or "").lower()

    for substring, label in AI_OPPORTUNITY_CATEGORIES.items():
        if substring in cat:
            sources.append(label)
            return 100.0, sources

    return 0.0, []


def _keyword_signal(discovered_keywords: List[Any]) -> tuple[float, List[str]]:
    """
    Compute keyword signal (0 or 100) based on AppDiscoveredKeyword rows
    (or plain dicts with a 'keyword' key) matching AI-related keyword phrases.
    """
    sources: List[str] = []
    for kw in discovered_keywords:
        term = (
            kw.keyword if hasattr(kw, "keyword") else kw.get("keyword", "")
        ).lower()
        for phrase in AI_RELATED_KEYWORD_PHRASES:
            if phrase in term:
                label = phrase.replace(" ", "_").replace("-", "_")
                sources.append(f"keyword_{label}")
                return 100.0, sources

    return 0.0, []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_ai_potential_v2(
    app: Any,
    feature_gaps: List[Any] = None,
    discovered_keywords: List[Any] = None,
) -> Dict[str, Any]:
    """
    Compute a weighted AI potential score for an app.

    Parameters
    ----------
    app:
        An App ORM object (or any object with attributes: name, subtitle,
        description, primary_category).
    feature_gaps:
        List of FeatureGap ORM objects or dicts with 'feature' key.
    discovered_keywords:
        List of AppDiscoveredKeyword ORM objects or dicts with 'keyword' key.

    Returns
    -------
    dict with keys:
        ai_potential_score   : float  (0-100)
        ai_opportunity_type  : str    ("ai_native" | "ai_enhanced" | "weak")
        ai_signal_sources    : list   (labels of detected signals)
    """
    if feature_gaps is None:
        feature_gaps = []
    if discovered_keywords is None:
        discovered_keywords = []

    app_name     = getattr(app, "name", "") or ""
    subtitle     = getattr(app, "subtitle", "") or ""
    description  = getattr(app, "description", "") or ""
    primary_cat  = getattr(app, "primary_category", "") or ""

    # Compute each signal
    t_score,  t_sources  = _title_signal(app_name, subtitle)
    d_score,  d_sources  = _description_signal(subtitle, description)
    fg_score, fg_sources = _feature_gap_signal(feature_gaps)
    c_score,  c_sources  = _category_signal(primary_cat)
    k_score,  k_sources  = _keyword_signal(discovered_keywords)

    # Weighted combination
    raw = (
        t_score  * _W_TITLE +
        d_score  * _W_DESCRIPTION +
        fg_score * _W_FEATURE_GAP +
        c_score  * _W_CATEGORY +
        k_score  * _W_KEYWORD
    )
    score = round(min(max(raw, 0.0), 100.0), 2)

    # Classify
    if score >= _THRESHOLD_NATIVE:
        opportunity_type = "ai_native"
    elif score >= _THRESHOLD_ENHANCED:
        opportunity_type = "ai_enhanced"
    else:
        opportunity_type = "weak"

    all_sources = t_sources + d_sources + fg_sources + c_sources + k_sources

    return {
        "ai_potential_score":  score,
        "ai_opportunity_type": opportunity_type,
        "ai_signal_sources":   all_sources,
    }
