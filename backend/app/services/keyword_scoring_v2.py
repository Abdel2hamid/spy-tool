"""
Keyword Scoring V2 — Multi-signal ASO keyword scoring system.

Complete rewrite of the keyword scoring pipeline. Replaces the single-signal
heuristics with weighted fusion of multiple data sources (Apple autocomplete,
Google Trends, iTunes ecosystem metrics, DataForSEO web volume) and adds
per-app "can I rank?" analysis plus organic install estimation.

All scoring functions are module-level for easy testing and reuse.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BIG_BRAND_DEVS: frozenset[str] = frozenset(
    {
        "openai",
        "google",
        "meta platforms",
        "microsoft",
        "apple inc",
        "amazon.com",
        "adobe",
        "netflix",
        "spotify",
        "bytedance",
        "tiktok",
        "snap inc",
        "pinterest",
        "samsung",
        "shopify",
        "salesforce",
        "zoom video",
        "duolingo",
        "match group",
        "epic games",
        "electronic arts",
        "king",
        "supercell",
        "disney",
        "reddit inc",
    }
)

# Click-through rate by search-result position (industry research).
_CTR_BY_RANK: dict[int, float] = {
    1: 0.35,
    2: 0.18,
    3: 0.11,
    4: 0.08,
    5: 0.06,
    6: 0.04,
    7: 0.03,
    8: 0.025,
    9: 0.02,
    10: 0.015,
}


# ---------------------------------------------------------------------------
# 1. Volume Score — Multi-Signal Fusion
# ---------------------------------------------------------------------------


def compute_volume_score(
    apps_count: int = 0,
    autocomplete_rank: int = 0,
    trend_score: float = 0.0,
    search_volume: int = 0,
    top5_avg_ratings: float = 0.0,
) -> float:
    """Return a 0-100 volume score by fusing all available popularity signals.

    Parameters
    ----------
    apps_count:
        Number of results returned by the iTunes Search API.
    autocomplete_rank:
        Position in Apple's autocomplete suggestions (1 = most popular).
        0 means the keyword was *not* suggested.
    trend_score:
        Google Trends interest score (0-100).
    search_volume:
        DataForSEO / Google Ads monthly search volume (when available).
    top5_avg_ratings:
        Average ``userRatingCount`` of the top 5 apps for this keyword.
        Acts as a proxy for market size.
    """

    # Short-circuit: nothing to score.
    if (
        apps_count == 0
        and autocomplete_rank == 0
        and trend_score == 0.0
        and search_volume == 0
        and top5_avg_ratings == 0.0
    ):
        return 0.0

    # --- Autocomplete signal (0-30) ---
    # Strongest free signal — Apple's own ranking of popularity.
    if autocomplete_rank >= 1:
        # Linear interpolation: rank 1 -> 30, rank 20 -> 6.
        # Clamp between 0 and 30.
        autocomplete_pts = max(30.0 - (autocomplete_rank - 1) * (24.0 / 19.0), 0.0)
        autocomplete_pts = min(autocomplete_pts, 30.0)
    else:
        autocomplete_pts = 0.0

    # --- Google Trends (0-25) ---
    trends_pts = min(max(trend_score, 0.0), 100.0) / 100.0 * 25.0

    # --- App ecosystem signal (0-20) ---
    # log10(avg_ratings + 1) / log10(500_001) normalised to 20.
    if top5_avg_ratings > 0:
        ecosystem_pts = min(
            math.log10(top5_avg_ratings + 1) / math.log10(500_001) * 20.0, 20.0
        )
    else:
        ecosystem_pts = 0.0

    # --- iTunes result count (0-15) ---
    if apps_count > 0:
        itunes_pts = min(
            math.log10(apps_count + 1) / math.log10(501) * 15.0, 15.0
        )
    else:
        itunes_pts = 0.0

    # --- DataForSEO web volume (0-10) ---
    if search_volume > 0:
        dataseo_pts = min(
            math.log10(search_volume + 1) / math.log10(1_000_001) * 10.0, 10.0
        )
    else:
        dataseo_pts = 0.0

    total = autocomplete_pts + trends_pts + ecosystem_pts + itunes_pts + dataseo_pts
    return min(round(total, 2), 100.0)


# ---------------------------------------------------------------------------
# 2. Difficulty Score — Full Top-10 Analysis
# ---------------------------------------------------------------------------


def compute_difficulty_score(
    top_apps: list[dict],
    keyword: str = "",
) -> dict:
    """Analyse the top 10 search results to produce a 0-100 difficulty score.

    Parameters
    ----------
    top_apps:
        Up to 10 dicts, each with keys ``trackName``, ``artistName``,
        ``userRatingCount``, ``averageUserRating``.
    keyword:
        The search term (used for title-match analysis).

    Returns
    -------
    dict with ``difficulty_score`` (0-100 composite) plus individual
    component scores and metadata.
    """

    n = len(top_apps)

    # Default response when there is no data.
    if n == 0:
        return {
            "difficulty_score": 0.0,
            "incumbent_strength": 0.0,
            "title_saturation": 0.0,
            "brand_dominance": 0.0,
            "rating_quality": 0.0,
            "market_concentration": 0.0,
            "top_player": "",
            "brand_count": 0,
        }

    # --- Incumbent strength (0-35) ---
    def _review_tier(count: int) -> int:
        if count >= 1_000_000:
            return 10
        if count >= 100_000:
            return 8
        if count >= 10_000:
            return 5
        if count >= 1_000:
            return 3
        return 1

    tier_sum = sum(
        _review_tier(int(app.get("userRatingCount", 0) or 0)) for app in top_apps
    )
    incumbent_strength = min(tier_sum / 100.0 * 35.0, 35.0)

    # --- Title saturation (0-20) ---
    kw_lower = keyword.lower().strip()
    if kw_lower:
        title_matches = sum(
            1
            for app in top_apps
            if kw_lower in (app.get("trackName", "") or "").lower()
        )
    else:
        title_matches = 0
    title_saturation = (title_matches / 10.0) * 20.0

    # --- Brand dominance (0-20) ---
    brand_count = 0
    for app in top_apps:
        artist = (app.get("artistName", "") or "").lower().strip()
        if artist in _BIG_BRAND_DEVS:
            brand_count += 1
    brand_dominance = (brand_count / 10.0) * 20.0

    # --- Rating quality (0-10) ---
    ratings = [
        float(app.get("averageUserRating", 0) or 0)
        for app in top_apps
    ]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
    rating_quality = min(avg_rating / 5.0 * 10.0, 10.0)

    # --- Market concentration HHI (0-15) ---
    review_counts = [
        int(app.get("userRatingCount", 0) or 0) for app in top_apps
    ]
    total_reviews = sum(review_counts)
    if total_reviews > 0:
        hhi = sum((rc / total_reviews) ** 2 for rc in review_counts)
        market_concentration = min(hhi * 15.0, 15.0)
    else:
        market_concentration = 0.0

    difficulty = min(
        incumbent_strength
        + title_saturation
        + brand_dominance
        + rating_quality
        + market_concentration,
        100.0,
    )

    top_player = (top_apps[0].get("trackName", "") or "") if top_apps else ""

    return {
        "difficulty_score": round(difficulty, 2),
        "incumbent_strength": round(incumbent_strength, 2),
        "title_saturation": round(title_saturation, 2),
        "brand_dominance": round(brand_dominance, 2),
        "rating_quality": round(rating_quality, 2),
        "market_concentration": round(market_concentration, 2),
        "top_player": top_player,
        "brand_count": brand_count,
    }


# ---------------------------------------------------------------------------
# 3. Chance Score — Per-App "Can I Rank?"
# ---------------------------------------------------------------------------


def compute_chance_score(
    app_reviews: int = 0,
    app_rating: float = 0.0,
    app_rank: int | None = None,
    keyword_in_title: bool = False,
    keyword_in_subtitle: bool = False,
    difficulty_score: float = 50.0,
    top_apps: list[dict] | None = None,
) -> float:
    """Estimate how likely *your* app is to rank for a given keyword (0-100).

    Parameters
    ----------
    app_reviews:
        Your app's total review count.
    app_rating:
        Your app's average star rating.
    app_rank:
        Your app's current rank for this keyword, or ``None`` if unranked.
    keyword_in_title:
        Whether the keyword appears in your app's title.
    keyword_in_subtitle:
        Whether the keyword appears in your app's subtitle.
    difficulty_score:
        The composite difficulty score from :func:`compute_difficulty_score`.
    top_apps:
        Top 10 app dicts (same format as ``compute_difficulty_score``).
    """

    # --- Power ratio (0-35) ---
    if top_apps:
        weakest_reviews = min(
            int(app.get("userRatingCount", 0) or 0) for app in top_apps
        )
        ratio = min(app_reviews / max(weakest_reviews, 1), 3.0) / 3.0
        power_pts = ratio * 35.0
    else:
        # Fallback: invert difficulty as a rough proxy.
        power_pts = (100.0 - difficulty_score) / 100.0 * 35.0

    # --- Metadata relevance (0-25) ---
    if keyword_in_title:
        metadata_pts = 25.0
    elif keyword_in_subtitle:
        metadata_pts = 15.0
    else:
        metadata_pts = 0.0

    # --- Current position bonus (0-20) ---
    if app_rank is not None:
        if app_rank <= 3:
            position_pts = 20.0
        elif app_rank <= 10:
            position_pts = 15.0
        elif app_rank <= 30:
            position_pts = 10.0
        elif app_rank <= 100:
            position_pts = 5.0
        else:
            position_pts = 2.0
    else:
        position_pts = 0.0

    # --- Market openness (0-20) ---
    openness_pts = (100.0 - difficulty_score) / 100.0 * 20.0

    total = power_pts + metadata_pts + position_pts + openness_pts
    return min(round(total, 2), 100.0)


# ---------------------------------------------------------------------------
# 4. KEI — Keyword Efficiency Index
# ---------------------------------------------------------------------------


def compute_kei(volume_score: float, chance_score: float) -> float:
    """Geometric mean of volume and chance, emphasising volume slightly.

    Returns 0-100.  Returns 0 if either input is 0.
    """

    if volume_score <= 0 or chance_score <= 0:
        return 0.0

    kei = (volume_score ** 0.55) * (chance_score ** 0.45)
    return min(round(kei, 2), 100.0)


# ---------------------------------------------------------------------------
# 5. Organic Install Estimation
# ---------------------------------------------------------------------------


def estimate_organic_installs(
    volume_score: float,
    rank: int | None,
    conversion_rate: float = 0.30,
) -> float:
    """Estimate daily organic installs driven by a single keyword.

    Parameters
    ----------
    volume_score:
        0-100 score from :func:`compute_volume_score`.
    rank:
        App's current rank for this keyword (``None`` if unranked).
    conversion_rate:
        Typical App Store page-view-to-install conversion rate.

    Returns
    -------
    Estimated daily installs (rounded to 1 decimal place).
    """

    # Determine click-through rate based on position.
    if rank is None or rank <= 0:
        ctr = 0.0
    elif rank <= 10:
        ctr = _CTR_BY_RANK.get(rank, 0.015)
    elif rank <= 20:
        ctr = 0.005
    elif rank <= 50:
        ctr = 0.001
    else:
        ctr = 0.0

    if ctr == 0.0:
        return 0.0

    # Map volume_score to estimated daily searches (exponential curve).
    # vol 0  -> 10,  vol 50 -> ~148,  vol 80 -> ~708,  vol 100 -> ~2117
    daily_searches = 10.0 * (1.055 ** volume_score)

    installs = daily_searches * ctr * conversion_rate
    return round(installs, 1)


# ---------------------------------------------------------------------------
# 6. Opportunity Score V2
# ---------------------------------------------------------------------------


def compute_opportunity_score_v2(
    volume_score: float,
    difficulty_score: float,
    trend_score: float = 0.0,
    trend_growth: float = 0.0,
) -> float:
    """Improved opportunity score combining volume, difficulty, and trends.

    Parameters
    ----------
    volume_score:
        0-100 from :func:`compute_volume_score`.
    difficulty_score:
        0-100 from :func:`compute_difficulty_score`.
    trend_score:
        Google Trends interest score (0-100).
    trend_growth:
        Percentage change in trend over the observation period.  Positive
        values indicate a growing trend.

    Returns
    -------
    0-100 opportunity score.
    """

    # No real data → low-confidence score (don't reward zero difficulty)
    if volume_score <= 0 and difficulty_score <= 0 and trend_score <= 0:
        return 0.0

    # Volume component (0-35).
    volume_component = volume_score / 100.0 * 35.0

    # Market openness (0-30).
    openness_component = (100.0 - difficulty_score) / 100.0 * 30.0

    # Trend component (0-20).
    trend_base = min(max(trend_score, 0.0), 100.0) / 100.0 * 15.0
    trend_growth_pts = min(max(trend_growth, 0.0) / 100.0 * 5.0, 5.0)
    trend_component = trend_base + trend_growth_pts

    # Growth bonus (0-15).
    if trend_growth > 50:
        growth_bonus = 15.0
    elif trend_growth > 20:
        growth_bonus = 10.0
    else:
        growth_bonus = min(max(trend_growth, 0.0) / 20.0 * 10.0, 10.0)

    total = volume_component + openness_component + trend_component + growth_bonus
    return min(round(total, 2), 100.0)
