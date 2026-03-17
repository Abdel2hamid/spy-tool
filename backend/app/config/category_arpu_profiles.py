"""
Category ARPU Profiles
======================
Rich per-category revenue profiles replacing the flat ARPU dict in revenue_estimator.py.

Each profile includes:
  arpu_low / arpu_medium / arpu_high  — monthly revenue per active paying user
  primary_model                        — dominant monetization model
  monetization_hint                    — human-readable hint for the frontend
  iap_conversion_rate                  — fraction of MAU making a purchase/subscribing
  active_fraction                      — fraction of installs that are MAU

Values calibrated against public developer case studies, App Store benchmarks,
and Sensor Tower / data.ai published category reports.
"""

from typing import Dict, Optional

CATEGORY_ARPU_PROFILES: Dict[str, dict] = {
    "games": {
        "arpu_low": 0.60,
        "arpu_medium": 1.50,
        "arpu_high": 4.50,
        "primary_model": "iap",
        "monetization_hint": "ad-driven",
        "iap_conversion_rate": 0.05,   # 5% of MAU make a purchase
        "active_fraction": 0.20,       # 20% of installs are MAU
    },
    "social networking": {
        "arpu_low": 0.40,
        "arpu_medium": 1.20,
        "arpu_high": 3.00,
        "primary_model": "ads",
        "monetization_hint": "ad-driven",
        "iap_conversion_rate": 0.03,
        "active_fraction": 0.35,
    },
    "social": {
        "arpu_low": 0.40,
        "arpu_medium": 1.20,
        "arpu_high": 3.00,
        "primary_model": "ads",
        "monetization_hint": "ad-driven",
        "iap_conversion_rate": 0.03,
        "active_fraction": 0.35,
    },
    "productivity": {
        "arpu_low": 1.50,
        "arpu_medium": 2.50,
        "arpu_high": 6.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.07,
        "active_fraction": 0.18,
    },
    "finance": {
        "arpu_low": 2.00,
        "arpu_medium": 4.50,
        "arpu_high": 12.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.08,
        "active_fraction": 0.12,
    },
    "business": {
        "arpu_low": 2.00,
        "arpu_medium": 3.50,
        "arpu_high": 9.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.07,
        "active_fraction": 0.14,
    },
    "photo & video": {
        "arpu_low": 1.20,
        "arpu_medium": 3.20,
        "arpu_high": 8.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.06,
        "active_fraction": 0.15,
    },
    "photo": {
        "arpu_low": 1.20,
        "arpu_medium": 3.20,
        "arpu_high": 8.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.06,
        "active_fraction": 0.15,
    },
    "health & fitness": {
        "arpu_low": 1.50,
        "arpu_medium": 3.50,
        "arpu_high": 9.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.07,
        "active_fraction": 0.14,
    },
    "health": {
        "arpu_low": 1.50,
        "arpu_medium": 3.50,
        "arpu_high": 9.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.07,
        "active_fraction": 0.14,
    },
    "fitness": {
        "arpu_low": 1.50,
        "arpu_medium": 3.50,
        "arpu_high": 9.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.07,
        "active_fraction": 0.14,
    },
    "utilities": {
        "arpu_low": 0.80,
        "arpu_medium": 1.80,
        "arpu_high": 4.50,
        "primary_model": "mixed",
        "monetization_hint": "mixed",
        "iap_conversion_rate": 0.05,
        "active_fraction": 0.16,
    },
    "lifestyle": {
        "arpu_low": 0.80,
        "arpu_medium": 2.10,
        "arpu_high": 5.50,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.05,
        "active_fraction": 0.14,
    },
    "education": {
        "arpu_low": 1.00,
        "arpu_medium": 2.20,
        "arpu_high": 6.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.06,
        "active_fraction": 0.13,
    },
    "entertainment": {
        "arpu_low": 0.50,
        "arpu_medium": 1.20,
        "arpu_high": 3.00,
        "primary_model": "mixed",
        "monetization_hint": "mixed",
        "iap_conversion_rate": 0.04,
        "active_fraction": 0.20,
    },
    "travel": {
        "arpu_low": 1.00,
        "arpu_medium": 2.50,
        "arpu_high": 6.50,
        "primary_model": "mixed",
        "monetization_hint": "mixed",
        "iap_conversion_rate": 0.05,
        "active_fraction": 0.10,
    },
    "food & drink": {
        "arpu_low": 0.50,
        "arpu_medium": 1.60,
        "arpu_high": 4.00,
        "primary_model": "mixed",
        "monetization_hint": "mixed",
        "iap_conversion_rate": 0.04,
        "active_fraction": 0.12,
    },
    "food": {
        "arpu_low": 0.50,
        "arpu_medium": 1.60,
        "arpu_high": 4.00,
        "primary_model": "mixed",
        "monetization_hint": "mixed",
        "iap_conversion_rate": 0.04,
        "active_fraction": 0.12,
    },
    "navigation": {
        "arpu_low": 0.80,
        "arpu_medium": 1.80,
        "arpu_high": 5.00,
        "primary_model": "mixed",
        "monetization_hint": "mixed",
        "iap_conversion_rate": 0.05,
        "active_fraction": 0.12,
    },
    "news": {
        "arpu_low": 0.60,
        "arpu_medium": 1.50,
        "arpu_high": 4.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.05,
        "active_fraction": 0.20,
    },
    "sports": {
        "arpu_low": 0.70,
        "arpu_medium": 1.80,
        "arpu_high": 5.00,
        "primary_model": "mixed",
        "monetization_hint": "mixed",
        "iap_conversion_rate": 0.04,
        "active_fraction": 0.15,
    },
    "shopping": {
        "arpu_low": 0.30,
        "arpu_medium": 0.80,
        "arpu_high": 2.50,
        "primary_model": "ads",
        "monetization_hint": "ad-driven",
        "iap_conversion_rate": 0.03,
        "active_fraction": 0.18,
    },
    "books": {
        "arpu_low": 0.70,
        "arpu_medium": 1.50,
        "arpu_high": 4.00,
        "primary_model": "iap",
        "monetization_hint": "iap",
        "iap_conversion_rate": 0.05,
        "active_fraction": 0.12,
    },
    "reference": {
        "arpu_low": 0.60,
        "arpu_medium": 1.20,
        "arpu_high": 3.50,
        "primary_model": "mixed",
        "monetization_hint": "mixed",
        "iap_conversion_rate": 0.04,
        "active_fraction": 0.12,
    },
    "medical": {
        "arpu_low": 1.00,
        "arpu_medium": 2.00,
        "arpu_high": 6.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.06,
        "active_fraction": 0.10,
    },
    "weather": {
        "arpu_low": 0.30,
        "arpu_medium": 0.80,
        "arpu_high": 2.50,
        "primary_model": "mixed",
        "monetization_hint": "mixed",
        "iap_conversion_rate": 0.03,
        "active_fraction": 0.25,
    },
    "music": {
        "arpu_low": 1.00,
        "arpu_medium": 2.80,
        "arpu_high": 7.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.06,
        "active_fraction": 0.20,
    },
    "graphics & design": {
        "arpu_low": 1.50,
        "arpu_medium": 3.00,
        "arpu_high": 8.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.07,
        "active_fraction": 0.14,
    },
    "developer tools": {
        "arpu_low": 2.00,
        "arpu_medium": 3.50,
        "arpu_high": 10.00,
        "primary_model": "subscription",
        "monetization_hint": "subscription",
        "iap_conversion_rate": 0.08,
        "active_fraction": 0.12,
    },
    "catalogs": {
        "arpu_low": 0.30,
        "arpu_medium": 0.70,
        "arpu_high": 2.00,
        "primary_model": "ads",
        "monetization_hint": "ad-driven",
        "iap_conversion_rate": 0.02,
        "active_fraction": 0.10,
    },
    # Fallback
    "default": {
        "arpu_low": 0.80,
        "arpu_medium": 2.00,
        "arpu_high": 5.00,
        "primary_model": "mixed",
        "monetization_hint": "unknown",
        "iap_conversion_rate": 0.05,
        "active_fraction": 0.15,
    },
}


def get_arpu_profile(category: Optional[str]) -> dict:
    """
    Return ARPU profile for a category with fuzzy matching and fallback to default.

    Args:
        category: Category name string (case-insensitive, partial match supported)

    Returns:
        ARPU profile dict with all fields populated
    """
    if not category:
        return CATEGORY_ARPU_PROFILES["default"]

    cat_lower = category.lower().strip()

    # Exact match
    if cat_lower in CATEGORY_ARPU_PROFILES:
        return CATEGORY_ARPU_PROFILES[cat_lower]

    # Substring match
    for key, profile in CATEGORY_ARPU_PROFILES.items():
        if key == "default":
            continue
        if key in cat_lower or cat_lower in key:
            return profile

    return CATEGORY_ARPU_PROFILES["default"]
