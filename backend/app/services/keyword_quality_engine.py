"""
Keyword Quality Engine
======================
Pre-insertion quality gate and composite scoring system for the global
keywords table.

Prevents low-value noise from entering the DB and maintains a hard global
ceiling of ~1M keywords, auto-pruning the weakest Tier-C entries daily.

Tier definitions
----------------
  A  quality_score >= 75  — high-priority, always kept
  B  quality_score >= 60  — accepted
  C  quality_score >= 45  — accepted cautiously; first to be pruned
  -  quality_score <  45  — rejected / pruned on next pass
"""

from __future__ import annotations

import re
import logging
from typing import List, Optional, Tuple

from app.config.scoring_config import KEYWORD_GATE_CONFIG as _CFG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants pulled from central config
# ---------------------------------------------------------------------------
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "for", "to", "of", "in", "on",
    "at", "by", "as", "is", "it", "be", "go", "he", "me", "my", "no",
    "us", "we", "do", "app", "apps", "free", "ios", "iphone", "ipad",
    "apple", "download", "get", "new", "all", "use", "you", "your",
})

_JUNK_PHRASES        = _CFG["junk_phrases"]
_WEAK_SINGLE_WORDS   = _CFG["weak_single_words"]
_SOURCE_WEIGHTS: dict = _CFG["source_weights"]
_SOURCE_WEIGHT_DEFAULT = _CFG["source_weight_default"]

GLOBAL_CAP            = _CFG["global_cap"]
TIER_C_STOP_THRESHOLD = _CFG["tier_c_stop_threshold"]
TIER_C_PRUNE_TARGET   = _CFG["tier_c_prune_target"]

SOURCE_QUOTAS  = _CFG["source_quotas"]
TOTAL_APP_QUOTA = _CFG["total_app_quota"]


# Source group mapping: raw source string → group name
_SOURCE_GROUP: dict = {
    "title":        "extracted",
    "subtitle":     "extracted",
    "description":  "extracted",
    "autocomplete": "autocomplete",
    "prefix":       "autocomplete",
    "suffix":       "autocomplete",
    "competitor":   "competitor",
    "category":     "category",
    "alphabet":     "alphabet",
}


def _get_source_group_values(group: str) -> List[str]:
    """Return all raw source strings that belong to a given source group."""
    values = [k for k, v in _SOURCE_GROUP.items() if v == group]
    return values if values else [group]


