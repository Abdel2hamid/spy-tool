"""
Rank Curves — Category-aware daily download bands.

Each category maps rank ranges to (daily_low, daily_high) download estimates.
Based on public developer data, app store analytics reports, and academic research.

Usage:
    from app.config.rank_curves import interpolate_rank_downloads
    lo, hi = interpolate_rank_downloads(rank=15, category="games")
"""

import math
from typing import Dict, Tuple, Optional

# Dict[category_slug, Dict[tuple(rank_lo, rank_hi), tuple(daily_lo, daily_hi)]]
# Bands: (1,5), (6,20), (21,50), (51,100), (101,300), (301,500), (501,1000), (1001,inf)
RANK_CURVES: Dict[str, Dict[Tuple[int, int], Tuple[int, int]]] = {
    "games": {
        (1, 5):       (200_000, 600_000),
        (6, 20):      (60_000,  200_000),
        (21, 50):     (20_000,   60_000),
        (51, 100):    (8_000,    20_000),
        (101, 300):   (2_000,     8_000),
        (301, 500):   (600,       2_000),
        (501, 1000):  (150,         600),
        (1001, 9999): (20,          150),
    },
    "social": {
        (1, 5):       (100_000, 350_000),
        (6, 20):      (35_000,  100_000),
        (21, 50):     (12_000,   35_000),
        (51, 100):    (4_000,    12_000),
        (101, 300):   (1_000,     4_000),
        (301, 500):   (300,       1_000),
        (501, 1000):  (80,          300),
        (1001, 9999): (10,           80),
    },
    "social networking": {
        (1, 5):       (100_000, 350_000),
        (6, 20):      (35_000,  100_000),
        (21, 50):     (12_000,   35_000),
        (51, 100):    (4_000,    12_000),
        (101, 300):   (1_000,     4_000),
        (301, 500):   (300,       1_000),
        (501, 1000):  (80,          300),
        (1001, 9999): (10,           80),
    },
    "productivity": {
        (1, 5):       (30_000,   90_000),
        (6, 20):      (10_000,   30_000),
        (21, 50):     (3_500,    10_000),
        (51, 100):    (1_200,     3_500),
        (101, 300):   (300,       1_200),
        (301, 500):   (90,          300),
        (501, 1000):  (25,           90),
        (1001, 9999): (5,            25),
    },
    "finance": {
        (1, 5):       (20_000,   60_000),
        (6, 20):      (7_000,    20_000),
        (21, 50):     (2_500,     7_000),
        (51, 100):    (800,       2_500),
        (101, 300):   (200,         800),
        (301, 500):   (60,          200),
        (501, 1000):  (15,           60),
        (1001, 9999): (3,            15),
    },
    "photo": {
        (1, 5):       (40_000,  120_000),
        (6, 20):      (14_000,   40_000),
        (21, 50):     (5_000,    14_000),
        (51, 100):    (1_700,     5_000),
        (101, 300):   (400,       1_700),
        (301, 500):   (120,         400),
        (501, 1000):  (30,          120),
        (1001, 9999): (5,            30),
    },
    "photo & video": {
        (1, 5):       (40_000,  120_000),
        (6, 20):      (14_000,   40_000),
        (21, 50):     (5_000,    14_000),
        (51, 100):    (1_700,     5_000),
        (101, 300):   (400,       1_700),
        (301, 500):   (120,         400),
        (501, 1000):  (30,          120),
        (1001, 9999): (5,            30),
    },
    "utilities": {
        (1, 5):       (15_000,   50_000),
        (6, 20):      (5_000,    15_000),
        (21, 50):     (1_800,     5_000),
        (51, 100):    (600,       1_800),
        (101, 300):   (150,         600),
        (301, 500):   (45,          150),
        (501, 1000):  (12,           45),
        (1001, 9999): (2,            12),
    },
    "health": {
        (1, 5):       (20_000,   70_000),
        (6, 20):      (7_000,    20_000),
        (21, 50):     (2_500,     7_000),
        (51, 100):    (800,       2_500),
        (101, 300):   (200,         800),
        (301, 500):   (60,          200),
        (501, 1000):  (15,           60),
        (1001, 9999): (3,            15),
    },
    "health & fitness": {
        (1, 5):       (20_000,   70_000),
        (6, 20):      (7_000,    20_000),
        (21, 50):     (2_500,     7_000),
        (51, 100):    (800,       2_500),
        (101, 300):   (200,         800),
        (301, 500):   (60,          200),
        (501, 1000):  (15,           60),
        (1001, 9999): (3,            15),
    },
    "lifestyle": {
        (1, 5):       (15_000,   55_000),
        (6, 20):      (5_000,    15_000),
        (21, 50):     (1_800,     5_000),
        (51, 100):    (600,       1_800),
        (101, 300):   (150,         600),
        (301, 500):   (45,          150),
        (501, 1000):  (12,           45),
        (1001, 9999): (2,            12),
    },
    "education": {
        (1, 5):       (18_000,   55_000),
        (6, 20):      (6_000,    18_000),
        (21, 50):     (2_000,     6_000),
        (51, 100):    (700,       2_000),
        (101, 300):   (170,         700),
        (301, 500):   (50,          170),
        (501, 1000):  (12,           50),
        (1001, 9999): (2,            12),
    },
    "entertainment": {
        (1, 5):       (50_000,  150_000),
        (6, 20):      (18_000,   50_000),
        (21, 50):     (6_000,    18_000),
        (51, 100):    (2_000,     6_000),
        (101, 300):   (500,       2_000),
        (301, 500):   (150,         500),
        (501, 1000):  (40,          150),
        (1001, 9999): (8,            40),
    },
    "shopping": {
        (1, 5):       (35_000,  100_000),
        (6, 20):      (12_000,   35_000),
        (21, 50):     (4_000,    12_000),
        (51, 100):    (1_400,     4_000),
        (101, 300):   (350,       1_400),
        (301, 500):   (100,         350),
        (501, 1000):  (25,          100),
        (1001, 9999): (5,            25),
    },
    "travel": {
        (1, 5):       (20_000,   60_000),
        (6, 20):      (7_000,    20_000),
        (21, 50):     (2_500,     7_000),
        (51, 100):    (800,       2_500),
        (101, 300):   (200,         800),
        (301, 500):   (60,          200),
        (501, 1000):  (15,           60),
        (1001, 9999): (3,            15),
    },
    "food": {
        (1, 5):       (18_000,   55_000),
        (6, 20):      (6_000,    18_000),
        (21, 50):     (2_000,     6_000),
        (51, 100):    (700,       2_000),
        (101, 300):   (170,         700),
        (301, 500):   (50,          170),
        (501, 1000):  (12,           50),
        (1001, 9999): (2,            12),
    },
    "food & drink": {
        (1, 5):       (18_000,   55_000),
        (6, 20):      (6_000,    18_000),
        (21, 50):     (2_000,     6_000),
        (51, 100):    (700,       2_000),
        (101, 300):   (170,         700),
        (301, 500):   (50,          170),
        (501, 1000):  (12,           50),
        (1001, 9999): (2,            12),
    },
    "music": {
        (1, 5):       (45_000,  130_000),
        (6, 20):      (15_000,   45_000),
        (21, 50):     (5_000,    15_000),
        (51, 100):    (1_700,     5_000),
        (101, 300):   (400,       1_700),
        (301, 500):   (120,         400),
        (501, 1000):  (30,          120),
        (1001, 9999): (5,            30),
    },
    "news": {
        (1, 5):       (25_000,   75_000),
        (6, 20):      (8_000,    25_000),
        (21, 50):     (2_800,     8_000),
        (51, 100):    (900,       2_800),
        (101, 300):   (220,         900),
        (301, 500):   (65,          220),
        (501, 1000):  (16,           65),
        (1001, 9999): (3,            16),
    },
    "navigation": {
        (1, 5):       (20_000,   60_000),
        (6, 20):      (7_000,    20_000),
        (21, 50):     (2_500,     7_000),
        (51, 100):    (800,       2_500),
        (101, 300):   (200,         800),
        (301, 500):   (60,          200),
        (501, 1000):  (15,           60),
        (1001, 9999): (3,            15),
    },
    "sports": {
        (1, 5):       (30_000,   90_000),
        (6, 20):      (10_000,   30_000),
        (21, 50):     (3_500,    10_000),
        (51, 100):    (1_200,     3_500),
        (101, 300):   (300,       1_200),
        (301, 500):   (90,          300),
        (501, 1000):  (25,           90),
        (1001, 9999): (5,            25),
    },
    "business": {
        (1, 5):       (12_000,   40_000),
        (6, 20):      (4_000,    12_000),
        (21, 50):     (1_400,     4_000),
        (51, 100):    (450,       1_400),
        (101, 300):   (110,         450),
        (301, 500):   (33,          110),
        (501, 1000):  (8,            33),
        (1001, 9999): (2,             8),
    },
    "weather": {
        (1, 5):       (22_000,   65_000),
        (6, 20):      (7_500,    22_000),
        (21, 50):     (2_600,     7_500),
        (51, 100):    (850,       2_600),
        (101, 300):   (210,         850),
        (301, 500):   (63,          210),
        (501, 1000):  (16,           63),
        (1001, 9999): (3,            16),
    },
    "medical": {
        (1, 5):       (8_000,    25_000),
        (6, 20):      (2_700,     8_000),
        (21, 50):     (950,       2_700),
        (51, 100):    (300,         950),
        (101, 300):   (75,          300),
        (301, 500):   (22,           75),
        (501, 1000):  (6,            22),
        (1001, 9999): (1,             6),
    },
    "reference": {
        (1, 5):       (10_000,   30_000),
        (6, 20):      (3_300,    10_000),
        (21, 50):     (1_100,     3_300),
        (51, 100):    (370,       1_100),
        (101, 300):   (90,          370),
        (301, 500):   (27,           90),
        (501, 1000):  (7,            27),
        (1001, 9999): (1,             7),
    },
    "books": {
        (1, 5):       (12_000,   40_000),
        (6, 20):      (4_000,    12_000),
        (21, 50):     (1_400,     4_000),
        (51, 100):    (450,       1_400),
        (101, 300):   (110,         450),
        (301, 500):   (33,          110),
        (501, 1000):  (8,            33),
        (1001, 9999): (2,             8),
    },
    "graphics & design": {
        (1, 5):       (12_000,   38_000),
        (6, 20):      (4_000,    12_000),
        (21, 50):     (1_400,     4_000),
        (51, 100):    (450,       1_400),
        (101, 300):   (110,         450),
        (301, 500):   (33,          110),
        (501, 1000):  (8,            33),
        (1001, 9999): (2,             8),
    },
    "developer tools": {
        (1, 5):       (6_000,    18_000),
        (6, 20):      (2_000,     6_000),
        (21, 50):     (700,       2_000),
        (51, 100):    (220,         700),
        (101, 300):   (55,          220),
        (301, 500):   (16,           55),
        (501, 1000):  (4,            16),
        (1001, 9999): (1,             4),
    },
    # Fallback for unknown / unmapped categories
    "default": {
        (1, 5):       (25_000,   80_000),
        (6, 20):      (8_500,    25_000),
        (21, 50):     (3_000,     8_500),
        (51, 100):    (1_000,     3_000),
        (101, 300):   (250,       1_000),
        (301, 500):   (75,          250),
        (501, 1000):  (20,           75),
        (1001, 9999): (3,            20),
    },
}

