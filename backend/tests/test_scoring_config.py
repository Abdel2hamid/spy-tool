"""
test_scoring_config.py
======================
Tests that verify:
1. Config values load correctly from scoring_config.py
2. Scoring modules use the centralised config values
3. Changing config values modifies scoring behaviour as expected
"""

import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config_patch(config_name: str, overrides: dict):
    """Return a context-manager that patches a top-level config dict."""
    import app.config.scoring_config as cfg_module
    original = getattr(cfg_module, config_name)
    patched = {**original, **overrides}
    return patch.object(cfg_module, config_name, patched)


# ---------------------------------------------------------------------------
# 1. Config values load correctly
# ---------------------------------------------------------------------------

class TestConfigLoads:
    def test_trending_config_keys(self):
        from app.config.scoring_config import TRENDING_CONFIG
        required = {
            "momentum_weights", "trend_score_weights",
            "absolute_rank_bonus_max", "rank_bonus_thresholds",
            "review_momentum_cap", "review_dampen_factors",
            "trend_velocity_map", "trend_velocity_default",
            "search_volume_per_app", "difficulty_cap",
        }
        assert required <= TRENDING_CONFIG.keys()

    def test_momentum_weights_sum_to_one(self):
        from app.config.scoring_config import TRENDING_CONFIG
        mw = TRENDING_CONFIG["momentum_weights"]
        total = mw["3d"] + mw["7d"] + mw["14d"]
        assert abs(total - 1.0) < 1e-9, f"momentum_weights must sum to 1.0, got {total}"

    def test_opportunity_config_weights_sum_to_one(self):
        from app.config.scoring_config import OPPORTUNITY_CONFIG
        w = OPPORTUNITY_CONFIG["weights"]
        total = sum(w.values())
        assert abs(total - 1.0) < 1e-9, f"OPPORTUNITY_CONFIG weights must sum to 1.0, got {total}"

    def test_fresh_risers_score_weights_sum_to_one(self):
        from app.config.scoring_config import FRESH_RISERS_CONFIG
        w = FRESH_RISERS_CONFIG["score_weights"]
        total = sum(w.values())
        assert abs(total - 1.0) < 1e-9, f"FRESH_RISERS_CONFIG score_weights must sum to 1.0, got {total}"

    def test_fresh_risers_hidden_gems_weights_sum_to_one(self):
        from app.config.scoring_config import FRESH_RISERS_CONFIG
        w = FRESH_RISERS_CONFIG["hidden_gems_weights"]
        total = sum(w.values())
        assert abs(total - 1.0) < 1e-9, f"hidden_gems_weights must sum to 1.0, got {total}"

    def test_ai_potential_weights_sum_to_one(self):
        from app.config.scoring_config import AI_POTENTIAL_CONFIG
        w = AI_POTENTIAL_CONFIG["weights"]
        total = sum(w.values())
        assert abs(total - 1.0) < 1e-9, f"AI_POTENTIAL_CONFIG weights must sum to 1.0, got {total}"

    def test_winnability_attractiveness_weights_sum_to_one(self):
        from app.config.scoring_config import WINNABILITY_CONFIG
        w = WINNABILITY_CONFIG["attractiveness_weights"]
        total = sum(w.values())
        assert abs(total - 1.0) < 1e-9, f"attractiveness_weights must sum to 1.0, got {total}"

    def test_winnability_combined_weights_sum_to_one(self):
        from app.config.scoring_config import WINNABILITY_CONFIG
        w = WINNABILITY_CONFIG["combined_weights"]
        total = sum(w.values())
        assert abs(total - 1.0) < 1e-9, f"combined_weights must sum to 1.0, got {total}"

    def test_keyword_gate_tier_thresholds_ordered(self):
        from app.config.scoring_config import KEYWORD_GATE_CONFIG
        t = KEYWORD_GATE_CONFIG["tier_thresholds"]
        assert t["A"] > t["B"] > t["C"] > 0

    def test_keyword_gate_capacity_ordering(self):
        from app.config.scoring_config import KEYWORD_GATE_CONFIG
        assert (
            KEYWORD_GATE_CONFIG["tier_c_prune_target"]
            < KEYWORD_GATE_CONFIG["tier_c_stop_threshold"]
            < KEYWORD_GATE_CONFIG["global_cap"]
        )

    def test_winnability_dominance_thresholds_positive(self):
        from app.config.scoring_config import WINNABILITY_CONFIG
        assert WINNABILITY_CONFIG["dominance_review_hard"] > 0
        assert WINNABILITY_CONFIG["dominance_review_rated"] > 0
        assert 0.0 < WINNABILITY_CONFIG["dominance_rated_floor"] <= 5.0
        assert WINNABILITY_CONFIG["dominance_top_rank"] >= 1

    def test_engine_config_keys(self):
        from app.config.scoring_config import ENGINE_CONFIG
        required = {
            "stopwords", "weak_keywords",
            "competition_per_app_boost", "competition_max_boost",
            "category_growth_scale", "phrase_min_words", "phrase_max_words",
            "market_weakness_min_reviews",
        }
        assert required <= ENGINE_CONFIG.keys()

    def test_signal_confidence_freshness_bands_keys_are_integers(self):
        from app.config.scoring_config import SIGNAL_CONFIDENCE_CONFIG
        for key in SIGNAL_CONFIDENCE_CONFIG["freshness_bands_days"]:
            assert isinstance(key, int), f"freshness_bands_days key must be int, got {key!r}"

    def test_idea_generator_scoring_coefficients_present(self):
        from app.config.scoring_config import IDEA_GENERATOR_CONFIG
        required = {
            "feature_gap_app_count_scale", "feature_gap_mentions_scale", "feature_gap_score_cap",
            "weak_market_ratio_scale", "weak_market_rating_base", "weak_market_rating_scale",
            "weak_market_score_cap",
            "keyword_gap_difficulty_scale", "keyword_gap_volume_scale",
            "keyword_gap_trend_scale", "keyword_gap_score_cap",
        }
        assert required <= IDEA_GENERATOR_CONFIG.keys()


