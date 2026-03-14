"""
scoring_config.py — Central Scoring Configuration
===================================================
ALL scoring thresholds, weights, and rule constants live here.
To tune the system, edit this file only — no logic files need to change.

Sections
--------
TRENDING_CONFIG         — Momentum & trend scoring
OPPORTUNITY_CONFIG      — Keyword opportunity score formula
FRESH_RISERS_CONFIG     — Fresh-risers eligibility + sub-score bands
KEYWORD_GATE_CONFIG     — Pre-insertion quality gate + tier thresholds
SIGNAL_CONFIDENCE_CONFIG — Data freshness / reliability decay
AI_POTENTIAL_CONFIG     — AI potential signal weights + classification thresholds
IDEA_GENERATOR_CONFIG   — Thresholds for the idea-generation queries
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# TRENDING_CONFIG
# ─────────────────────────────────────────────────────────────────────────────
TRENDING_CONFIG: dict = {
    # ── Multi-window momentum weights ────────────────────────────────────────
    # Shorter windows are discounted — recent consistency matters most.
    # Tuning: must sum to 1.0. Increase "14d" to reward sustained trends.
    "momentum_weights": {"3d": 0.20, "7d": 0.35, "14d": 0.45},

    # ── Final score assembly (contributes to the 0-100 trend_score) ──────────
    # momentum_normalized_scale: raw positions/day is multiplied by this so the
    # 0-60 pt momentum contribution is proportionate to realistic rank movement.
    # Tuning: increase to reward faster movers; decrease to dampen outliers.
    "trend_score_weights": {
        "momentum_normalized_scale": 3.0,
        "consistency_weight": 0.15,   # max 15 pts — rewards consistent direction
        "rank_bonus_weight": 1.0,     # absolute rank bonus applied 1:1
        "review_momentum_weight": 0.5,  # review spike contribution factor
    },

    # ── Absolute rank bonus (0-20 pts) ───────────────────────────────────────
    # Apps already near the top get a bonus because achieving/keeping a top rank
    # is itself a signal of quality. Max 20 pts.
    # Tuning: raise threshold values to be more generous; lower to be stricter.
    "absolute_rank_bonus_max": 20.0,
    "rank_bonus_thresholds": {
        5: 20.0,   # top-5 → +20 pts
        10: 15.0,  # top-10 → +15 pts
        25: 10.0,  # top-25 → +10 pts
        50: 5.0,   # top-50 → +5 pts
    },

    # ── Review momentum cap ──────────────────────────────────────────────────
    # Review spikes contribute up to this many points to the trend score.
    # Tuning: raise if reviews are a stronger signal in your market.
    "review_momentum_cap": 20.0,

    # ── Review dampening factors ─────────────────────────────────────────────
    # High-review apps need fewer incremental reviews to be meaningful, so raw
    # velocity is dampened for apps with large existing review bases.
    # key = current_reviews threshold; value = dampening multiplier (< 1.0).
    # Tuning: lower values are more aggressive dampening.
    "review_dampen_factors": {100: 0.3, 1_000: 0.6, 10_000: 0.85},

    # ── Trend velocity seed map ───────────────────────────────────────────────
    # Category-derived trend estimate used when real trend data is unavailable.
    # Scale: 0-10 (will be stored directly as kw.trend).
    # Tuning: adjust per market conditions; "default" used for unrecognised terms.
    "trend_velocity_map": {
        "ai": 8.5, "gpt": 8.0, "chat": 7.5, "game": 6.5, "gaming": 6.5,
        "fitness": 5.5, "health": 5.5, "productivity": 5.0, "social": 5.0,
        "finance": 4.5, "education": 4.5, "music": 4.0, "travel": 3.5,
    },
    "trend_velocity_default": 3.0,

    # ── search_volume / difficulty estimation heuristics ─────────────────────
    # search_volume ≈ app_count × search_volume_per_app
    # Tuning: raise if Apple's ecosystem tends to have higher search volume.
    "search_volume_per_app": 850,
    # difficulty caps at this value so keywords remain visible in the default
    # max_difficulty=60 view on the dashboard.
    # Tuning: raise to 100 for unfiltered difficulty; lower for stricter gate.
    "difficulty_cap": 60.0,
}


# ─────────────────────────────────────────────────────────────────────────────
# OPPORTUNITY_CONFIG
# ─────────────────────────────────────────────────────────────────────────────
OPPORTUNITY_CONFIG: dict = {
    # ── Canonical opportunity formula weights ─────────────────────────────────
    # opportunity_score = search_volume×W + (100-difficulty)×W + trend×W + rank_gap×W
    # Tuning: weights must sum to 1.0. Increase "search_volume" to reward volume
    # more; increase "difficulty" to reward low-competition niches more.
    "weights": {
        "search_volume": 0.4,
        "difficulty":    0.3,
        "trend":         0.2,
        "rank_gap":      0.1,
    },

    # ── Rank-gap component lookup ─────────────────────────────────────────────
    # Mapping: app_rank threshold → rank_gap_score (0-100).
    # None key = app has no ranking at all (biggest gap).
    # Tuning: increase the "not ranking" bonus to reward entering an unranked niche.
    "rank_gap_scores": {
        None: 100.0,   # not ranking at all — maximum opportunity
        30:    80.0,   # outside top-30
        10:    50.0,   # top 11-30
        0:     10.0,   # already in top-10 — low incremental opportunity
    },

    # ── Legacy inline formula weights (engine.py get_keyword_opportunities) ──
    # A separate, older formula still used inside engine.py.
    # Tuning: keep consistent with the canonical weights above if possible.
    "legacy_weights": {
        "difficulty":        0.3,
        "trend":             0.4,
        "search_volume_scale": 0.2,   # (search_volume / 1000) × this
        "competition_factor": 10.0,   # 1/(app_count+1) × this
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# FRESH_RISERS_CONFIG
# ─────────────────────────────────────────────────────────────────────────────
FRESH_RISERS_CONFIG: dict = {
    # ── Sub-score weights (must sum to 1.0) ───────────────────────────────────
    # Default "fresh_risers" mode weights.
    # Tuning: increase "review_traction" if early user response is most predictive.
    "score_weights": {
        "freshness":        0.25,
        "review_traction":  0.25,
        "rank_quality":     0.20,
        "momentum":         0.20,
        "niche_viability":  0.10,
    },

    # ── "hidden_gems" mode weights ────────────────────────────────────────────
    # Emphasises momentum and niche viability over freshness.
    # Tuning: adjust to surface different kinds of under-the-radar apps.
    "hidden_gems_weights": {
        "momentum":         0.40,
        "niche_viability":  0.30,
        "rank_quality":     0.20,
        "review_traction":  0.10,
    },

    # ── Eligibility rules ─────────────────────────────────────────────────────
    # max_age_days: primary cutoff — app release_date must be within this window.
    # fallback_age_days: accepted when release_date is null but created_at exists.
    # min_reviews / min_ranking_snapshots: noise filters.
    # max_rank: apps ranked worse than this are excluded (too obscure).
    # Tuning: increase max_age_days to include older apps; lower min_reviews for
    #         smaller niches where even 2 reviews are meaningful.
    "eligibility": {
        "max_age_days":             7,
        "fallback_age_days":       14,
        "min_reviews":              5,
        "min_ranking_snapshots":    3,
        "max_rank":               500,
    },

    # ── Freshness score bands (age_days → score) ──────────────────────────────
    # key = max age (inclusive); score = pts at that band; fallback = 0.
    # Tuning: add a band at 5 days → 70 if you want smoother decay.
    "freshness_bands": {2: 100.0, 4: 80.0, 7: 60.0},

    # ── Review velocity bands (reviews/day → score) ───────────────────────────
    # Tuning: lower the 5.0 threshold if you're in a niche with slower take-up.
    "review_velocity_bands": {5: 100.0, 2: 70.0, 1: 40.0},
    "review_velocity_floor": 10.0,   # score for velocity < 1

    # ── Rank quality bands (current_rank → score) ─────────────────────────────
    # Tuning: lower the "300" threshold to be stricter; add an intermediate band
    #         at 200 → 20 if you want more granularity.
    "rank_quality_bands": {10: 100.0, 50: 80.0, 100: 60.0, 300: 30.0},
    "rank_quality_floor": 10.0,   # score for rank > 300 or no rank
    "rank_quality_no_rank": 10.0,

    # ── Momentum bands (rank_improvement → score) ─────────────────────────────
    # rank_improvement = rank_7_days_ago - current_rank (positive = moving up).
    # Tuning: lower "100" to reward smaller improvements in crowded categories.
    "momentum_bands": {100: 100.0, 50: 70.0, 20: 40.0},
    "momentum_floor": 10.0,
    "momentum_no_history": 10.0,

    # ── Niche viability bands (avg_reviews_in_category → score) ──────────────
    # Low avg reviews ⇒ early stage niche ⇒ higher opportunity.
    # Tuning: raise thresholds in mature categories where 20k avg is normal.
    "niche_avg_reviews_bands": {1_000: 90.0, 5_000: 70.0, 20_000: 50.0},
    "niche_floor": 30.0,
    "niche_default": 50.0,   # used when category has no review data
    "niche_no_category": 50.0,
}


# ─────────────────────────────────────────────────────────────────────────────
# KEYWORD_GATE_CONFIG
# ─────────────────────────────────────────────────────────────────────────────
KEYWORD_GATE_CONFIG: dict = {
    # ── Hard-gate length constraints ──────────────────────────────────────────
    # Single-word keywords must be at least this long to be valuable.
    # Tuning: raise to 7 for stricter single-word gates; never go below 4.
    "min_single_word_length":      6,
    "max_word_length":            45,   # apply to both single and multi
    "max_multi_word_count":        4,   # 5+ word phrases are rejected
    "min_multi_word_char_length":  5,

    # ── Stop-word ratio gate ──────────────────────────────────────────────────
    # Minimum fraction of non-stop-words in a multi-word phrase.
    # E.g. 0.4 = at least 40% of tokens must have semantic value.
    # Tuning: raise to 0.5 to be stricter about keyword quality.
    "min_non_stop_ratio": 0.4,

    # ── Single-word score penalty ─────────────────────────────────────────────
    # Single-word keywords always receive this quality_score multiplier because
    # they have lower inherent specificity than phrases.
    # Tuning: lower (e.g. 0.75) to penalise more; raise to 0.95 to penalise less.
    "single_word_penalty": 0.85,

    # ── Tier thresholds ───────────────────────────────────────────────────────
    # A ≥ 75: always kept; B ≥ 60: accepted; C ≥ 45: cautious; < 45: rejected.
    # Tuning: lower "B" to widen acceptance; raise "A" to keep only the best.
    "tier_thresholds": {"A": 75.0, "B": 60.0, "C": 45.0},

    # ── Global DB capacity controls ───────────────────────────────────────────
    # global_cap: hard ceiling on total keyword rows.
    # tier_c_stop_threshold: stop inserting new Tier-C rows at this count.
    # tier_c_prune_target: prune Tier-C until count drops below this.
    # Tuning: raise global_cap if your DB can handle more; raise stop_threshold
    #         to delay pruning; lower prune_target to prune more aggressively.
    "global_cap":               1_000_000,
    "tier_c_stop_threshold":      900_000,
    "tier_c_prune_target":        850_000,

    # ── Per-app source quotas ─────────────────────────────────────────────────
    # Maximum keywords per app per source group AND total across all sources.
    # Tuning: raise individual quotas to allow richer keyword sets per app.
    "source_quotas": {
        "extracted":    25,
        "autocomplete": 25,
        "competitor":   20,
        "category":     15,
        "alphabet":     15,
    },
    "total_app_quota": 100,

    # ── Source-score weights (0-15 pts) ───────────────────────────────────────
    # Higher-quality sources (title, subtitle) receive more points.
    # "default" is used for unknown source strings.
    # Tuning: raise "competitor" to reward competitive research more.
    "source_weights": {
        "title":              15,
        "subtitle":           14,
        "autocomplete":       12,
        "seed":               12,
        "competitor":         11,
        "description":        10,
        "category":            9,
        "discovery_engine":    8,
        "reviews":             8,
        "alphabet":            6,
    },
    "source_weight_default": 7,

    # ── Phrase score sub-components ───────────────────────────────────────────
    # phrase_score is the sum of word-count, char-length, and punctuation pts.
    # Tuning: raise multi_word_pts to further incentivise multi-word keywords.
    "phrase_score": {
        "multi_word_pts":         10.0,   # 2-4 word phrases
        "single_word_pts":         5.0,
        "char_len_optimal_range": (8, 25),   # ideal keyword length range
        "char_len_optimal_pts":    5.0,
        "char_len_mid_pts":        3.0,   # (5-7) or (26-35) chars
        "char_len_other_pts":      1.0,   # outside both ranges
        "no_punct_pts":            5.0,
        "punct_pts":               2.0,
    },

    # ── Validation-score bands (Apple app result count → pts) ─────────────────
    # More apps ranking for a keyword = more search demand = higher validation.
    # key = max result count (inclusive); value = base pts.
    # Tuning: lower the "100" threshold if most niches have < 50 apps.
    "validation_bands": {0: 0.0, 5: 5.0, 20: 10.0, 100: 15.0},
    "validation_above_100_pts": 20.0,
    "validation_max": 25.0,          # absolute cap including token-match bonus
    "validation_token_match_bonus":  1.0,  # per matching token in top-5 Apple results
    "validation_token_min_length":   3,    # tokens shorter than this are not checked

    # ── Volume-score bands (search_volume → pts) ──────────────────────────────
    # Tuning: raise the "100" threshold if your market has very high search volumes.
    "volume_bands": {0: 0.0, 10: 5.0, 50: 8.0, 100: 12.0},
    "volume_max_pts": 15.0,

    # ── Competitor score sweet-spot ───────────────────────────────────────────
    # 5-50 apps = niche opportunity. < 5 = possibly too new. > 200 = saturated.
    # Tuning: widen to (3, 80) for broader niches.
    "competitor_sweet_spot":        (5, 50),
    "competitor_niche_pts":          5.0,
    "competitor_very_niche_range":   (1, 4),
    "competitor_very_niche_pts":     3.0,
    "competitor_crowded_range":     (51, 200),
    "competitor_crowded_pts":        2.0,
    "competitor_saturated_pts":      0.0,

    # ── Trend component cap ───────────────────────────────────────────────────
    "trend_max_pts": 5.0,

    # ── Relevance score ───────────────────────────────────────────────────────
    "relevance_per_token":    2.5,   # pts per token found in app title/subtitle
    "relevance_min_token_len": 3,
    "relevance_max":          5.0,

    # ── Weak single-word gate list ────────────────────────────────────────────
    # These words are rejected as standalone keywords because they are too
    # generic to drive meaningful organic traffic.
    # Tuning: add domain-specific noise words (e.g. "timer" if irrelevant).
    "weak_single_words": frozenset({
        "best", "easy", "free", "smart", "simple", "new", "cool", "top",
        "pro", "lite", "hd", "app", "apps", "game", "run", "get", "use",
    }),

    # ── Junk phrase exact-match reject list ───────────────────────────────────
    # Exact multi-word phrases that are pure advertising noise.
    "junk_phrases": frozenset({
        "click here", "download now", "install now", "best app", "top app",
        "number one", "#1 app", "great app", "awesome app", "amazing app",
    }),
}


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL_CONFIDENCE_CONFIG
# ─────────────────────────────────────────────────────────────────────────────
SIGNAL_CONFIDENCE_CONFIG: dict = {
    # ── Freshness decay (days since last_enriched → factor 0-1) ──────────────
    # Data quality degrades over time. Factor is used as a multiplier.
    # key = max age in days (exclusive upper bound); value = factor.
    # Tuning: lower factors to discount old data more aggressively.
    "freshness_bands_days": {7: 1.0, 30: 0.85, 90: 0.65},
    "freshness_stale": 0.4,   # factor when data is > 90 days old or missing

    # ── Reliability by keyword status ────────────────────────────────────────
    # ENRICHED keywords have observed data; RAW keywords have only estimates.
    # Tuning: lower "raw" to 0.3 if estimated data is unreliable in your market.
    "reliability_by_status": {"enriched": 1.0, "raw": 0.5},

    # ── Reliability by quality tier ───────────────────────────────────────────
    # Complements status — Tier A has the most reliable data.
    # Tuning: raise/lower individual tiers to match observed data quality.
    "reliability_by_tier": {"A": 1.0, "B": 0.8, "C": 0.6},
    "reliability_default": 0.5,

    # ── Completeness scoring ──────────────────────────────────────────────────
    # Number of distinct metric fields that contribute to the completeness factor.
    # Tuning: add fields if more metrics are tracked in the Keyword model.
    "total_metrics": 5,
}


# ─────────────────────────────────────────────────────────────────────────────
# AI_POTENTIAL_CONFIG
# ─────────────────────────────────────────────────────────────────────────────
AI_POTENTIAL_CONFIG: dict = {
    # ── Signal weights (must sum to 1.0) ──────────────────────────────────────
    # Title carries the most weight because explicit AI terms in a product name
    # are the strongest signal of an AI-native product.
    # Feature gaps carry high weight because user-expressed demand for AI
    # features is a strong market opportunity signal.
    # Tuning: raise "feature_gap" to 0.25 and lower "description" if you trust
    #         review data more than marketing copy.
    "weights": {
        "title":        0.35,
        "description":  0.25,
        "feature_gap":  0.20,
        "category":     0.10,
        "keyword":      0.10,
    },

    # ── Classification thresholds ─────────────────────────────────────────────
    # native:   score ≥ this → "ai_native"   (AI is the core product)
    # enhanced: score ≥ this → "ai_enhanced" (AI can meaningfully improve it)
    # below enhanced → "weak"
    # Tuning: lower "native" to 50 to be more inclusive; raise to 70 to be strict.
    #         Lower "enhanced" to 15 to catch more opportunity cases.
    "thresholds": {
        "native":   60.0,
        "enhanced": 25.0,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# IDEA_GENERATOR_CONFIG
# ─────────────────────────────────────────────────────────────────────────────
IDEA_GENERATOR_CONFIG: dict = {
    # ── Pattern A — Feature Gap Demand ───────────────────────────────────────
    # A feature gap must be reported across at least this many distinct apps
    # AND have at least this many total user mentions to qualify.
    # Tuning: lower to 1 and 1 in early-data scenarios; raise for mature datasets.
    "feature_gap_min_apps":     2,
    "feature_gap_min_mentions": 2,
    "feature_gap_limit":       20,   # max ideas generated from this pattern

    # ── Pattern B — Weak Market ───────────────────────────────────────────────
    # Thresholds that identify a "broken" market in a given country.
    # negative_ratio ≥ 0.30 = 30% of reviews are negative (rating ≤ 2).
    # average_rating ≤ 3.5  = below-average satisfaction.
    # total_reviews ≥ 20    = enough data to trust the signal.
    # Tuning: lower negative_ratio to 0.20 for earlier detection; raise
    #         min_reviews to 50 in markets with more review volume.
    "weak_market_min_negative_ratio": 0.30,
    "weak_market_max_avg_rating":     3.5,
    "weak_market_min_reviews":       20,
    "weak_market_limit":             30,

    # ── Pattern C — Keyword Gap Opportunity ───────────────────────────────────
    # Only keywords with difficulty < this and search_volume ≥ this qualify.
    # Tuning: raise max_difficulty to 70 to include more competitive niches;
    #         lower min_volume to 500 in smaller markets.
    "keyword_gap_max_difficulty": 60,
    "keyword_gap_min_volume":    800,
    "keyword_gap_limit":          20,

    # ── Low-competition keyword lookup (used inside Pattern B) ────────────────
    "keyword_difficulty_low": 50,

    # ── Pattern A — Feature Gap scoring formula ───────────────────────────────
    # score = min(app_count × app_count_scale + total_mentions × mentions_scale, score_cap)
    # Tuning: raise app_count_scale to weight breadth of demand more heavily;
    #         raise mentions_scale to weight depth of demand more heavily.
    "feature_gap_app_count_scale":  10,
    "feature_gap_mentions_scale":    2,
    "feature_gap_score_cap":        95,

    # ── Pattern B — Weak Market scoring formula ───────────────────────────────
    # score = min(negative_ratio × ratio_scale + (rating_base - avg_rating) × rating_scale, cap)
    # Tuning: raise ratio_scale to penalise high-negativity markets more;
    #         raise rating_scale to reward very-low-rated markets more.
    "weak_market_ratio_scale":      60,
    "weak_market_rating_base":       5.0,
    "weak_market_rating_scale":     10,
    "weak_market_score_cap":        95,

    # ── Pattern C — Keyword Gap scoring formula ───────────────────────────────
    # score = min((100-difficulty) × diff_scale + (volume/1000) × volume_scale
    #             + trend × trend_scale, cap)
    # Tuning: raise diff_scale to favour easy niches more; raise volume_scale
    #         to favour high-search-volume keywords more.
    "keyword_gap_difficulty_scale":  0.45,
    "keyword_gap_volume_scale":     15,      # applied per 1 000 search volume
    "keyword_gap_trend_scale":       0.4,
    "keyword_gap_score_cap":        95,
}

# ─────────────────────────────────────────────────────────────────────────────
# WINNABILITY_CONFIG
# ─────────────────────────────────────────────────────────────────────────────
WINNABILITY_CONFIG: dict = {
    # ── Big-brand developer exclusion list (normalised lowercase) ─────────────
    # Any app whose developer field matches an entry (exact or as a substring for
    # entries > brand_substring_min_length chars) is excluded from Opportunity
    # of the Day.
    # Tuning: add new major companies as they enter the App Store.
    "big_brand_developers": frozenset({
        "openai", "openai llc", "openai lc",
        "google llc", "google inc", "google",
        "meta platforms", "meta platforms inc", "meta",
        "microsoft corporation", "microsoft",
        "xai", "x.ai",
        "anthropic", "anthropic plc", "anthropic llc",
        "amazon.com services llc", "amazon", "amazon.com",
        "apple", "apple inc", "apple distribution international",
        "adobe", "adobe inc", "adobe systems",
        "netflix", "netflix inc",
        "spotify ab", "spotify",
        "notion labs", "notion labs inc", "notion",
        "canva pty ltd", "canva",
        "bytedance", "tiktok ltd", "tiktok pte",
        "x corp", "twitter", "twitter inc",
        "snap inc", "snap",
        "linkedin corporation", "linkedin",
        "pinterest",
        "samsung electronics",
        "huawei device",
        "shopify inc",
        "salesforce inc", "salesforce.com",
        "zoom video communications",
        "slack technologies",
        "dropbox inc",
        "box inc",
        "airbnb inc",
        "uber technologies",
        "lyft inc",
        "doordash inc",
        "instacart",
        "duolingo",
        "bumble inc",
        "match group",
        "unity technologies",
        "epic games",
        "activision publishing",
        "electronic arts",
        "zynga",
        "king",
        "niantic",
        "riot games",
        "supercell",
        "verizon media",
        "yahoo",
        "baidu",
        "alibaba",
        "tencent",
        "naver corporation",
        "kakao corporation",
        "line corporation",
        "rakuten",
        "sony interactive entertainment",
        "warner bros",
        "disney",
        "paramount",
        "hbo",
        "hulu",
        "peacock",
        "amazon prime video",
        "twitch interactive",
        "reddit inc",
    }),

    # Minimum character length for a developer token to trigger substring match.
    # Tokens <= this length are only matched exactly (avoids false positives like "meta").
    # Tuning: lower to 4 to catch shorter brand tokens; raise to 7 for stricter matching.
    "brand_substring_min_length": 5,

    # ── App-name substrings that flag a big-brand product ─────────────────────
    # Checked case-insensitively against the app's name field.
    # Tuning: add/remove entries to keep pace with brand portfolio changes.
    "big_brand_app_keywords": (
        "chatgpt", "dall-e", "dall·e", "openai",
        "gemini", "google one", "google docs", "google sheets", "google drive",
        "youtube", "gmail", "chrome", "google maps", "google photos",
        "instagram", "facebook", "whatsapp", "messenger", "threads",
        "grok",
        "microsoft copilot", "bing ", "bing chat", "microsoft 365",
        "microsoft teams", "outlook", "onedrive", "xbox",
        "claude ",
        "alexa ", "amazon prime", "amazon music", "amazon photos",
        "adobe photoshop", "adobe acrobat", "adobe illustrator",
        "adobe lightroom", "adobe premiere",
        "netflix",
        "notion ",
        "canva ",
        "tiktok",
        "snapchat",
        " twitter", "twitter for", "x for iphone",
        "linkedin",
        "pinterest",
        "spotify",
        "slack ",
        "zoom ",
        "dropbox",
        "duolingo",
        "shazam",
        "garageband",
        "iwork", "pages for", "numbers for", "keynote for",
    ),

    # ── Market dominance thresholds ───────────────────────────────────────────
    # An app meeting any condition is considered an unbeatable incumbent.
    # Tuning: raise review_hard to 750k to widen the opportunity pool;
    #         lower to 300k to be more conservative.
    "dominance_review_hard":   500_000,   # absolute behemoth — never winnable
    "dominance_review_rated":  100_000,   # entrenched + high rating
    "dominance_rated_floor":       4.5,   # minimum rating for "entrenched + beloved"
    "dominance_top_rank":            3,   # chart dominator rank threshold
    "dominance_top_reviews":   50_000,   # chart dominator review count threshold

    # ── Feasibility score — Review scarcity component (max 25 pts) ───────────
    # key = max reviews (exclusive upper bound); value = pts awarded.
    # Fewer reviews = easier to enter market = higher feasibility.
    # Tuning: adjust break-points to match typical app review counts in your niche.
    "feasibility_review_bands": {
        500:     25.0,   # < 500 reviews — wide open market
        5_000:   20.0,   # < 5 k  reviews — accessible
        20_000:  12.0,   # < 20k  reviews — competitive
        50_000:   6.0,   # < 50k  reviews — very competitive
        100_000:  2.0,   # < 100k reviews — tough
    },
    "feasibility_review_floor": 0.0,     # ≥ 100k reviews — effectively unenterable

    # ── Feasibility score — Keyword competition component (max 25 pts) ────────
    # pts = max(0, (100 − competition_score) / divisor)
    # Tuning: lower divisor to award more points for low competition.
    "feasibility_competition_divisor": 4.0,

    # ── Feasibility score — Feature gap component (max 20 pts) ───────────────
    # pts = min(gap_count × gap_scale, gap_max)
    # Tuning: raise gap_scale to reward each gap request more heavily.
    "feasibility_gap_scale": 4.0,
    "feasibility_gap_max":  20.0,

    # ── Feasibility score — Rating weakness component (max 15 pts) ───────────
    # Lower avg rating = more unhappy users to win over = higher pts.
    # Tuning: raise threshold values to award points in higher-rated markets.
    "feasibility_rating_bands": {
        2.0: 15.0,   # < 2.0 ★ — very unhappy users
        3.0: 12.0,   # < 3.0 ★ — unhappy
        3.5:  8.0,   # < 3.5 ★ — slightly below average
        4.0:  4.0,   # < 4.0 ★ — room for improvement
    },
    "feasibility_rating_floor": 0.0,     # ≥ 4.0 ★ — users already happy

    # ── Feasibility score — Rank accessibility component (max 15 pts) ────────
    # Apps outside the top ranks are easier to displace.
    # Tuning: raise rank_accessible_threshold to widen "open chart" definition.
    "feasibility_rank_bands": {
        20:  5.0,    # rank 21-50
        50: 10.0,    # rank 51-100
    },
    "feasibility_rank_accessible": 15.0,   # rank > 100 — chart is open
    "feasibility_rank_floor":       0.0,   # rank ≤ 20 — chart is locked

    # ── Attractiveness formula weights (must sum to 1.0) ─────────────────────
    # Attractiveness = rank_score×W + rating_score×W + competition×W + ai×W
    # Tuning: increase "rank_score" to weight market size more; increase "ai"
    #         to surface more AI-opportunity apps.
    "attractiveness_weights": {
        "rank_score":        0.45,
        "rating_score":      0.30,
        "competition_score": 0.15,
        "ai_potential":      0.10,
    },

    # ── Combined opportunity score weights (attractiveness + feasibility) ─────
    # final = attractiveness × W + feasibility × W
    # Tuning: raise "feasibility" to favour winnable niches; raise "attractiveness"
    #         to favour high-demand markets regardless of difficulty.
    "combined_weights": {
        "attractiveness": 0.45,
        "feasibility":    0.55,
    },

    # ── Winnability recommendation thresholds ─────────────────────────────────
    # Tuning: lower high_threshold to label more opportunities as "High winnability".
    "winnability_high_threshold":     65,
    "winnability_moderate_threshold": 45,

    # Minimum values that trigger specific recommendation signals.
    "recommendation_gap_min_count":   3,    # feature gaps to flag differentiation path
    "recommendation_rating_pts_min":  8,    # rating_pts for "users unhappy" signal
    "recommendation_review_pts_min":  20,   # review_pts for "early mover" signal
    "recommendation_competition_pts_min": 18,   # competition_pts for "ASO opportunity"
}


# ─────────────────────────────────────────────────────────────────────────────
# SUCCESS_PROBABILITY_CONFIG
# ─────────────────────────────────────────────────────────────────────────────
SUCCESS_PROBABILITY_CONFIG: dict = {
    # ── Success probability formula weights ──────────────────────────────────
    # probability = rank_factor + review_factor + competition_factor + ai_factor + category_factor
    # where:
    #   rank_factor       = min(rank_velocity × rank_velocity_scale, rank_velocity_max)
    #   review_factor     = min(review_growth × review_growth_scale, review_growth_max)
    #   competition_factor = (100 − competition_score) × competition_scale
    #   ai_factor         = ai_potential × ai_potential_scale
    #   category_factor   = category_growth × category_growth_scale
    # Tuning: raise rank_velocity_max to reward fast movers more.
    "rank_velocity_scale":   10.0,
    "rank_velocity_max":     30.0,
    "rank_velocity_default": 10.0,   # used when velocity ≤ 0 (no negative reward)
    "review_growth_scale":    0.5,
    "review_growth_max":     25.0,
    "competition_scale":      0.2,
    "ai_potential_scale":     0.15,
    "category_growth_scale":  0.1,

    # ── Legacy trend_score formula (score_opportunity method) ─────────────────
    # trend_score = min(rank_velocity × trend_rank_scale + review_growth × trend_review_scale
    #                   + category_growth × trend_category_scale, 100)
    "trend_rank_scale":      20.0,
    "trend_review_scale":     0.3,
    "trend_category_scale":   0.4,

    # ── Recommendation thresholds (score_opportunity / _generate_recommendation) ─
    # Tuning: lower high_potential_threshold to surface more "High-potential" labels.
    "high_potential_threshold":   70,
    "moderate_potential_threshold": 50,
    "trend_alert_threshold":      60,
    "competition_low_threshold":  40,
    "competition_high_threshold": 70,
    "ai_opportunity_threshold":   60,
}


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE_CONFIG
# ─────────────────────────────────────────────────────────────────────────────
ENGINE_CONFIG: dict = {
    # ── Keyword competition boost ─────────────────────────────────────────────
    # competition_boost = min(app_count × per_app_boost, max_boost)
    # Added to the base difficulty score to reflect ranking pressure from more apps.
    # Tuning: raise per_app_boost to penalise crowded keywords more.
    "competition_per_app_boost": 2,
    "competition_max_boost":    30,

    # ── Category growth scaling ───────────────────────────────────────────────
    # category_growth = min(recent_app_count × growth_scale, 100)
    # Tuning: lower growth_scale if large categories score too high.
    "category_growth_scale": 5,

    # ── Phrase extraction (select_primary_keyword / _extract_phrases) ─────────
    # Tuning: raise min_phrase_words to require longer phrases.
    "phrase_min_words": 2,
    "phrase_max_words": 3,

    # ── Stopwords for phrase extraction and keyword filtering ─────────────────
    # Words that carry no semantic value for ASO purposes.
    # Tuning: add domain-specific noise words; do NOT remove very common words.
    "stopwords": frozenset({
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "up", "about", "into", "through", "during",
        "before", "after", "above", "below", "between", "under", "again", "further",
        "then", "once", "here", "there", "when", "where", "why", "how", "all", "each",
        "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
        "own", "same", "so", "than", "too", "very", "can", "will", "just", "should",
        "now", "your", "you", "its", "this", "that", "these", "those", "i", "we",
        "they", "he", "she", "it", "my", "our", "their", "his", "her", "what", "which",
        "who", "whom", "is", "are", "was", "were", "be", "been", "being", "have", "has",
        "had", "doing", "game", "app", "free", "pro", "lite", "hd", "ios",
    }),

    # ── Weak keywords for phrase filtering ───────────────────────────────────
    # Generic descriptors that provide no ASO targeting value on their own.
    # Tuning: add category-specific generic words; be conservative — a word
    #         like "fitness" is NOT weak even though it's broad.
    "weak_keywords": frozenset({
        "best", "top", "new", "latest", "easy", "simple", "fast", "quick", "smart",
        "awesome", "cool", "amazing", "great", "perfect", "fun", "good", "nice",
        "beautiful", "lovely", "fantastic", "wonderful", "excellent",
        "premium", "ultimate", "super", "mega", "power", "world", "day", "today",
    }),

    # ── Market weakness minimum review count (noise gate) ─────────────────────
    # Countries with fewer reviews than this are excluded from weak-market analysis.
    # Tuning: raise to 50 in markets with higher review volume for better signal.
    "market_weakness_min_reviews": 20,
}