# Reliability weight per category — used by ConfidenceEngine
# Higher = more public data available → higher confidence ceiling
CATEGORY_CURVE_RELIABILITY: Dict[str, float] = {
    "games": 0.85,
    "social": 0.75,
    "social networking": 0.75,
    "entertainment": 0.78,
    "productivity": 0.80,
    "finance": 0.70,
    "photo": 0.78,
    "photo & video": 0.78,
    "utilities": 0.72,
    "health": 0.73,
    "health & fitness": 0.73,
    "lifestyle": 0.70,
    "education": 0.72,
    "shopping": 0.74,
    "travel": 0.68,
    "food": 0.68,
    "food & drink": 0.68,
    "music": 0.76,
    "news": 0.70,
    "sports": 0.72,
    "navigation": 0.68,
    "business": 0.68,
    "weather": 0.72,
    "medical": 0.62,
    "reference": 0.65,
    "books": 0.67,
    "graphics & design": 0.67,
    "developer tools": 0.65,
    "default": 0.65,
}


def _fuzzy_match_category(category: str) -> str:
    """Return the best matching key in RANK_CURVES for a category string."""
    if not category:
        return "default"
    cat_lower = category.lower().strip()
    # Exact match
    if cat_lower in RANK_CURVES:
        return cat_lower
    # Substring match
    for key in RANK_CURVES:
        if key == "default":
            continue
        if key in cat_lower or cat_lower in key:
            return key
    return "default"