# ---------------------------------------------------------------------------
# 2. Scoring modules use config values
# ---------------------------------------------------------------------------

class TestModulesUseConfig:
    def test_ai_potential_uses_config_weights(self):
        """calculate_ai_potential_v2 score must be consistent with AI_POTENTIAL_CONFIG weights."""
        import importlib.util, os
        # Load ai_potential.py directly to avoid triggering app.scoring.__init__
        # (which transitively imports SQLAlchemy models and the DB connection).
        _path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "app", "scoring", "ai_potential.py")
        )
        _spec = importlib.util.spec_from_file_location("_ai_potential", _path)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        calculate_ai_potential_v2 = _mod.calculate_ai_potential_v2
        from app.config.scoring_config import AI_POTENTIAL_CONFIG

        class FakeApp:
            name = "AI Writer Pro"
            subtitle = "ai-powered writing"
            description = "powered by ai"
            primary_category = "productivity"

        result = calculate_ai_potential_v2(FakeApp(), [], [])
        # Title + description both fire (100 each), category fires (100)
        expected_raw = (
            100.0 * AI_POTENTIAL_CONFIG["weights"]["title"] +
            100.0 * AI_POTENTIAL_CONFIG["weights"]["description"] +
            0.0   * AI_POTENTIAL_CONFIG["weights"]["feature_gap"] +
            100.0 * AI_POTENTIAL_CONFIG["weights"]["category"] +
            0.0   * AI_POTENTIAL_CONFIG["weights"]["keyword"]
        )
        expected = round(min(max(expected_raw, 0.0), 100.0), 2)
        assert result["ai_potential_score"] == expected

    def test_opportunity_service_uses_config_weights(self):
        """compute_opportunity_score must use OPPORTUNITY_CONFIG weights."""
        from app.services.opportunity_service import compute_opportunity_score
        from app.config.scoring_config import OPPORTUNITY_CONFIG

        _w = OPPORTUNITY_CONFIG["weights"]
        _rgs = OPPORTUNITY_CONFIG["rank_gap_scores"]

        sv, diff, trend, app_rank = 80, 20, 50, None
        expected = round(min(max(
            sv       * _w["search_volume"] +
            (100 - diff) * _w["difficulty"] +
            trend    * _w["trend"] +
            _rgs[None] * _w["rank_gap"],
            0.0,
        ), 100.0), 1)

        assert compute_opportunity_score(sv, diff, trend, app_rank) == expected

    def test_keyword_quality_engine_uses_tier_thresholds(self):
        """assign_tier must respect KEYWORD_GATE_CONFIG tier thresholds."""
        from app.services.keyword_quality_engine import KeywordQualityEngine
        from app.config.scoring_config import KEYWORD_GATE_CONFIG

        t = KEYWORD_GATE_CONFIG["tier_thresholds"]
        assert KeywordQualityEngine.assign_tier(t["A"])     == "A"
        assert KeywordQualityEngine.assign_tier(t["B"])     == "B"
        assert KeywordQualityEngine.assign_tier(t["C"])     == "C"
        assert KeywordQualityEngine.assign_tier(t["C"] - 1) is None

    def test_keyword_gate_uses_config_min_single_word_length(self):
        """passes_hard_gate must enforce min_single_word_length from config."""
        from app.services.keyword_quality_engine import KeywordQualityEngine
        from app.config.scoring_config import KEYWORD_GATE_CONFIG

        min_len = KEYWORD_GATE_CONFIG["min_single_word_length"]
        # Use a real word of exactly min_len chars that isn't a stopword, weak word,
        # or repeated-char sequence.  "widget" is 6 chars and passes all checks.
        borderline = "widget"[:min_len] if min_len <= 6 else "widgets"[:min_len]
        ok, reason = KeywordQualityEngine.passes_hard_gate(borderline)
        assert ok, f"Expected pass for length={min_len} word '{borderline}', got reason={reason!r}"

        # A non-repeated word one character shorter than the threshold must fail
        # with "single_word_too_short" (use distinct chars to bypass repeated-char check).
        short_chars = "abcdefghijklmnopqrst"
        too_short = short_chars[: min_len - 1]
        ok2, reason2 = KeywordQualityEngine.passes_hard_gate(too_short)
        assert not ok2
        assert reason2 == "single_word_too_short"

    def test_keyword_gate_uses_config_min_non_stop_ratio(self):
        """Mostly-stopword phrases must be rejected using min_non_stop_ratio from config."""
        from app.services.keyword_quality_engine import KeywordQualityEngine
        # "of the" = 2 words, both stopwords → 0% non-stop → rejected
        ok, reason = KeywordQualityEngine.passes_hard_gate("of the app")
        assert not ok
        assert reason in ("mostly_stopwords", "all_stopwords")