class KeywordQualityEngine:
    """
    Stateless quality gate and scoring engine for keywords.

    Usage::
        # Pre-insertion gate (no DB needed)
        passed, reason = KeywordQualityEngine.passes_hard_gate(term)

        # Full quality score (after enrichment data is available)
        score, val_score, rel_score = KeywordQualityEngine.compute_quality_score(...)
        tier = KeywordQualityEngine.assign_tier(score)

        # DB-level checks
        KeywordQualityEngine.check_app_quota(db, app_id, source)
        KeywordQualityEngine.should_reject_tier_c(db)
    """

    # -----------------------------------------------------------------------
    # Normalization
    # -----------------------------------------------------------------------

    @staticmethod
    def normalize(term: str) -> str:
        """Lowercase, remove punctuation, collapse whitespace."""
        term = term.lower().strip()
        term = re.sub(r"[^\w\s]", " ", term)
        term = re.sub(r"\s+", " ", term).strip()
        return term

    @staticmethod
    def canonicalize(term: str) -> str:
        """
        Simple plural dedup: strip trailing 's' when resulting word is ≥ 3 chars.
        "trackers" → "tracker", "tasks" → "task", "as" stays "as".
        """
        norm = KeywordQualityEngine.normalize(term)
        words = [w[:-1] if w.endswith("s") and len(w) > 3 else w for w in norm.split()]
        return " ".join(words)

    # -----------------------------------------------------------------------
    # Hard gate — no network, no DB
    # -----------------------------------------------------------------------

    @staticmethod
    def passes_hard_gate(term: str) -> Tuple[bool, str]:
        """
        Fast pre-insertion quality gate.

        Returns (True, "") on pass, or (False, reason_code) on reject.
        
        Single-word keywords are allowed if they pass stricter validation:
        - Minimum length >= 6
        - Not a weak/stopword
        - Not numeric/junk
        """
        if not term:
            return False, "empty"

        norm = KeywordQualityEngine.normalize(term)

        words = norm.split()

        if len(words) == 1:
            return KeywordQualityEngine._check_single_word_gate(norm, words[0])

        if len(words) > _CFG["max_multi_word_count"]:
            return False, "too_many_words"

        # Character length for multi-word
        if len(norm) < _CFG["min_multi_word_char_length"]:
            return False, "too_short"
        if len(norm) > _CFG["max_word_length"]:
            return False, "too_long"

        # Repeated tokens (e.g. "app app")
        if len(set(words)) < len(words):
            return False, "repeated_tokens"

        # Stop-word ratio
        non_stop = [w for w in words if w not in _STOPWORDS]
        if len(non_stop) == 0:
            return False, "all_stopwords"
        if len(non_stop) / len(words) < _CFG["min_non_stop_ratio"]:
            return False, "mostly_stopwords"

        # Punctuation heavy (after normalization)
        punct_count = len(re.findall(r"[^\w\s]", norm))
        if punct_count > 1:
            return False, "punctuation_heavy"

        # Number heavy (>50% tokens are pure digits)
        digit_tokens = [w for w in words if w.isdigit()]
        if len(digit_tokens) / len(words) > 0.5:
            return False, "number_heavy"

        # Junk phrase exact match
        if norm in _JUNK_PHRASES:
            return False, "junk_phrase"

        return True, ""

    @staticmethod
    def _check_single_word_gate(norm: str, word: str) -> Tuple[bool, str]:
        """
        Validate single-word keyword with stricter rules.

        Single-word keywords are only accepted if:
        - Not a weak/stopword (checked first for important filtering)
        - Not numeric only
        - Not repeated characters
        - Length >= min_single_word_length characters
        """
        if word in _WEAK_SINGLE_WORDS:
            return False, "single_word_weak"

        if word in _STOPWORDS:
            return False, "single_word_stopword"

        if word.isdigit():
            return False, "single_word_numeric"

        if len(set(word)) < len(word) / 2:
            return False, "single_word_repeated_chars"

        if len(word) < _CFG["min_single_word_length"]:
            return False, "single_word_too_short"

        if len(word) > _CFG["max_word_length"]:
            return False, "too_long"

        return True, ""

    # -----------------------------------------------------------------------
    # Quality score computation (0–100)
    # -----------------------------------------------------------------------

    @staticmethod
    def compute_quality_score(
        term: str,
        keyword_source: Optional[str] = None,
        apps_count: int = 0,
        search_volume: int = 0,
        difficulty: float = 0.0,
        trend_score: float = 0.0,
        apple_top_names: Optional[List[str]] = None,
        app_title: str = "",
        app_subtitle: str = "",
        validation_score_override: Optional[float] = None,
    ) -> Tuple[float, float, float]:
        """
        Compute quality_score (0–100), validation_score (0–25), relevance_score (0–5).

        Formula::
            quality_score =
                source_score      (0-15)   source weight lookup
              + phrase_score      (0-20)   word count + length + punctuation
              + validation_score  (0-25)   Apple iTunes result count + token match
              + volume_score      (0-15)   search_volume bracketed
              + diff_score        (0-10)   (1 - difficulty/100) × 10
              + competitor_score  (0-5)    apps_count sweet-spot
              + trend_component   (0-5)    trend_score / 100 × 5
              + relevance_score   (0-5)    word overlap with app title/subtitle

        Returns (quality_score, validation_score, relevance_score).
        
        Note: apps_count should be the raw iTunes result count (number of apps 
        returned for this keyword), NOT the derived search_volume score (0-100).
        search_volume is a separate metric used for volume_score.
        """
        # ── Defensive check: detect suspicious patterns ────────────────────────
        # If apps_count looks like a derived score (0-100), it's likely a bug
        if apps_count > 0 and search_volume > 0:
            if abs(apps_count - search_volume) < 5 and apps_count <= 100:
                logger.warning(
                    f"[QualityScore] Suspicious: term={term!r}, apps_count={apps_count}, "
                    f"search_volume={search_volume} — apps_count may incorrectly equal search_volume. "
                    f"apps_count should be raw result count, not derived score."
                )
        
        norm = KeywordQualityEngine.normalize(term)
        words = norm.split()

        # ── source_score (0-15) ───────────────────────────────────────────
        source_key = (keyword_source or "").lower().strip()
        source_score = float(_SOURCE_WEIGHTS.get(source_key, _SOURCE_WEIGHT_DEFAULT))

        # ── phrase_score (0-20) ──────────────────────────────────────────
        wc = len(words)
        # Word count component (+10 for 2-4 words, +5 otherwise)
        wc_pts = 10.0 if 2 <= wc <= 4 else 5.0
        # Length component
        char_count = len(norm)
        if 8 <= char_count <= 25:
            len_pts = 5.0
        elif (5 <= char_count <= 7) or (26 <= char_count <= 35):
            len_pts = 3.0
        else:
            len_pts = 1.0
        # Punctuation component
        remaining_punct = len(re.findall(r"[^\w\s]", norm))
        punct_pts = 5.0 if remaining_punct == 0 else 2.0
        phrase_score = wc_pts + len_pts + punct_pts

        # ── validation_score (0-25) ─ Apple result count + token match ───
        if validation_score_override is not None:
            validation_score = float(validation_score_override)
        else:
            if apps_count == 0:
                validation_score = 0.0
            elif apps_count <= 5:
                validation_score = 5.0
            elif apps_count <= 20:
                validation_score = 10.0
            elif apps_count <= 100:
                validation_score = 15.0
            else:
                validation_score = 20.0

            # Token-match bonus: +1.0 per term token (len>3) found in any of
            # the top-5 Apple app names, capped at +5.0
            if apple_top_names:
                bonus = 0.0
                for token in words:
                    if len(token) > 3:
                        for name in (apple_top_names[:5] or []):
                            if token in (name or "").lower():
                                bonus += 1.0
                                break
                validation_score = min(validation_score + bonus, 25.0)

        # ── volume_score (0-15) ──────────────────────────────────────────
        if search_volume == 0:
            volume_score = 0.0
        elif search_volume <= 10:
            volume_score = 5.0
        elif search_volume <= 50:
            volume_score = 8.0
        elif search_volume <= 100:
            volume_score = 12.0
        else:
            volume_score = 15.0

        # ── diff_score (0-10) ────────────────────────────────────────────
        diff_score = (1.0 - min(difficulty, 100.0) / 100.0) * 10.0

        # ── competitor_score (0-5) ───────────────────────────────────────
        if 5 <= apps_count <= 50:
            competitor_score = 5.0    # niche opportunity sweet-spot
        elif 1 <= apps_count <= 4:
            competitor_score = 3.0    # very niche
        elif 51 <= apps_count <= 200:
            competitor_score = 2.0    # crowded
        else:
            competitor_score = 0.0    # empty (no data) or saturated

        # ── trend_component (0-5) ────────────────────────────────────────
        trend_component = min(trend_score / 100.0 * 5.0, 5.0)

        # ── relevance_score (0-5) ─ word overlap with app context ─────────
        relevance_score = 0.0
        if app_title or app_subtitle:
            context = (app_title + " " + app_subtitle).lower()
            for word in words:
                if len(word) > 3 and word in context:
                    relevance_score += 2.5
            relevance_score = min(relevance_score, 5.0)

        # ── Total ─────────────────────────────────────────────────────────
        total = (
            source_score
            + phrase_score
            + validation_score
            + volume_score
            + diff_score
            + competitor_score
            + trend_component
            + relevance_score
        )
        
        # Apply penalty for single-word keywords
        single_word_penalty = _CFG["single_word_penalty"]
        if len(words) == 1:
            total = total * single_word_penalty
        
        quality_score = round(min(total, 100.0), 1)
        return quality_score, round(validation_score, 1), round(relevance_score, 1)

    # -----------------------------------------------------------------------
    # Tier assignment
    # -----------------------------------------------------------------------

    @staticmethod
    def assign_tier(quality_score: float) -> Optional[str]:
        """
        A: quality_score >= 75  (always kept)
        B: quality_score >= 60  (accepted)
        C: quality_score >= 45  (accepted cautiously)
        None: quality_score < 45  (should be rejected)
        """
        _t = _CFG["tier_thresholds"]
        if quality_score >= _t["A"]:
            return "A"
        elif quality_score >= _t["B"]:
            return "B"
        elif quality_score >= _t["C"]:
            return "C"
        return None

    # -----------------------------------------------------------------------
    # Global cap (requires DB)
    # -----------------------------------------------------------------------

    @staticmethod
    def should_reject_tier_c(db) -> bool:
        """Return True when total keyword count >= TIER_C_STOP_THRESHOLD (900k)."""
        try:
            from app.models.models import Keyword
            count = db.query(Keyword).count()
            return count >= TIER_C_STOP_THRESHOLD
        except Exception as exc:
            logger.warning(f"[QualityEngine] should_reject_tier_c failed: {exc}")
            return False  # fail open

    @staticmethod
    def prune_tier_c_to_target(db) -> int:
        """
        Delete weakest Tier-C keywords in passes of 10,000 until
        total keyword count drops below TIER_C_PRUNE_TARGET (850k).
        Returns total rows deleted.
        """
        from sqlalchemy import text

        total_deleted = 0
        max_passes = 20  # safety ceiling

        for _ in range(max_passes):
            try:
                count = db.execute(text("SELECT COUNT(*) FROM keywords")).scalar() or 0
                if count < TIER_C_PRUNE_TARGET:
                    break

                result = db.execute(text("""
                    DELETE FROM keywords
                    WHERE id IN (
                        SELECT id FROM keywords
                        WHERE quality_tier = 'C'
                        ORDER BY quality_score ASC, last_seen_at ASC NULLS FIRST
                        LIMIT 10000
                    )
                """))
                deleted = result.rowcount or 0
                if deleted == 0:
                    break
                db.commit()
                total_deleted += deleted
                logger.info(
                    f"[QualityEngine] tier_c_cap pass: deleted {deleted}, "
                    f"total_deleted={total_deleted}"
                )
            except Exception as exc:
                logger.error(f"[QualityEngine] prune_tier_c_to_target error: {exc}")
                try:
                    db.rollback()
                except Exception:
                    pass
                break

        return total_deleted

    # -----------------------------------------------------------------------
    # Per-app source quota (requires DB)
    # -----------------------------------------------------------------------

    @staticmethod
    def check_app_quota(db, app_id: int, source: str) -> bool:
        """
        Return True if this app+source combination has room for more keywords.

        source: raw source string ('autocomplete', 'alphabet', 'title', 'competitor', …)
        """
        from app.models.models import AppDiscoveredKeyword
        from sqlalchemy import func

        group = _SOURCE_GROUP.get(source, source)
        per_source_limit = SOURCE_QUOTAS.get(group, 25)
        group_sources = _get_source_group_values(group)

        try:
            source_count = (
                db.query(func.count(AppDiscoveredKeyword.id))
                .filter(
                    AppDiscoveredKeyword.app_id == app_id,
                    AppDiscoveredKeyword.source.in_(group_sources),
                )
                .scalar() or 0
            )
            if source_count >= per_source_limit:
                return False

            total_count = (
                db.query(func.count(AppDiscoveredKeyword.id))
                .filter(AppDiscoveredKeyword.app_id == app_id)
                .scalar() or 0
            )
            return total_count < TOTAL_APP_QUOTA
        except Exception as exc:
            logger.warning(f"[QualityEngine] check_app_quota failed: {exc}")
            return True  # fail open — don't block on quota errors