# Fixed uncertainty spread around the central estimate. A symmetric ±40% range
# keeps the (lo, hi) bounds monotonic whenever the central estimate is
# monotonic, which the original band-ratio approach did not guarantee at
# band edges.
_ESTIMATE_SPREAD = 1.4


def interpolate_rank_downloads(rank: int, category: str) -> Tuple[int, int]:
    """
    Return (daily_lo, daily_hi) for a given rank in a given category.

    Uses log-linear interpolation within each band so that the transition
    between bands is smooth and monotonic: a worse rank never returns more
    downloads than a better rank, and adjacent bands meet at their shared
    boundary.

    For a band ``(lo_rank, hi_rank) -> (lo_dl, hi_dl)``:
      - ``lo_rank`` (the best rank in the band) maps to ``hi_dl``.
      - ``hi_rank`` (the worst rank in the band) maps to ``lo_dl``.

    Args:
        rank: Chart rank (1 = #1, positive integer)
        category: Category name string (fuzzy-matched to known categories)

    Returns:
        Tuple of (daily_low, daily_high) download estimates
    """
    if rank is None or rank <= 0:
        return (0, 0)

    cat_key = _fuzzy_match_category(category)
    bands = RANK_CURVES[cat_key]

    sorted_bands = sorted(bands.items())
    for (lo_rank, hi_rank), (lo_dl, hi_dl) in sorted_bands:
        if lo_rank <= rank <= hi_rank:
            # Degenerate single-rank band
            if lo_rank == hi_rank:
                return (lo_dl, hi_dl)

            # Log-linear position inside the band: 0.0 at lo_rank, 1.0 at hi_rank
            try:
                t = (math.log(rank) - math.log(lo_rank)) / (
                    math.log(hi_rank) - math.log(lo_rank)
                )
            except (ValueError, ZeroDivisionError):
                t = 0.5
            t = max(0.0, min(1.0, t))

            # Central estimate: decreases from hi_dl (best rank) to lo_dl (worst rank)
            central = hi_dl * (1 - t) + lo_dl * t

            # Symmetric uncertainty spread. Because the spread factor is constant,
            # monotonicity of the central estimate guarantees monotonicity of
            # both bounds and continuity at band boundaries.
            lo = max(1, int(central / _ESTIMATE_SPREAD))
            hi = max(lo, int(central * _ESTIMATE_SPREAD))
            return (lo, hi)

    # Rank beyond all bands — use the lowest (long-tail) band values as a floor
    return sorted_bands[-1][1]


def get_category_reliability(category: str) -> float:
    """Return reliability weight for a category (0.0–1.0)."""
    cat_key = _fuzzy_match_category(category)
    return CATEGORY_CURVE_RELIABILITY.get(cat_key, CATEGORY_CURVE_RELIABILITY["default"])