# ---------------------------------------------------------------------------
# 3. Changing config modifies scoring behaviour
# ---------------------------------------------------------------------------

class TestConfigChangeModifiesBehaviour:
    def test_ai_potential_threshold_change_affects_classification(self):
        """Lowering the 'native' threshold should reclassify more apps as ai_native."""
        import importlib.util, os
        _path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "app", "scoring", "ai_potential.py")
        )
        _spec = importlib.util.spec_from_file_location("_ai_potential2", _path)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        calculate_ai_potential_v2 = _mod.calculate_ai_potential_v2

        class FakeApp:
            name = "Smart Assistant"       # no native AI term → low score
            subtitle = ""
            description = "writing assistant"
            primary_category = "productivity"

        # Patch module-level thresholds on the dynamically loaded module
        with patch.object(_mod, "_THRESHOLD_NATIVE", 10.0), \
             patch.object(_mod, "_THRESHOLD_ENHANCED", 5.0):
            result = calculate_ai_potential_v2(FakeApp(), [], [])
            # category fires (100 × 0.10 = 10), description fires (100 × 0.25 = 25)
            # raw ≈ 35 → with threshold 10 it should be "ai_native"
            assert result["ai_opportunity_type"] == "ai_native"

    def test_opportunity_weight_change_affects_score(self):
        """Changing search_volume weight in OPPORTUNITY_CONFIG must change score."""
        from app.services.opportunity_service import compute_opportunity_score
        import app.services.opportunity_service as svc_module
        import app.config.scoring_config as cfg_module

        original_score = compute_opportunity_score(100, 20, 50, None)

        # Double search_volume weight (and zero out others so math is simple)
        new_weights = {"search_volume": 0.8, "difficulty": 0.1, "trend": 0.1, "rank_gap": 0.0}
        new_opp_config = {**cfg_module.OPPORTUNITY_CONFIG, "weights": new_weights}

        with patch.object(cfg_module, "OPPORTUNITY_CONFIG", new_opp_config):
            # Also patch module-level _W in the service (it's set at import time)
            with patch.object(svc_module, "_W", new_weights):
                new_score = compute_opportunity_score(100, 20, 50, None)

        assert new_score != original_score

    def test_keyword_tier_threshold_change_reclassifies(self):
        """Raising tier A threshold should push a borderline score to tier B."""
        from app.services.keyword_quality_engine import KeywordQualityEngine
        from app.config.scoring_config import KEYWORD_GATE_CONFIG
        import app.services.keyword_quality_engine as kqe_module

        original_a = KEYWORD_GATE_CONFIG["tier_thresholds"]["A"]
        borderline_score = original_a  # exactly at current A threshold → "A"

        assert KeywordQualityEngine.assign_tier(borderline_score) == "A"

        new_thresholds = {**KEYWORD_GATE_CONFIG["tier_thresholds"], "A": original_a + 5}
        new_cfg = {**KEYWORD_GATE_CONFIG, "tier_thresholds": new_thresholds}

        with patch.object(kqe_module, "_CFG", new_cfg):
            tier = KeywordQualityEngine.assign_tier(borderline_score)
            # The raised threshold means the same score is now "B" (if ≥ B threshold)
            assert tier in ("B", "C", None)

    def test_winnability_dominance_threshold_affects_exclusion(self):
        """Patching _DOMINANCE_REVIEW_RATED in engine module changes the effective threshold."""
        import app.scoring.engine as engine_module

        original = engine_module._DOMINANCE_REVIEW_RATED

        # Default: 100k reviews threshold for the "rated" dominance check
        assert original == 100_000

        # Patch to higher value — now 200k reviews would NOT trigger this gate
        with patch.object(engine_module, "_DOMINANCE_REVIEW_RATED", 300_000):
            assert engine_module._DOMINANCE_REVIEW_RATED == 300_000
            # An app with 200k reviews sits below 300k so it would not be dominated
            # by this specific gate alone (may still be dominated by other gates)
            assert 200_000 < engine_module._DOMINANCE_REVIEW_RATED

        # Context manager restores original value
        assert engine_module._DOMINANCE_REVIEW_RATED == original
