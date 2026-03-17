"""
Calibration Profiles
====================
Per-category multipliers for fine-tuning the download estimator without changing core logic.

To adjust estimates for a specific category, edit only the values here.
No changes to download_estimator.py are needed.

Fields:
  rank_curve_factor     — scales the rank-curve daily estimate (1.0 = no adjustment)
  review_ratio_factor   — scales the review-velocity estimate
  confidence_ceiling    — maximum confidence score achievable for this category
"""

from typing import Dict, Optional

CALIBRATION_PROFILES: Dict[str, dict] = {
    "games": {
        "rank_curve_factor": 1.0,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.88,
    },
    "social networking": {
        "rank_curve_factor": 0.95,
        "review_ratio_factor": 0.90,
        "confidence_ceiling": 0.80,
    },
    "social": {
        "rank_curve_factor": 0.95,
        "review_ratio_factor": 0.90,
        "confidence_ceiling": 0.80,
    },
    "productivity": {
        "rank_curve_factor": 0.90,
        "review_ratio_factor": 1.05,
        "confidence_ceiling": 0.82,
    },
    "finance": {
        "rank_curve_factor": 0.85,
        "review_ratio_factor": 1.10,
        "confidence_ceiling": 0.78,
    },
    "business": {
        "rank_curve_factor": 0.88,
        "review_ratio_factor": 1.08,
        "confidence_ceiling": 0.78,
    },
    "photo & video": {
        "rank_curve_factor": 0.95,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.82,
    },
    "photo": {
        "rank_curve_factor": 0.95,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.82,
    },
    "health & fitness": {
        "rank_curve_factor": 0.90,
        "review_ratio_factor": 1.05,
        "confidence_ceiling": 0.80,
    },
    "health": {
        "rank_curve_factor": 0.90,
        "review_ratio_factor": 1.05,
        "confidence_ceiling": 0.80,
    },
    "fitness": {
        "rank_curve_factor": 0.90,
        "review_ratio_factor": 1.05,
        "confidence_ceiling": 0.80,
    },
    "utilities": {
        "rank_curve_factor": 0.92,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.80,
    },
    "lifestyle": {
        "rank_curve_factor": 0.92,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.78,
    },
    "education": {
        "rank_curve_factor": 0.90,
        "review_ratio_factor": 1.02,
        "confidence_ceiling": 0.80,
    },
    "entertainment": {
        "rank_curve_factor": 1.0,
        "review_ratio_factor": 0.95,
        "confidence_ceiling": 0.82,
    },
    "travel": {
        "rank_curve_factor": 0.88,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.76,
    },
    "food & drink": {
        "rank_curve_factor": 0.88,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.76,
    },
    "food": {
        "rank_curve_factor": 0.88,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.76,
    },
    "navigation": {
        "rank_curve_factor": 0.88,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.76,
    },
    "news": {
        "rank_curve_factor": 0.90,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.78,
    },
    "sports": {
        "rank_curve_factor": 0.92,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.79,
    },
    "shopping": {
        "rank_curve_factor": 0.95,
        "review_ratio_factor": 0.95,
        "confidence_ceiling": 0.79,
    },
    "books": {
        "rank_curve_factor": 0.92,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.78,
    },
    "reference": {
        "rank_curve_factor": 0.88,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.76,
    },
    "medical": {
        "rank_curve_factor": 0.85,
        "review_ratio_factor": 1.05,
        "confidence_ceiling": 0.72,
    },
    "weather": {
        "rank_curve_factor": 0.90,
        "review_ratio_factor": 0.95,
        "confidence_ceiling": 0.78,
    },
    "music": {
        "rank_curve_factor": 0.95,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.82,
    },
    "graphics & design": {
        "rank_curve_factor": 0.90,
        "review_ratio_factor": 1.02,
        "confidence_ceiling": 0.79,
    },
    "developer tools": {
        "rank_curve_factor": 0.88,
        "review_ratio_factor": 1.05,
        "confidence_ceiling": 0.76,
    },
    "default": {
        "rank_curve_factor": 1.0,
        "review_ratio_factor": 1.0,
        "confidence_ceiling": 0.82,
    },
}


def _fuzzy_match(category: str) -> str:
    """Return the best matching key in CALIBRATION_PROFILES."""
    if not category:
        return "default"
    cat_lower = category.lower().strip()
    if cat_lower in CALIBRATION_PROFILES:
        return cat_lower
    for key in CALIBRATION_PROFILES:
        if key == "default":
            continue
        if key in cat_lower or cat_lower in key:
            return key
    return "default"


def get_calibration(category: Optional[str]) -> dict:
    """
    Return calibration profile for a category with fuzzy match + fallback.

    Args:
        category: Category name string

    Returns:
        Calibration profile dict
    """
    return CALIBRATION_PROFILES[_fuzzy_match(category or "")]
