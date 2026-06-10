from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from collections import defaultdict
from sqlalchemy import func, and_, distinct, text
from sqlalchemy.sql import bindparam

from app.models.models import App, Ranking, Review, Keyword, AppKeyword, Opportunity, Category, AppKeywordIntelligence, AppDiscoveredKeyword, KeywordStatus
from app.scoring.weights import SCORING_WEIGHTS
from app.config.scoring_config import (
    TRENDING_CONFIG,
    OPPORTUNITY_CONFIG,
    FRESH_RISERS_CONFIG,
    SIGNAL_CONFIDENCE_CONFIG,
    WINNABILITY_CONFIG,
    SUCCESS_PROBABILITY_CONFIG,
    IDEA_GENERATOR_CONFIG,
    ENGINE_CONFIG,
)

# ---------------------------------------------------------------------------
# Module-level constants derived from central config (WINNABILITY_CONFIG)
# ---------------------------------------------------------------------------

_BIG_BRAND_DEVELOPERS    = WINNABILITY_CONFIG["big_brand_developers"]
_BIG_BRAND_APP_KEYWORDS  = WINNABILITY_CONFIG["big_brand_app_keywords"]
_BRAND_SUBSTR_MIN_LEN    = WINNABILITY_CONFIG["brand_substring_min_length"]

_DOMINANCE_REVIEW_HARD   = WINNABILITY_CONFIG["dominance_review_hard"]
_DOMINANCE_REVIEW_RATED  = WINNABILITY_CONFIG["dominance_review_rated"]
_DOMINANCE_RATED_FLOOR   = WINNABILITY_CONFIG["dominance_rated_floor"]
_DOMINANCE_TOP_RANK      = WINNABILITY_CONFIG["dominance_top_rank"]
_DOMINANCE_TOP_REVIEWS   = WINNABILITY_CONFIG["dominance_top_reviews"]

# Keyword phrase-extraction helpers (ENGINE_CONFIG)
_STOPWORDS    = ENGINE_CONFIG["stopwords"]
_WEAK_KEYWORDS = ENGINE_CONFIG["weak_keywords"]


class ScoringEngine:
    def __init__(self, db: Session):
        self.db = db
        self.weights = SCORING_WEIGHTS

    def calculate_rank_velocity(self, app_id: int, days: int = 7) -> float:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        rankings = (
            self.db.query(Ranking)
            .filter(
                and_(
                    Ranking.app_id == app_id,
                    Ranking.recorded_at >= cutoff_date
                )
            )
            .order_by(Ranking.recorded_at)
            .all()
        )

        if len(rankings) < 2:
            return 0.0

        ranks = [r.rank for r in rankings if r.rank is not None]
        if len(ranks) < 2:
            return 0.0

        velocity = (ranks[0] - ranks[-1]) / len(ranks)
        return float(velocity)

    def calculate_review_growth(self, app_id: int, days: int = 30) -> float:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        reviews_count = (
            self.db.query(Review)
            .filter(
                and_(
                    Review.app_id == app_id,
                    Review.date >= cutoff_date
                )
            )
            .count()
        )

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app or not app.current_reviews or app.current_reviews == 0:
            return 0.0

        growth_rate = reviews_count / app.current_reviews
        return min(growth_rate * 100, 100)

    def calculate_rating_velocity(self, app_id: int, days: int = 30) -> float:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        recent_reviews = (
            self.db.query(Review)
            .filter(
                and_(
                    Review.app_id == app_id,
                    Review.date >= cutoff_date
                )
            )
            .all()
        )

        if not recent_reviews:
            return 0.0

        ratings = [r.rating for r in recent_reviews if r.rating is not None]
        if not ratings:
            return 0.0

        recent_avg = sum(ratings) / len(ratings)

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app or app.current_rating is None:
            return 0.0

        velocity = recent_avg - app.current_rating
        return float(velocity)

    def calculate_keyword_competition(self, keyword: str) -> float:
        keyword_obj = self.db.query(Keyword).filter(Keyword.term == keyword).first()

        if not keyword_obj:
            return 50.0

        base_difficulty = keyword_obj.difficulty if keyword_obj.difficulty and keyword_obj.difficulty > 0 else 50.0

        app_count = (
            self.db.query(AppKeyword)
            .join(Keyword, AppKeyword.keyword_id == Keyword.id)
            .filter(Keyword.term == keyword)
            .count()
        )

        competition_boost = min(
            app_count * ENGINE_CONFIG["competition_per_app_boost"],
            ENGINE_CONFIG["competition_max_boost"],
        )
        return min(base_difficulty + competition_boost, 100)

    def calculate_category_growth(self, category_id: int, days: int = 30) -> float:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        recent_count = (
            self.db.query(Ranking.app_id)
            .filter(
                and_(
                    Ranking.category_id == category_id,
                    Ranking.recorded_at >= cutoff_date
                )
            )
            .distinct()
            .count()
        )

        if recent_count == 0:
            return 0.0

        return min(recent_count * ENGINE_CONFIG["category_growth_scale"], 100)

    def calculate_ai_potential(self, app_id: int, app_name: str, description: str = "") -> float:
        """Return a 0-100 AI potential score for an app (float, backward-compatible)."""
        result = self.calculate_ai_potential_structured(app_id)
        return result["ai_potential_score"]

    def calculate_ai_potential_structured(
        self, app_id: int
    ) -> Dict:
        """
        Return the full structured AI potential result:
            {
                "ai_potential_score":  float,   # 0-100
                "ai_opportunity_type": str,     # 'ai_native' | 'ai_enhanced' | 'weak'
                "ai_signal_sources":   list,    # labels of detected signals
            }

        Uses a weighted multi-signal model defined in app.scoring.ai_potential.
        Signals:
          - title_signal       ×0.35  (explicit AI terms in title)
          - description_signal ×0.25  (AI phrases in subtitle/description)
          - feature_gap_signal ×0.20  (user reviews requesting AI features)
          - category_signal    ×0.10  (category name associated with AI opportunity)
          - keyword_signal     ×0.10  (discovered keywords contain AI phrases)
        """
        from app.scoring.ai_potential import calculate_ai_potential_v2
        from app.models.models import FeatureGap, AppDiscoveredKeyword

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return {
                "ai_potential_score":  0.0,
                "ai_opportunity_type": "weak",
                "ai_signal_sources":   [],
            }

        feature_gaps = (
            self.db.query(FeatureGap)
            .filter(FeatureGap.app_id == app_id)
            .all()
        )
        discovered = (
            self.db.query(AppDiscoveredKeyword)
            .filter(AppDiscoveredKeyword.app_id == app_id)
            .all()
        )

        return calculate_ai_potential_v2(app, feature_gaps, discovered)

    def calculate_success_probability(
        self,
        rank_velocity: float,
        review_growth: float,
        competition_score: float,
        ai_potential: float,
        category_growth: float
    ) -> float:
        _spc = SUCCESS_PROBABILITY_CONFIG
        rank_factor = (
            min(rank_velocity * _spc["rank_velocity_scale"], _spc["rank_velocity_max"])
            if rank_velocity > 0 else _spc["rank_velocity_default"]
        )
        review_factor     = min(review_growth   * _spc["review_growth_scale"],  _spc["review_growth_max"])
        competition_factor = (100 - competition_score) * _spc["competition_scale"]
        ai_factor          = ai_potential               * _spc["ai_potential_scale"]
        category_factor    = category_growth            * _spc["category_growth_scale"]

        probability = rank_factor + review_factor + competition_factor + ai_factor + category_factor
        return min(max(probability, 0), 100)

    def score_opportunity(self, app_id: int, primary_keyword: str) -> Optional[Dict]:
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return None

        rank_velocity = self.calculate_rank_velocity(app_id)
        review_growth = self.calculate_review_growth(app_id)
        rating_velocity = self.calculate_rating_velocity(app_id)
        competition_score = self.calculate_keyword_competition(primary_keyword)

        category_growth = 0.0
        if app.category_id:
            category_growth = self.calculate_category_growth(app.category_id)

        ai_potential = self.calculate_ai_potential(app_id, app.name, app.description or "")

        success_prob = self.calculate_success_probability(
            rank_velocity,
            review_growth,
            competition_score,
            ai_potential,
            category_growth
        )

        _spc = SUCCESS_PROBABILITY_CONFIG
        trend_score = min(
            (rank_velocity * _spc["trend_rank_scale"]
             + review_growth * _spc["trend_review_scale"]
             + category_growth * _spc["trend_category_scale"]),
            100,
        )

        return {
            "app_id": app_id,
            "app_name": app.name,
            "primary_keyword": primary_keyword,
            "competition_score": round(competition_score, 2),
            "trend_score": round(trend_score, 2),
            "success_probability": round(success_prob, 2),
            "ai_integration_potential": round(ai_potential, 2),
            "rank_velocity": round(rank_velocity, 2),
            "review_growth": round(review_growth, 2),
            "rating_velocity": round(rating_velocity, 2),
            "category_growth": round(category_growth, 2),
            "recommendation": self._generate_recommendation(
                app.name,
                success_prob,
                trend_score,
                competition_score,
                ai_potential
            )
        }

    def _generate_recommendation(
        self,
        app_name: str,
        success_prob: float,
        trend_score: float,
        competition: float,
        ai_potential: float
    ) -> str:
        recommendations = []

        _spc = SUCCESS_PROBABILITY_CONFIG
        if success_prob > _spc["high_potential_threshold"]:
            recommendations.append(f"High-potential app! {app_name} shows strong growth metrics.")
        elif success_prob > _spc["moderate_potential_threshold"]:
            recommendations.append(f"Moderate opportunity. {app_name} has decent metrics.")
        else:
            recommendations.append("Low immediate potential. Consider different keywords.")

        if trend_score > _spc["trend_alert_threshold"]:
            recommendations.append("Strong upward trend - enter soon!")

        if competition < _spc["competition_low_threshold"]:
            recommendations.append("Low competition - good keyword targeting opportunity.")
        elif competition > _spc["competition_high_threshold"]:
            recommendations.append("High competition - need strong differentiation.")

        if ai_potential > _spc["ai_opportunity_threshold"]:
            recommendations.append("Great candidate for AI feature integration.")

        return " ".join(recommendations[:3])

    # ------------------------------------------------------------------
    # Big-brand / dominance filters
    # ------------------------------------------------------------------

    def _is_excluded_big_brand(self, app: App) -> Tuple[bool, str]:
        """Return (True, reason) if the app belongs to a big-brand developer."""
        dev = (app.developer or "").strip().lower()
        if dev in _BIG_BRAND_DEVELOPERS:
            return True, f"Developer '{app.developer}' is a major company"
        for brand in _BIG_BRAND_DEVELOPERS:
            if len(brand) > _BRAND_SUBSTR_MIN_LEN and brand in dev:
                return True, f"Developer name contains brand token '{brand}'"

        name_lower = (app.name or "").lower()
        for kw in _BIG_BRAND_APP_KEYWORDS:
            if kw.strip() in name_lower:
                return True, f"App name contains big-brand keyword '{kw.strip()}'"

        return False, ""

    def _is_dominated_market(self, app: App) -> Tuple[bool, str]:
        """Return (True, reason) if this app is an entrenched market incumbent."""
        reviews = app.current_reviews or 0
        rating = app.current_rating or 0.0
        rank = app.current_rank

        if reviews >= _DOMINANCE_REVIEW_HARD:
            return True, f"{reviews:,} reviews — absolute behemoth"
        if reviews >= _DOMINANCE_REVIEW_RATED and rating >= _DOMINANCE_RATED_FLOOR:
            return True, f"{reviews:,} reviews + {rating:.1f}★ — entrenched and beloved"
        if rank is not None and rank <= _DOMINANCE_TOP_RANK and reviews >= _DOMINANCE_TOP_REVIEWS:
            return True, f"Rank #{rank} with {reviews:,} reviews — chart dominator"

        return False, ""

    # ------------------------------------------------------------------
    # Feasibility / winnability scoring
    # ------------------------------------------------------------------

    def calculate_feasibility_score(
        self, app: App, competition_score: float, gap_count: Optional[int] = None
    ) -> Tuple[float, Dict]:
        """
        Score how feasible it is for an indie developer to win in this space.

        Components (100 pts total):
          review_pts      (25) — fewer reviews = easier to enter
          competition_pts (25) — lower keyword difficulty = easier ASO
          gap_pts         (20) — feature-gap requests = clear differentiation path
          rating_pts      (15) — lower avg rating = unhappy users to win over
          rank_pts        (15) — rank > 20 = not locked out of charts

        gap_count: pre-loaded count to avoid a DB query; fetched on-demand if None.
        """
        from app.models.models import FeatureGap

        _wc = WINNABILITY_CONFIG
        reviews = app.current_reviews or 0
        rating = app.current_rating or 3.0
        rank = app.current_rank or 999

        # 1. Review scarcity — fewer reviews = easier to enter
        _rb = _wc["feasibility_review_bands"]
        if reviews < 500:
            review_pts = _rb[500]
        elif reviews < 5_000:
            review_pts = _rb[5_000]
        elif reviews < 20_000:
            review_pts = _rb[20_000]
        elif reviews < 50_000:
            review_pts = _rb[50_000]
        elif reviews < 100_000:
            review_pts = _rb[100_000]
        else:
            review_pts = _wc["feasibility_review_floor"]

        # 2. Low keyword competition
        competition_pts = max(
            0.0,
            (100.0 - competition_score) / _wc["feasibility_competition_divisor"],
        )

        # 3. Feature gap signals
        if gap_count is None:
            gap_count = (
                self.db.query(FeatureGap)
                .filter(FeatureGap.app_id == app.id)
                .count()
            )
        gap_pts = min(gap_count * _wc["feasibility_gap_scale"], _wc["feasibility_gap_max"])

        # 4. Rating weakness — lower rating means more room to win
        _rat = _wc["feasibility_rating_bands"]
        if rating < 2.0:
            rating_pts = _rat[2.0]
        elif rating < 3.0:
            rating_pts = _rat[3.0]
        elif rating < 3.5:
            rating_pts = _rat[3.5]
        elif rating < 4.0:
            rating_pts = _rat[4.0]
        else:
            rating_pts = _wc["feasibility_rating_floor"]

        # 5. Rank accessibility — not locked out of charts
        _rnk = _wc["feasibility_rank_bands"]
        if rank > 100:
            rank_pts = _wc["feasibility_rank_accessible"]
        elif rank > 50:
            rank_pts = _rnk[50]
        elif rank > 20:
            rank_pts = _rnk[20]
        else:
            rank_pts = _wc["feasibility_rank_floor"]

        total = min(review_pts + competition_pts + gap_pts + rating_pts + rank_pts, 100.0)
        details = {
            "review_pts": round(review_pts, 1),
            "competition_pts": round(competition_pts, 1),
            "gap_pts": round(gap_pts, 1),
            "rating_pts": round(rating_pts, 1),
            "rank_pts": round(rank_pts, 1),
            "gap_count": gap_count,
        }
        return round(total, 2), details

    def _generate_winnability_recommendation(
        self,
        app_name: str,
        feasibility_score: float,
        feasibility_details: Dict,
        attractiveness_score: float,
    ) -> str:
        parts = []

        _wc = WINNABILITY_CONFIG
        if feasibility_score >= _wc["winnability_high_threshold"]:
            parts.append(f"High winnability — realistic indie opportunity in the '{app_name}' niche.")
        elif feasibility_score >= _wc["winnability_moderate_threshold"]:
            parts.append(f"Moderate winnability — competition is manageable around '{app_name}'.")
        else:
            parts.append(f"Tough space — '{app_name}' category is crowded but micro-niches exist.")

        gap_count = feasibility_details.get("gap_count", 0)
        if gap_count >= _wc["recommendation_gap_min_count"]:
            parts.append(f"{gap_count} feature gaps reported by users — clear differentiation path.")
        if feasibility_details.get("rating_pts", 0) >= _wc["recommendation_rating_pts_min"]:
            parts.append("Users are unhappy with existing options — quality gap to exploit.")
        if feasibility_details.get("review_pts", 0) >= _wc["recommendation_review_pts_min"]:
            parts.append("Low review count — early-mover advantage still available.")
        if feasibility_details.get("competition_pts", 0) >= _wc["recommendation_competition_pts_min"]:
            parts.append("Low keyword competition — strong ASO opportunity.")

        return " ".join(parts[:3])

    # ------------------------------------------------------------------
    # Opportunity of the Day
    # ------------------------------------------------------------------

    def _build_scored_opportunities(self) -> List[Dict]:
        """
        Score all ranked apps and return them sorted by success_probability descending.

        Uses 4-tier keyword selection, brand/incumbent exclusions, attractiveness,
        and feasibility scoring. Shared by generate_opportunity_of_day() and
        get_all_scored_opportunities().

        Bulk-loads all data before the scoring loop to avoid N+1 queries.
        Total DB queries: ~10 fixed regardless of candidate count.
        """
        from app.models.models import FeatureGap
        from app.scoring.ai_potential import calculate_ai_potential_v2

        apps = self.db.query(App).filter(App.current_rank.isnot(None)).all()
        if not apps:
            return []

        # --- Filter excluded apps (no DB needed) ---
        candidates = []
        for app in apps:
            excluded, _ = self._is_excluded_big_brand(app)
            if excluded:
                continue
            dominated, _ = self._is_dominated_market(app)
            if dominated:
                continue
            candidates.append(app)

        if not candidates:
            return []

        all_ids = [a.id for a in candidates]
        cat_ids = list({a.category_id for a in candidates if a.category_id})
        cutoff_7d  = datetime.now(timezone.utc) - timedelta(days=7)
        cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)

        # --- Bulk load 1: Rankings 7d ---
        rankings_7d_rows = (
            self.db.query(Ranking.app_id, Ranking.rank, Ranking.recorded_at)
            .filter(Ranking.app_id.in_(all_ids), Ranking.recorded_at >= cutoff_7d)
            .order_by(Ranking.app_id, Ranking.recorded_at)
            .all()
        )
        rankings_7d: Dict[int, list] = defaultdict(list)
        for app_id, rank, recorded_at in rankings_7d_rows:
            rankings_7d[app_id].append((rank, recorded_at))

        # --- Bulk load 2: Reviews 30d (rating + date) ---
        reviews_30d_rows = (
            self.db.query(Review.app_id, Review.rating, Review.date)
            .filter(Review.app_id.in_(all_ids), Review.date >= cutoff_30d)
            .all()
        )
        reviews_30d: Dict[int, list] = defaultdict(list)
        for app_id, rating, date in reviews_30d_rows:
            reviews_30d[app_id].append((rating, date))

        # --- Bulk load 3: Categories ---
        cat_name_map: Dict[int, str] = {}
        if cat_ids:
            cat_rows = self.db.query(Category.id, Category.name).filter(Category.id.in_(cat_ids)).all()
            cat_name_map = {cid: (name or "general") for cid, name in cat_rows}

        # --- Bulk load 4: Category growth (distinct apps per category, 30d) ---
        cat_growth_map: Dict[int, float] = {}
        if cat_ids:
            cat_growth_rows = (
                self.db.query(
                    Ranking.category_id,
                    func.count(distinct(Ranking.app_id)).label("cnt"),
                )
                .filter(Ranking.category_id.in_(cat_ids), Ranking.recorded_at >= cutoff_30d)
                .group_by(Ranking.category_id)
                .all()
            )
            for cid, cnt in cat_growth_rows:
                cat_growth_map[cid] = min(cnt * ENGINE_CONFIG["category_growth_scale"], 100.0)

        # --- Bulk load 5: Feature gap counts (for feasibility) ---
        gap_count_rows = (
            self.db.query(FeatureGap.app_id, func.count(FeatureGap.id).label("cnt"))
            .filter(FeatureGap.app_id.in_(all_ids))
            .group_by(FeatureGap.app_id)
            .all()
        )
        gap_count_map: Dict[int, int] = {app_id: cnt for app_id, cnt in gap_count_rows}

        # --- Bulk load 6: Feature gap objects (for AI potential) ---
        feature_gap_rows = (
            self.db.query(FeatureGap)
            .filter(FeatureGap.app_id.in_(all_ids))
            .all()
        )
        feature_gaps_by_app: Dict[int, list] = defaultdict(list)
        for fg in feature_gap_rows:
            feature_gaps_by_app[fg.app_id].append(fg)

        # --- Bulk load 7: Best AppKeywordIntelligence per app (Tier 1) ---
        intel_rows = (
            self.db.query(AppKeywordIntelligence.app_id, Keyword.term, AppKeywordIntelligence.traffic_score)
            .join(Keyword, Keyword.id == AppKeywordIntelligence.keyword_id)
            .filter(AppKeywordIntelligence.app_id.in_(all_ids))
            .order_by(AppKeywordIntelligence.app_id, AppKeywordIntelligence.traffic_score.desc())
            .all()
        )
        best_intel_by_app: Dict[int, str] = {}
        for app_id, term, _ in intel_rows:
            if app_id not in best_intel_by_app and term and not self._is_weak_keyword(term):
                best_intel_by_app[app_id] = term

        # --- Bulk load 8: AppDiscoveredKeywords (Tier 2 + AI potential) ---
        disc_rows = (
            self.db.query(AppDiscoveredKeyword)
            .filter(AppDiscoveredKeyword.app_id.in_(all_ids))
            .order_by(AppDiscoveredKeyword.app_id, AppDiscoveredKeyword.opportunity_score.desc())
            .all()
        )
        best_disc_by_app: Dict[int, str] = {}
        disc_all_by_app: Dict[int, list] = defaultdict(list)
        for dkw in disc_rows:
            disc_all_by_app[dkw.app_id].append(dkw)
            if (
                dkw.app_id not in best_disc_by_app
                and dkw.keyword
                and dkw.opportunity_score
                and dkw.opportunity_score > 0
                and not self._is_weak_keyword(dkw.keyword)
            ):
                best_disc_by_app[dkw.app_id] = dkw.keyword

        # --- Phase 1: Keyword selection in-memory; collect Tier-3 phrases ---
        primary_kws: Dict[int, object] = {}
        phrases_to_lookup: set = set()

        for app in candidates:
            if app.id in best_intel_by_app:
                primary_kws[app.id] = best_intel_by_app[app.id]
                continue
            if app.id in best_disc_by_app:
                primary_kws[app.id] = best_disc_by_app[app.id]
                continue
            app_text = f"{app.name or ''} {app.subtitle or ''}".strip()
            phrases = self._extract_phrases(app_text, min_words=2, max_words=3)
            if phrases:
                phrases_to_lookup.update(phrases)
                primary_kws[app.id] = ("__phrases__", phrases)
            else:
                words = app_text.split()
                valid_words = [w for w in words if not self._is_weak_keyword(w)]
                if len(valid_words) >= 2:
                    primary_kws[app.id] = f"{valid_words[0]} {valid_words[1]}".lower()
                elif valid_words:
                    primary_kws[app.id] = valid_words[0].lower()
                else:
                    primary_kws[app.id] = "app"

        # --- Bulk load 9: Keyword rows for Tier-3 phrases ---
        phrase_kw_map: Dict[str, float] = {}
        if phrases_to_lookup:
            kw_phrase_rows = (
                self.db.query(Keyword.term, Keyword.opportunity_score)
                .filter(Keyword.term.in_(list(phrases_to_lookup)))
                .all()
            )
            for term, opp_score in kw_phrase_rows:
                phrase_kw_map[term] = opp_score or 10.0

        # Resolve Tier-3 placeholders
        for app in candidates:
            kw = primary_kws.get(app.id)
            if isinstance(kw, tuple) and kw[0] == "__phrases__":
                phrases = kw[1]
                scored_phrases = sorted(
                    [(p, phrase_kw_map.get(p, 10.0)) for p in phrases],
                    key=lambda x: x[1],
                    reverse=True,
                )
                primary_kws[app.id] = scored_phrases[0][0] if scored_phrases else "app"

        # --- Bulk load 10: Keyword difficulty + AppKeyword counts for all primary kws ---
        unique_kws = list({kw for kw in primary_kws.values() if isinstance(kw, str)})
        kw_diff_map: Dict[str, float] = {}
        kw_app_count_map: Dict[str, int] = {}
        if unique_kws:
            kw_diff_rows = (
                self.db.query(Keyword.term, Keyword.difficulty)
                .filter(Keyword.term.in_(unique_kws))
                .all()
            )
            for term, diff in kw_diff_rows:
                kw_diff_map[term] = diff if diff and diff > 0 else 50.0

            kw_count_rows = (
                self.db.query(Keyword.term, func.count(AppKeyword.id).label("cnt"))
                .join(AppKeyword, AppKeyword.keyword_id == Keyword.id)
                .filter(Keyword.term.in_(unique_kws))
                .group_by(Keyword.term)
                .all()
            )
            for term, cnt in kw_count_rows:
                kw_app_count_map[term] = cnt

        # --- Phase 2: Score each candidate in-memory (no DB queries) ---
        _aw = WINNABILITY_CONFIG["attractiveness_weights"]
        _cw = WINNABILITY_CONFIG["combined_weights"]
        scored = []

        for app in candidates:
            primary_keyword = primary_kws.get(app.id, "app")
            if not isinstance(primary_keyword, str):
                primary_keyword = "app"

            # Competition score
            base_diff = kw_diff_map.get(primary_keyword, 50.0)
            app_count = kw_app_count_map.get(primary_keyword, 0)
            competition_boost = min(
                app_count * ENGINE_CONFIG["competition_per_app_boost"],
                ENGINE_CONFIG["competition_max_boost"],
            )
            competition_score = min(base_diff + competition_boost, 100.0)

            # AI potential (preloaded objects, no DB)
            ai_result = calculate_ai_potential_v2(
                app,
                feature_gaps_by_app.get(app.id, []),
                disc_all_by_app.get(app.id, []),
            )
            ai_potential = ai_result.get("ai_potential_score", 0.0) if isinstance(ai_result, dict) else float(ai_result)

            # Attractiveness
            rank_score = max(0.0, 100.0 - (app.current_rank * 2)) if app.current_rank else 0.0
            rating_score = (app.current_rating or 0.0) * 20.0
            attractiveness = min(
                rank_score        * _aw["rank_score"] +
                rating_score      * _aw["rating_score"] +
                (100.0 - competition_score) * _aw["competition_score"] +
                ai_potential      * _aw["ai_potential"],
                100.0,
            )

            # Feasibility (gap_count pre-loaded)
            gap_count = gap_count_map.get(app.id, 0)
            feasibility, feasibility_details = self.calculate_feasibility_score(
                app, competition_score, gap_count=gap_count
            )

            combined = attractiveness * _cw["attractiveness"] + feasibility * _cw["feasibility"]

            # In-memory signals
            rank_velocity    = self._rank_velocity_from_prefetch(rankings_7d.get(app.id, []))
            review_growth    = self._review_growth_from_prefetch(reviews_30d.get(app.id, []), app.current_reviews)
            rating_velocity  = self._rating_velocity_from_prefetch(reviews_30d.get(app.id, []), app.current_rating)
            category_growth  = cat_growth_map.get(app.category_id, 0.0) if app.category_id else 0.0
            category_name    = cat_name_map.get(app.category_id, "general") if app.category_id else "general"

            scored.append({
                "app_id": app.id,
                "app_name": app.name,
                "primary_keyword": primary_keyword,
                "competition_score": round(competition_score, 2),
                "trend_score": round(min(rank_score * 0.6 + rating_score * 0.4, 100.0), 2),
                "success_probability": round(combined, 2),
                "attractiveness_score": round(attractiveness, 2),
                "feasibility_score": round(feasibility, 2),
                "feasibility_details": feasibility_details,
                "ai_integration_potential": round(ai_potential, 2),
                "rank_velocity": round(rank_velocity, 2),
                "review_growth": round(review_growth, 2),
                "rating_velocity": round(rating_velocity, 2),
                "category_growth": round(category_growth, 2),
                "category": category_name,
                "recommendation": self._generate_winnability_recommendation(
                    app.name,
                    feasibility,
                    feasibility_details,
                    attractiveness,
                ),
            })

        scored.sort(key=lambda x: x["success_probability"], reverse=True)
        return scored

    # ------------------------------------------------------------------
    # In-memory signal helpers (used by _build_scored_opportunities)
    # ------------------------------------------------------------------

    def _rank_velocity_from_prefetch(self, rankings: list) -> float:
        """Compute rank velocity from preloaded (rank, recorded_at) tuples."""
        ranks = [r for r, _ in rankings if r is not None]
        if len(ranks) < 2:
            return 0.0
        return float((ranks[0] - ranks[-1]) / len(ranks))

    def _review_growth_from_prefetch(
        self, reviews_30d: list, current_reviews: Optional[int]
    ) -> float:
        """Compute review growth rate from preloaded (rating, date) tuples."""
        if not current_reviews or current_reviews == 0:
            return 0.0
        return min(len(reviews_30d) / current_reviews * 100, 100.0)

    def _rating_velocity_from_prefetch(
        self, reviews_30d: list, current_rating: Optional[float]
    ) -> float:
        """Compute rating velocity from preloaded (rating, date) tuples."""
        if not reviews_30d or current_rating is None:
            return 0.0
        ratings = [r for r, _ in reviews_30d if r is not None]
        if not ratings:
            return 0.0
        recent_avg = sum(ratings) / len(ratings)
        return float(recent_avg - current_rating)

    def generate_opportunity_of_day(self) -> Optional[Dict]:
        """
        Generate the Opportunity of the Day by scoring all tracked apps.

        Uses 4-tier keyword selection:
        1. AppKeywordIntelligence - highest traffic_score from extracted keywords
        2. AppDiscoveredKeyword - highest opportunity_score from discovery
        3. Title/Subtitle phrases - 2-3 word phrases from app metadata
        4. Smart fallback - stopword-filtered phrase extraction
        """
        scored = self._build_scored_opportunities()
        return scored[0] if scored else None

    def get_all_scored_opportunities(self, n: Optional[int] = None) -> List[Dict]:
        """
        Return all scored opportunities sorted by success_probability descending.
        Pass n to cap the result (e.g., n=20 for candidate pool).
        Used by WeeklyOpportunitiesService to build the top-5 weekly list.
        """
        scored = self._build_scored_opportunities()
        return scored[:n] if n is not None else scored

    def get_top_trending_apps(self, limit: int = 10) -> List[Dict]:
        cutoff = datetime.utcnow() - timedelta(days=7)

        rankings = (
            self.db.query(
                Ranking.app_id,
                func.count(Ranking.id).label("rank_count"),
                func.avg(Ranking.rank_velocity).label("avg_velocity"),
                func.min(Ranking.rank).label("best_rank")
            )
            .filter(Ranking.recorded_at >= cutoff)
            .group_by(Ranking.app_id)
            .all()
        )

        trending = []
        for app_id, count, avg_velocity, best_rank in rankings:
            if avg_velocity and avg_velocity > 0:
                app = self.db.query(App).filter(App.id == app_id).first()
                if app:
                    review_growth = self.calculate_review_growth(app_id)
                    rating_velocity = self.calculate_rating_velocity(app_id)

                    trending.append({
                        "id": app.id,
                        "app_id": app.app_id,
                        "name": app.name,
                        "developer": app.developer,
                        "icon_url": app.icon_url,
                        "current_rank": app.current_rank or best_rank,
                        "rank_velocity": round(avg_velocity, 2),
                        "review_growth": round(review_growth, 2),
                        "rating_velocity": round(rating_velocity, 2),
                        "trend_score": round(avg_velocity * 20 + review_growth * 0.3, 2)
                    })

        trending.sort(key=lambda x: x["trend_score"], reverse=True)
        return trending[:limit]

    # ---------------------------------------------------------------------------
    # New Multi-Factor Trending Algorithm
    # ---------------------------------------------------------------------------
    # SOURCE OF TRUTH: All trend metrics are computed ON THE FLY from raw ranking
    # history, NOT from stored rank_velocity. This ensures consistency and accuracy.
    # ---------------------------------------------------------------------------

    def _get_ranking_history(self, app_id: int, days: int = 14) -> List[Dict]:
        """
        Fetch ranking history for an app within the given time window.
        Returns list of {rank, recorded_at, previous_rank} sorted by date.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        rankings = (
            self.db.query(Ranking)
            .filter(
                and_(
                    Ranking.app_id == app_id,
                    Ranking.recorded_at >= cutoff
                )
            )
            .order_by(Ranking.recorded_at)
            .all()
        )
        return [
            {
                "rank": r.rank,
                "previous_rank": r.previous_rank,
                "recorded_at": r.recorded_at,
            }
            for r in rankings
            if r.rank is not None
        ]

    def compute_momentum_score(self, app_id: int) -> Dict:
        """
        Compute multi-window momentum scores.
        
        Returns:
            momentum_3d: 3-day momentum (positions gained per day)
            momentum_7d: 7-day momentum
            momentum_14d: 14-day momentum
            momentum_weighted: Weighted combination favoring sustained trends
        """
        history_14d = self._get_ranking_history(app_id, days=14)
        # Slice in Python — avoids 2 extra DB round-trips
        if history_14d:
            latest_ts = history_14d[-1]["recorded_at"]
            history_7d = [h for h in history_14d
                          if (latest_ts - h["recorded_at"]).total_seconds() <= 7 * 86400]
            history_3d = [h for h in history_14d
                          if (latest_ts - h["recorded_at"]).total_seconds() <= 3 * 86400]
        else:
            history_7d = []
            history_3d = []

        def calc_momentum(history):
            if len(history) < 2:
                return 0.0
            first_rank = history[0]["rank"]
            last_rank = history[-1]["rank"]
            days_span = max((history[-1]["recorded_at"] - history[0]["recorded_at"]).days, 1)
            return (first_rank - last_rank) / days_span

        mom_3d = calc_momentum(history_3d)
        mom_7d = calc_momentum(history_7d)
        mom_14d = calc_momentum(history_14d)

        _mw = TRENDING_CONFIG["momentum_weights"]
        momentum_weighted = (
            mom_3d  * _mw["3d"] +
            mom_7d  * _mw["7d"] +
            mom_14d * _mw["14d"]
        )

        return {
            "momentum_3d": round(mom_3d, 3),
            "momentum_7d": round(mom_7d, 3),
            "momentum_14d": round(mom_14d, 3),
            "momentum_weighted": round(momentum_weighted, 3),
        }

    def compute_consistency_score(self, app_id: int) -> float:
        """
        Compute consistency/stability score based on ranking variance.
        
        Higher score = more consistent upward movement.
        Lower score = volatile/noisy movement.
        
        Uses coefficient of variation of daily rank changes.
        """
        history = self._get_ranking_history(app_id, days=14)
        
        if len(history) < 3:
            return 0.0

        daily_changes = []
        for i in range(1, len(history)):
            change = history[i-1]["rank"] - history[i]["rank"]
            daily_changes.append(change)

        if not daily_changes:
            return 0.0

        positive_moves = [c for c in daily_changes if c > 0]
        negative_moves = [c for c in daily_changes if c < 0]

        if not positive_moves:
            return 0.0

        consistency_ratio = len(positive_moves) / len(daily_changes)
        
        avg_improvement = sum(positive_moves) / len(positive_moves) if positive_moves else 0
        
        consistency_score = (consistency_ratio * 0.6) + (min(avg_improvement / 10, 1.0) * 0.4)
        
        return round(consistency_score * 100, 2)

    def compute_confidence_score(self, app_id: int) -> float:
        """
        Compute confidence score based on data quality.
        
        Factors:
        - Number of ranking snapshots (more = higher confidence)
        - Coverage within time window
        - Presence of recent data
        
        Returns 0.0 to 1.0 multiplier.
        """
        history_14d = self._get_ranking_history(app_id, days=14)
        history_7d = self._get_ranking_history(app_id, days=7)
        
        snapshot_score = min(len(history_14d) / 10, 1.0) * 0.4
        
        coverage_14d = len(history_14d) / 14 if history_14d else 0
        coverage_score = min(coverage_14d, 1.0) * 0.3
        
        has_recent = 1.0 if history_7d else 0.0
        recent_score = has_recent * 0.3
        
        return round(snapshot_score + coverage_score + recent_score, 3)

    def compute_absolute_rank_bonus(self, app_id: int) -> float:
        """
        Compute bonus for apps that are moving up from strong positions.
        
        A mover near top ranks (1-10) should generally beat a similarly
        noisy deep-rank app.
        
        BONUS SCALE: 0-20 (capped in compute_trend_score to prevent overpowering)
        """
        history = self._get_ranking_history(app_id, days=7)
        
        if not history:
            return 0.0

        best_rank = min(h["rank"] for h in history)
        current_rank = history[-1]["rank"]

        # Base bonus for best rank achieved (not overpowering)
        _rbt = TRENDING_CONFIG["rank_bonus_thresholds"]
        if best_rank <= 5:
            base_bonus = _rbt[5]
        elif best_rank <= 10:
            base_bonus = _rbt[10]
        elif best_rank <= 25:
            base_bonus = _rbt[25]
        elif best_rank <= 50:
            base_bonus = _rbt[50]
        else:
            base_bonus = 0.0

        improvement = history[0]["rank"] - current_rank
        if improvement > 0:
            return round(base_bonus * min(improvement / 15, 1.0), 2)
        
        return 0.0

    def compute_bounded_review_momentum(self, app_id: int) -> float:
        """
        Compute bounded review growth momentum.
        
        Caps the effect so tiny apps with sudden review spikes don't
        dominate the ranking.
        """
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return 0.0

        base_reviews = app.current_reviews or 0
        
        review_growth_7d = self.calculate_review_growth(app_id, days=7)
        
        _df = TRENDING_CONFIG["review_dampen_factors"]
        if base_reviews < 100:
            dampen_factor = _df[100]
        elif base_reviews < 1_000:
            dampen_factor = _df[1_000]
        elif base_reviews < 10_000:
            dampen_factor = _df[10_000]
        else:
            dampen_factor = 1.0

        bounded_score = review_growth_7d * dampen_factor
        return round(min(bounded_score, TRENDING_CONFIG["review_momentum_cap"]), 2)

    def normalize_within_category(self, app_id: int, raw_score: float) -> float:
        """
        Normalize trend score within category to prevent weak-category outliers.
        
        Uses category percentile ranking.
        """
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app or not app.category_id:
            return raw_score

        category_apps = (
            self.db.query(App)
            .filter(
                and_(
                    App.category_id == app.category_id,
                    App.current_rank.isnot(None)
                )
            )
            .all()
        )

        if len(category_apps) < 5:
            return raw_score

        ranks = [a.current_rank for a in category_apps if a.current_rank]
        if not ranks:
            return raw_score

        category_avg_rank = sum(ranks) / len(ranks)
        app_rank = app.current_rank or 999
        
        percentile = 1 - (app_rank / max(category_avg_rank * 2, 1))
        
        normalized = raw_score * (0.7 + (0.3 * max(percentile, 0)))
        
        return round(normalized, 2)

    def compute_trend_score(self, app_id: int, use_category_norm: bool = True) -> Dict:
        """
        Compute comprehensive trend score using multi-factor model.
        
        Formula:
            trend_score = (
                (momentum_weighted * 25) +
                (consistency_score * 0.15) +
                (absolute_rank_bonus * 0.25) +
                (bounded_review_momentum * 0.15)
            ) * confidence_factor
            
            Optionally normalized within category.
        
        Returns detailed breakdown for debugging.
        
        COMPONENT SCALES (normalized to 0-100 for safety):
        - momentum_weighted: positions/day (typically 0-20) → scaled by 3 → 0-60
        - consistency_score: 0-100 → weighted by 0.15 → 0-15
        - absolute_rank_bonus: 0-30 → to 0- capped20
        - review_momentum: 0-20 → weighted by 0.5 → 0-10
        
        Final score range: 0-100 (before confidence multiplier)
        """
        momentum = self.compute_momentum_score(app_id)
        consistency = self.compute_consistency_score(app_id)
        confidence = self.compute_confidence_score(app_id)
        rank_bonus = min(self.compute_absolute_rank_bonus(app_id), 20.0)  # Cap at 20
        review_momentum = self.compute_bounded_review_momentum(app_id)

        _tsw = TRENDING_CONFIG["trend_score_weights"]

        # Normalize momentum to 0-60 range (max ~20 pos/day × scale → ~60)
        momentum_normalized = min(
            momentum["momentum_weighted"] * _tsw["momentum_normalized_scale"], 60
        )
        # Normalize consistency to 0-15 range
        consistency_normalized = consistency * _tsw["consistency_weight"]
        # Rank bonus already 0-20
        rank_bonus_normalized = rank_bonus * _tsw["rank_bonus_weight"]
        # Normalize review momentum contribution
        review_normalized = review_momentum * _tsw["review_momentum_weight"]

        raw_score = (
            momentum_normalized +
            consistency_normalized +
            rank_bonus_normalized +
            review_normalized
        )

        final_score = raw_score * confidence

        if use_category_norm:
            final_score = self.normalize_within_category(app_id, final_score)

        return {
            "app_id": app_id,
            "momentum_3d": momentum["momentum_3d"],
            "momentum_7d": momentum["momentum_7d"],
            "momentum_14d": momentum["momentum_14d"],
            "momentum_weighted": momentum["momentum_weighted"],
            "consistency_score": consistency,
            "confidence_factor": confidence,
            "absolute_rank_bonus": rank_bonus,
            "review_momentum": review_momentum,
            "raw_score": round(raw_score, 2),
            "final_score": round(final_score, 2),
        }

    def compute_trend_score_from_prefetch(
        self,
        app_id: int,
        ranking_history: List[Dict],
        current_reviews: Optional[int],
        current_rank: Optional[int],
        category_id: Optional[int],
        review_count_7d: int,
        category_ranks: Optional[List[int]],
        use_category_norm: bool = True,
    ) -> Optional[Dict]:
        """
        Compute trend score using prefetched data — ZERO DB queries.

        Exact same algorithm as compute_trend_score() but all data is passed in
        so the caller can batch-prefetch for thousands of apps at once.
        """
        # Filter to records with non-null rank
        history_14d = [h for h in ranking_history if h["rank"] is not None]

        if history_14d:
            latest_ts = history_14d[-1]["recorded_at"]
            history_7d = [
                h for h in history_14d
                if (latest_ts - h["recorded_at"]).total_seconds() <= 7 * 86400
            ]
            history_3d = [
                h for h in history_14d
                if (latest_ts - h["recorded_at"]).total_seconds() <= 3 * 86400
            ]
        else:
            history_7d = []
            history_3d = []

        # --- Momentum (same as compute_momentum_score) ---
        def _calc_momentum(history):
            if len(history) < 2:
                return 0.0
            first_rank = history[0]["rank"]
            last_rank = history[-1]["rank"]
            days_span = max(
                (history[-1]["recorded_at"] - history[0]["recorded_at"]).days, 1
            )
            return (first_rank - last_rank) / days_span

        mom_3d = _calc_momentum(history_3d)
        mom_7d = _calc_momentum(history_7d)
        mom_14d = _calc_momentum(history_14d)

        _mw = TRENDING_CONFIG["momentum_weights"]
        momentum_weighted = (
            mom_3d * _mw["3d"] + mom_7d * _mw["7d"] + mom_14d * _mw["14d"]
        )

        # --- Consistency (same as compute_consistency_score) ---
        consistency = 0.0
        if len(history_14d) >= 3:
            daily_changes = [
                history_14d[i - 1]["rank"] - history_14d[i]["rank"]
                for i in range(1, len(history_14d))
            ]
            positive_moves = [c for c in daily_changes if c > 0]
            if positive_moves and daily_changes:
                consistency_ratio = len(positive_moves) / len(daily_changes)
                avg_improvement = sum(positive_moves) / len(positive_moves)
                consistency = round(
                    (consistency_ratio * 0.6 + min(avg_improvement / 10, 1.0) * 0.4)
                    * 100,
                    2,
                )

        # --- Confidence (same as compute_confidence_score) ---
        snapshot_score = min(len(history_14d) / 10, 1.0) * 0.4
        coverage_14d = len(history_14d) / 14 if history_14d else 0
        coverage_score = min(coverage_14d, 1.0) * 0.3
        recent_score = (1.0 if history_7d else 0.0) * 0.3
        confidence = round(snapshot_score + coverage_score + recent_score, 3)

        # --- Absolute Rank Bonus (same as compute_absolute_rank_bonus) ---
        rank_bonus = 0.0
        if history_7d:
            best_rank = min(h["rank"] for h in history_7d)
            current_rank_7d = history_7d[-1]["rank"]

            _rbt = TRENDING_CONFIG["rank_bonus_thresholds"]
            if best_rank <= 5:
                base_bonus = _rbt[5]
            elif best_rank <= 10:
                base_bonus = _rbt[10]
            elif best_rank <= 25:
                base_bonus = _rbt[25]
            elif best_rank <= 50:
                base_bonus = _rbt[50]
            else:
                base_bonus = 0.0

            improvement = history_7d[0]["rank"] - current_rank_7d
            if improvement > 0:
                rank_bonus = round(base_bonus * min(improvement / 15, 1.0), 2)
        rank_bonus = min(rank_bonus, 20.0)

        # --- Bounded Review Momentum (same as compute_bounded_review_momentum) ---
        base_reviews = current_reviews or 0
        if base_reviews > 0 and review_count_7d > 0:
            review_growth_7d = min(review_count_7d / base_reviews * 100, 100)
        else:
            review_growth_7d = 0.0

        _df = TRENDING_CONFIG["review_dampen_factors"]
        if base_reviews < 100:
            dampen_factor = _df[100]
        elif base_reviews < 1_000:
            dampen_factor = _df[1_000]
        elif base_reviews < 10_000:
            dampen_factor = _df[10_000]
        else:
            dampen_factor = 1.0

        review_momentum = round(
            min(review_growth_7d * dampen_factor, TRENDING_CONFIG["review_momentum_cap"]),
            2,
        )

        # --- Combine (same as compute_trend_score) ---
        _tsw = TRENDING_CONFIG["trend_score_weights"]
        momentum_normalized = min(
            momentum_weighted * _tsw["momentum_normalized_scale"], 60
        )
        consistency_normalized = consistency * _tsw["consistency_weight"]
        rank_bonus_normalized = rank_bonus * _tsw["rank_bonus_weight"]
        review_normalized = review_momentum * _tsw["review_momentum_weight"]

        raw_score = (
            momentum_normalized
            + consistency_normalized
            + rank_bonus_normalized
            + review_normalized
        )
        final_score = raw_score * confidence

        # --- Category Normalization (same as normalize_within_category) ---
        if (
            use_category_norm
            and category_id
            and category_ranks
            and len(category_ranks) >= 5
        ):
            app_rank_val = current_rank or 999
            category_avg_rank = sum(category_ranks) / len(category_ranks)
            percentile = 1 - (app_rank_val / max(category_avg_rank * 2, 1))
            final_score = final_score * (0.7 + (0.3 * max(percentile, 0)))

        return {
            "app_id": app_id,
            "momentum_3d": round(mom_3d, 3),
            "momentum_7d": round(mom_7d, 3),
            "momentum_14d": round(mom_14d, 3),
            "momentum_weighted": round(momentum_weighted, 3),
            "consistency_score": consistency,
            "confidence_factor": confidence,
            "absolute_rank_bonus": rank_bonus,
            "review_momentum": review_momentum,
            "raw_score": round(raw_score, 2),
            "final_score": round(final_score, 2),
        }

    def get_top_trending_apps_v2(self, limit: int = 10, category_id: int = None) -> List[Dict]:
        """
        New improved trending algorithm — batch-prefetch version.

        Uses 4 batch queries total (same pattern as trending_compute_service)
        instead of ~11N per-app queries.
        """
        cutoff = datetime.utcnow() - timedelta(days=14)

        # 1. All rankings in last 14 days → group by app_id in Python
        rank_query = (
            self.db.query(Ranking.app_id, Ranking.rank, Ranking.previous_rank, Ranking.recorded_at)
            .filter(Ranking.recorded_at >= cutoff)
        )
        if category_id:
            rank_query = rank_query.filter(Ranking.category_id == category_id)

        rankings_by_app = defaultdict(list)
        for row in rank_query.order_by(Ranking.app_id, Ranking.recorded_at).all():
            rankings_by_app[row.app_id].append({
                "rank": row.rank,
                "previous_rank": row.previous_rank,
                "recorded_at": row.recorded_at,
            })

        app_ids = list(rankings_by_app.keys())
        if not app_ids:
            return []

        # 2. App data for all candidate apps
        app_data_map = {}
        _BATCH = 2000
        for i in range(0, len(app_ids), _BATCH):
            batch = app_ids[i : i + _BATCH]
            for app in (
                self.db.query(App)
                .filter(App.id.in_(batch))
                .all()
            ):
                app_data_map[app.id] = app

        # 3. Review counts (last 7 days)
        review_cutoff = datetime.utcnow() - timedelta(days=7)
        review_count_map = {}
        for i in range(0, len(app_ids), _BATCH):
            batch = app_ids[i : i + _BATCH]
            for row in (
                self.db.query(Review.app_id, func.count(Review.id))
                .filter(Review.app_id.in_(batch), Review.date >= review_cutoff)
                .group_by(Review.app_id)
                .all()
            ):
                review_count_map[row[0]] = row[1]

        # 4. Category ranks for normalization
        category_ids = list({
            a.category_id for a in app_data_map.values() if a.category_id
        })
        category_ranks_map = defaultdict(list)
        if category_ids:
            for i in range(0, len(category_ids), _BATCH):
                batch = category_ids[i : i + _BATCH]
                for row in (
                    self.db.query(App.category_id, App.current_rank)
                    .filter(App.category_id.in_(batch), App.current_rank.isnot(None))
                    .all()
                ):
                    category_ranks_map[row[0]].append(row[1])

        # Score each app using prefetched data (zero per-app queries)
        trending = []
        for app_id in app_ids:
            app = app_data_map.get(app_id)
            if not app:
                continue

            cat_id = app.category_id
            trend_data = self.compute_trend_score_from_prefetch(
                app_id=app_id,
                ranking_history=rankings_by_app.get(app_id, []),
                current_reviews=app.current_reviews,
                current_rank=app.current_rank,
                category_id=cat_id,
                review_count_7d=review_count_map.get(app_id, 0),
                category_ranks=category_ranks_map.get(cat_id) if cat_id else None,
                use_category_norm=True,
            )

            if not trend_data or trend_data["final_score"] <= 0:
                continue

            trending.append({
                "id": app.id,
                "app_id": app.app_id,
                "name": app.name,
                "developer": app.developer,
                "icon_url": app.icon_url,
                "current_rank": app.current_rank,
                "current_rating": app.current_rating,
                "current_reviews": app.current_reviews,
                "trend_score": trend_data["final_score"],
                "momentum_3d": trend_data["momentum_3d"],
                "momentum_7d": trend_data["momentum_7d"],
                "consistency_score": trend_data["consistency_score"],
                "confidence_factor": trend_data["confidence_factor"],
                "absolute_rank_bonus": trend_data["absolute_rank_bonus"],
                "review_momentum": trend_data["review_momentum"],
            })

        trending.sort(key=lambda x: x["trend_score"], reverse=True)
        return trending[:limit]

    def update_keyword_metrics(self) -> None:
        """
        Estimate keyword metrics from available app-keyword data.

        Uses a single GROUP BY query to count app-keyword associations for ALL
        keywords at once (instead of N per-keyword COUNT queries).

          search_volume ≈ app_count × search_volume_per_app
          difficulty    ≈ min(app_count, difficulty_cap)
          trend         ≈ category-based estimate (AI/chat keywords score higher)
        """
        _tmap = TRENDING_CONFIG["trend_velocity_map"]
        _tdef = TRENDING_CONFIG["trend_velocity_default"]
        _svpa = TRENDING_CONFIG["search_volume_per_app"]
        _dcap = TRENDING_CONFIG["difficulty_cap"]

        # Single query: keyword_id → app_count  (replaces N per-keyword COUNTs)
        counts = dict(
            self.db.query(AppKeyword.keyword_id, func.count(AppKeyword.app_id))
            .group_by(AppKeyword.keyword_id)
            .all()
        )

        _BATCH = 500
        offset = 0
        while True:
            batch = (
                self.db.query(Keyword)
                .order_by(Keyword.id)
                .offset(offset)
                .limit(_BATCH)
                .all()
            )
            if not batch:
                break
            for kw in batch:
                if not kw.term:
                    continue
                app_count = counts.get(kw.id, 0)
                kw.search_volume = app_count * _svpa
                kw.difficulty = min(float(app_count), _dcap)
                kw.trend = _tmap.get(kw.term.lower(), _tdef)
            self.db.commit()
            self.db.expire_all()
            offset += _BATCH

    def compute_market_weakness(self, app_id: int) -> List[Dict]:
        """
        Compute per-country negative review ratio for an app.

        negative_review = rating <= 2
        negative_ratio  = negative_reviews / total_reviews

        Countries with < 20 reviews are excluded (noise filter).
        Reviews with null storefront are skipped.
        Results are upserted into AppMarketWeakness and returned sorted
        by negative_ratio descending.
        """
        from app.models.models import AppMarketWeakness

        # Countries with fewer reviews than this are excluded from weak-market analysis.
        MIN_REVIEWS = ENGINE_CONFIG["market_weakness_min_reviews"]

        reviews = (
            self.db.query(Review)
            .filter(
                and_(
                    Review.app_id == app_id,
                    Review.storefront.isnot(None),
                    Review.rating.isnot(None),
                )
            )
            .all()
        )

        country_stats: Dict[str, Dict] = {}
        for review in reviews:
            country = review.storefront.upper()
            if country not in country_stats:
                country_stats[country] = {"total": 0, "negative": 0, "rating_sum": 0}
            country_stats[country]["total"] += 1
            country_stats[country]["rating_sum"] += review.rating
            if review.rating <= 2:
                country_stats[country]["negative"] += 1

        results = []
        for country, stats in country_stats.items():
            if stats["total"] < MIN_REVIEWS:
                continue
            negative_ratio = stats["negative"] / stats["total"]
            avg_rating = stats["rating_sum"] / stats["total"]
            results.append({
                "country": country,
                "total_reviews": stats["total"],
                "negative_reviews": stats["negative"],
                "average_rating": round(avg_rating, 2),
                "negative_ratio": round(negative_ratio, 4),
            })

        results.sort(key=lambda x: x["negative_ratio"], reverse=True)

        for stat in results:
            existing = (
                self.db.query(AppMarketWeakness)
                .filter(
                    and_(
                        AppMarketWeakness.app_id == app_id,
                        AppMarketWeakness.country == stat["country"],
                    )
                )
                .first()
            )
            if existing:
                existing.total_reviews = stat["total_reviews"]
                existing.negative_reviews = stat["negative_reviews"]
                existing.average_rating = stat["average_rating"]
                existing.negative_ratio = stat["negative_ratio"]
                existing.computed_at = datetime.utcnow()
            else:
                weakness = AppMarketWeakness(
                    app_id=app_id,
                    country=stat["country"],
                    total_reviews=stat["total_reviews"],
                    negative_reviews=stat["negative_reviews"],
                    average_rating=stat["average_rating"],
                    negative_ratio=stat["negative_ratio"],
                )
                self.db.add(weakness)

        if results:
            self.db.commit()

        return results

    def calculate_keyword_signal_confidence(self, keyword: Keyword) -> float:
        """
        Calculate signal confidence score (0-1) for a keyword based on data quality.
        
        Factors:
        - completeness: how many metrics are present
        - freshness: how recently the data was updated
        - source reliability: observed vs estimated signals
        """
        completeness = self._calculate_completeness_factor(keyword)
        freshness = self._calculate_freshness_factor(keyword)
        reliability = self._calculate_source_reliability_factor(keyword)
        
        confidence = completeness * freshness * reliability
        return max(0.0, min(1.0, confidence))

    def _calculate_completeness_factor(self, keyword: Keyword) -> float:
        """
        Calculate completeness factor based on presence of key metrics.
        
        Returns 0-1 score where:
        - All metrics present = 1.0
        - Some metrics missing = proportionally less
        """
        metrics_present = 0
        total_metrics = SIGNAL_CONFIDENCE_CONFIG["total_metrics"]

        if keyword.search_volume and keyword.search_volume > 0:
            metrics_present += 1
        if keyword.difficulty and keyword.difficulty > 0:
            metrics_present += 1
        if keyword.trend_score and keyword.trend_score > 0:
            metrics_present += 1
        if keyword.trend_growth is not None and keyword.trend_growth != 0:
            metrics_present += 1
        if keyword.last_enriched is not None:
            metrics_present += 1

        return metrics_present / total_metrics

    def _calculate_freshness_factor(self, keyword: Keyword) -> float:
        """
        Calculate freshness factor based on last update time.
        
        Returns:
        - <7 days old = 1.0
        - <30 days = 0.85
        - <90 days = 0.65
        - older = 0.4
        """
        if not keyword.last_enriched:
            if not keyword.last_updated:
                return SIGNAL_CONFIDENCE_CONFIG["freshness_stale"]
            age = datetime.utcnow() - keyword.last_updated
        else:
            age = datetime.utcnow() - keyword.last_enriched
        
        days_old = age.days
        _bands = SIGNAL_CONFIDENCE_CONFIG["freshness_bands_days"]

        if days_old < 7:
            return _bands[7]
        elif days_old < 30:
            return _bands[30]
        elif days_old < 90:
            return _bands[90]
        else:
            return SIGNAL_CONFIDENCE_CONFIG["freshness_stale"]

    def _calculate_source_reliability_factor(self, keyword: Keyword) -> float:
        """
        Calculate source reliability factor based on data source.
        """
        _rs = SIGNAL_CONFIDENCE_CONFIG["reliability_by_status"]
        _rt = SIGNAL_CONFIDENCE_CONFIG["reliability_by_tier"]
        _rd = SIGNAL_CONFIDENCE_CONFIG["reliability_default"]
        if keyword.status == KeywordStatus.ENRICHED.value:
            return _rs["enriched"]
        elif keyword.status == KeywordStatus.RAW.value:
            return _rs["raw"]
        elif keyword.quality_tier == 'A':
            return _rt["A"]
        elif keyword.quality_tier == 'B':
            return _rt["B"]
        elif keyword.quality_tier == 'C':
            return _rt["C"]
        return _rd

    def get_keyword_opportunities(
        self,
        min_difficulty: float = 0,
        max_difficulty: float = 60
    ) -> List[Dict]:
        keywords = (
            self.db.query(Keyword)
            .filter(
                and_(
                    Keyword.difficulty >= min_difficulty,
                    Keyword.difficulty <= max_difficulty
                )
            )
            .order_by(Keyword.trend.desc())
            .limit(50)
            .all()
        )

        opportunities = []
        for kw in keywords:
            app_count = (
                self.db.query(AppKeyword)
                .filter(AppKeyword.keyword_id == kw.id)
                .count()
            )

            search_volume = kw.search_volume or 0
            difficulty = kw.difficulty or 0
            trend = kw.trend or 0

            _lw = OPPORTUNITY_CONFIG["legacy_weights"]
            base_opportunity_score = (
                (100 - difficulty) * _lw["difficulty"]
                + trend            * _lw["trend"]
                + (search_volume / 1000) * _lw["search_volume_scale"]
                + (1 / (app_count + 1)) * _lw["competition_factor"]
            )

            confidence = self.calculate_keyword_signal_confidence(kw)
            adjusted_opportunity_score = base_opportunity_score * confidence

            opportunities.append({
                "keyword": kw.term,
                "search_volume": search_volume,
                "difficulty": difficulty,
                "trend": trend,
                "opportunity_score": round(adjusted_opportunity_score, 2),
                "base_opportunity_score": round(base_opportunity_score, 2),
                "signal_confidence": round(confidence, 2),
                "current_apps": app_count
            })

        opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return opportunities[:20]

    def get_fresh_risers(
        self,
        mode: str = "fresh_risers",
        limit: int = 20,
        category_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get fresh riser apps - newly released apps showing early traction.

        Batch-prefetch version: 3 queries total instead of ~4N per-app queries.

        Modes:
        - fresh_risers: Default - apps with best fresh_riser_score
        - newest: Most recently released apps
        - hidden_gems: Apps with high momentum but lower visibility
        """
        import logging as _logging
        _log = _logging.getLogger(__name__)

        now = datetime.now(timezone.utc)
        cutoff_7_days = now - timedelta(days=7)
        _elig = FRESH_RISERS_CONFIG["eligibility"]
        max_age = _elig["max_age_days"]
        min_reviews = _elig["min_reviews"]
        min_snapshots = _elig["min_ranking_snapshots"]
        max_rank = _elig["max_rank"]
        fallback_age = _elig.get("fallback_age_days", 14)

        # ── Pre-filter candidates in SQL (eliminates 90%+ of apps) ─────────
        age_cutoff = now - timedelta(days=max_age)
        base_query = (
            self.db.query(App)
            .filter(
                App.category_id.isnot(None),
                App.current_reviews >= min_reviews,
                func.coalesce(App.current_rank, 0) <= max_rank,
                func.coalesce(App.release_date, App.created_at) >= age_cutoff,
            )
        )
        if category_id:
            base_query = base_query.filter(App.category_id == category_id)

        candidates = base_query.all()
        if not candidates:
            return []

        candidate_ids = [a.id for a in candidates]

        # ── Batch prefetch 1: ranking counts per app (last 7 days) ─────────
        ranking_counts = dict(
            self.db.query(Ranking.app_id, func.count(Ranking.id))
            .filter(Ranking.app_id.in_(candidate_ids), Ranking.recorded_at >= cutoff_7_days)
            .group_by(Ranking.app_id)
            .all()
        )

        # ── Batch prefetch 2: oldest ranking per app (last 7 days) for momentum
        oldest_rank_sub = (
            self.db.query(
                Ranking.app_id,
                func.min(Ranking.recorded_at).label("min_ts"),
            )
            .filter(Ranking.app_id.in_(candidate_ids), Ranking.recorded_at >= cutoff_7_days)
            .group_by(Ranking.app_id)
            .subquery()
        )
        oldest_ranks = {}
        for row in (
            self.db.query(Ranking.app_id, Ranking.rank)
            .join(
                oldest_rank_sub,
                and_(
                    Ranking.app_id == oldest_rank_sub.c.app_id,
                    Ranking.recorded_at == oldest_rank_sub.c.min_ts,
                ),
            )
            .all()
        ):
            oldest_ranks[row.app_id] = row.rank

        # ── Batch prefetch 3: category avg reviews ─────────────────────────
        cat_ids = list({a.category_id for a in candidates if a.category_id})
        cat_avg_reviews = {}
        if cat_ids:
            for row in (
                self.db.query(App.category_id, func.avg(App.current_reviews))
                .filter(App.category_id.in_(cat_ids), App.current_reviews.isnot(None))
                .group_by(App.category_id)
                .all()
            ):
                cat_avg_reviews[row[0]] = row[1]

        # ── Batch prefetch 4: category names ───────────────────────────────
        cat_names = {}
        if cat_ids:
            for row in self.db.query(Category.id, Category.name).filter(Category.id.in_(cat_ids)).all():
                cat_names[row.id] = row.name

        # ── Score each candidate using prefetched data (zero per-app queries)
        fresh_risers = []
        for app in candidates:
            try:
                # Eligibility check (inline — uses prefetched ranking_counts)
                def _to_aware(dt):
                    if dt is None:
                        return None
                    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

                release_date = _to_aware(app.release_date)
                created_at = _to_aware(app.created_at)

                if not release_date:
                    if created_at and (now - created_at).days <= fallback_age:
                        release_date = created_at
                    else:
                        continue
                age_days = (now - release_date).days
                if age_days > max_age:
                    continue

                ranking_count = ranking_counts.get(app.id, 0)
                if ranking_count < min_snapshots:
                    continue

                reviews_count = app.current_reviews or 0

                # Scores (inline — uses prefetched data)
                freshness_score = self._calculate_freshness_score(age_days)
                review_traction_score = self._calculate_review_traction_score(reviews_count, age_days)
                rank_quality_score = self._calculate_rank_quality_score(app.current_rank)

                # Momentum from prefetched oldest rank
                current_rank = app.current_rank
                if not current_rank:
                    momentum_score = 10.0
                else:
                    oldest_r = oldest_ranks.get(app.id)
                    if oldest_r is None:
                        momentum_score = FRESH_RISERS_CONFIG["momentum_no_history"]
                    else:
                        momentum = oldest_r - current_rank
                        _mbands = FRESH_RISERS_CONFIG["momentum_bands"]
                        if momentum >= 100:
                            momentum_score = _mbands[100]
                        elif momentum >= 50:
                            momentum_score = _mbands[50]
                        elif momentum >= 20:
                            momentum_score = _mbands[20]
                        else:
                            momentum_score = FRESH_RISERS_CONFIG["momentum_floor"]

                # Niche viability from prefetched category avg
                cat_id = app.category_id
                if not cat_id:
                    niche_viability_score = FRESH_RISERS_CONFIG["niche_no_category"]
                else:
                    avg_rev = cat_avg_reviews.get(cat_id)
                    if not avg_rev:
                        niche_viability_score = FRESH_RISERS_CONFIG["niche_default"]
                    else:
                        _nbands = FRESH_RISERS_CONFIG["niche_avg_reviews_bands"]
                        if avg_rev < 1_000:
                            niche_viability_score = _nbands[1_000]
                        elif avg_rev < 5_000:
                            niche_viability_score = _nbands[5_000]
                        elif avg_rev < 20_000:
                            niche_viability_score = _nbands[20_000]
                        else:
                            niche_viability_score = FRESH_RISERS_CONFIG["niche_floor"]

                _sw = FRESH_RISERS_CONFIG["score_weights"]
                fresh_riser_score = (
                    freshness_score       * _sw["freshness"] +
                    review_traction_score * _sw["review_traction"] +
                    rank_quality_score    * _sw["rank_quality"] +
                    momentum_score        * _sw["momentum"] +
                    niche_viability_score * _sw["niche_viability"]
                )

                if mode == "hidden_gems":
                    _hw = FRESH_RISERS_CONFIG["hidden_gems_weights"]
                    final_score = (
                        momentum_score        * _hw["momentum"] +
                        niche_viability_score * _hw["niche_viability"] +
                        rank_quality_score    * _hw["rank_quality"] +
                        review_traction_score * _hw["review_traction"]
                    )
                elif mode == "newest":
                    final_score = freshness_score
                else:
                    final_score = fresh_riser_score

                category_name = cat_names.get(cat_id) or app.primary_category

                fresh_risers.append({
                    "app_id": app.id,
                    "app_name": app.name,
                    "developer": app.developer,
                    "release_date": app.release_date.isoformat() if app.release_date else None,
                    "current_rank": app.current_rank,
                    "current_reviews": reviews_count,
                    "category": category_name,
                    "fresh_riser_score": round(final_score, 2),
                    "freshness_score": freshness_score,
                    "review_traction_score": review_traction_score,
                    "rank_quality_score": rank_quality_score,
                    "momentum_score": momentum_score,
                    "niche_viability_score": niche_viability_score,
                    "ranking_snapshots_count": ranking_count,
                    "age_days": age_days,
                })
            except Exception as exc:
                _log.warning(
                    "[fresh_risers] Skipping app id=%s name=%r: %s",
                    getattr(app, "id", "?"), getattr(app, "name", "?"), exc
                )
                continue

        fresh_risers.sort(key=lambda x: x["fresh_riser_score"], reverse=True)
        return fresh_risers[:limit]

    def _check_fresh_riser_eligibility(
        self,
        app: App,
        cutoff_7_days: datetime,
        cutoff_14_days: datetime
    ) -> Dict:
        """Check if app is eligible for fresh risers."""
        now = datetime.now(timezone.utc)

        def _to_aware(dt):
            """Ensure dt is timezone-aware UTC; returns None if dt is None."""
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        release_date = _to_aware(app.release_date)
        created_at = _to_aware(app.created_at)

        if not release_date:
            if created_at:
                age = now - created_at
                age_days = age.days
                if age_days <= FRESH_RISERS_CONFIG["eligibility"]["fallback_age_days"]:
                    release_date = created_at
                else:
                    return {"eligible": False, "reason": "no_valid_release_date"}
            else:
                return {"eligible": False, "reason": "no_release_date"}
        else:
            age = now - release_date
            age_days = age.days

        if age_days > FRESH_RISERS_CONFIG["eligibility"]["max_age_days"]:
            return {"eligible": False, "reason": "too_old"}

        reviews_count = app.current_reviews or 0
        if reviews_count < FRESH_RISERS_CONFIG["eligibility"]["min_reviews"]:
            return {"eligible": False, "reason": "insufficient_reviews"}

        ranking_count = (
            self.db.query(Ranking)
            .filter(Ranking.app_id == app.id)
            .filter(Ranking.recorded_at >= cutoff_7_days)
            .count()
        )

        if ranking_count < FRESH_RISERS_CONFIG["eligibility"]["min_ranking_snapshots"]:
            return {"eligible": False, "reason": "insufficient_ranking_history"}

        if app.current_rank and app.current_rank > FRESH_RISERS_CONFIG["eligibility"]["max_rank"]:
            return {"eligible": False, "reason": "rank_too_low"}

        return {
            "eligible": True,
            "age_days": age_days,
            "ranking_count": ranking_count,
            "reviews_count": reviews_count,
        }

    def _calculate_fresh_riser_scores(
        self,
        app: App,
        eligibility: Dict,
        cutoff_7_days: datetime
    ) -> Dict:
        """Calculate all fresh riser score components."""
        age_days = eligibility["age_days"]
        
        freshness_score = self._calculate_freshness_score(age_days)
        
        review_traction_score = self._calculate_review_traction_score(
            eligibility["reviews_count"], age_days
        )
        
        rank_quality_score = self._calculate_rank_quality_score(app.current_rank)
        
        momentum_score = self._calculate_momentum_score(app.id, cutoff_7_days, app.current_rank)
        
        niche_viability_score = self._calculate_niche_viability_score(app.category_id)
        
        fresh_riser_score = (
            freshness_score        * FRESH_RISERS_CONFIG["score_weights"]["freshness"] +
            review_traction_score  * FRESH_RISERS_CONFIG["score_weights"]["review_traction"] +
            rank_quality_score     * FRESH_RISERS_CONFIG["score_weights"]["rank_quality"] +
            momentum_score         * FRESH_RISERS_CONFIG["score_weights"]["momentum"] +
            niche_viability_score  * FRESH_RISERS_CONFIG["score_weights"]["niche_viability"]
        )

        return {
            "fresh_riser_score": fresh_riser_score,
            "freshness_score": freshness_score,
            "review_traction_score": review_traction_score,
            "rank_quality_score": rank_quality_score,
            "momentum_score": momentum_score,
            "niche_viability_score": niche_viability_score,
        }

    def _calculate_freshness_score(self, age_days: int) -> float:
        """Calculate freshness score based on app age."""
        _bands = FRESH_RISERS_CONFIG["freshness_bands"]
        _floor = 0.0
        if age_days <= 2:
            return _bands[2]
        elif age_days <= 4:
            return _bands[4]
        elif age_days <= 7:
            return _bands[7]
        else:
            return _floor

    def _calculate_review_traction_score(self, reviews_count: int, age_days: int) -> float:
        """Calculate review traction score based on velocity."""
        if age_days < 1:
            age_days = 1
        velocity = reviews_count / age_days
        _bands = FRESH_RISERS_CONFIG["review_velocity_bands"]
        _floor = FRESH_RISERS_CONFIG["review_velocity_floor"]
        if velocity >= 5:
            return _bands[5]
        elif velocity >= 2:
            return _bands[2]
        elif velocity >= 1:
            return _bands[1]
        else:
            return _floor

    def _calculate_rank_quality_score(self, current_rank: Optional[int]) -> float:
        """Calculate rank quality score based on best rank."""
        if not current_rank:
            return FRESH_RISERS_CONFIG["rank_quality_no_rank"]
        _bands = FRESH_RISERS_CONFIG["rank_quality_bands"]
        _floor = FRESH_RISERS_CONFIG["rank_quality_floor"]
        if current_rank <= 10:
            return _bands[10]
        elif current_rank <= 50:
            return _bands[50]
        elif current_rank <= 100:
            return _bands[100]
        elif current_rank <= 300:
            return _bands[300]
        else:
            return _floor

    def _calculate_momentum_score(
        self,
        app_id: int,
        cutoff_7_days: datetime,
        current_rank: Optional[int]
    ) -> float:
        """Calculate momentum score based on ranking improvement."""
        if not current_rank:
            return 10.0
        
        oldest_rank = (
            self.db.query(Ranking)
            .filter(Ranking.app_id == app_id)
            .filter(Ranking.recorded_at >= cutoff_7_days)
            .order_by(Ranking.recorded_at.asc())
            .first()
        )
        
        if not oldest_rank:
            return FRESH_RISERS_CONFIG["momentum_no_history"]

        rank_7_days_ago = oldest_rank.rank if oldest_rank.rank else current_rank
        momentum = rank_7_days_ago - current_rank
        _bands = FRESH_RISERS_CONFIG["momentum_bands"]
        _floor = FRESH_RISERS_CONFIG["momentum_floor"]
        if momentum >= 100:
            return _bands[100]
        elif momentum >= 50:
            return _bands[50]
        elif momentum >= 20:
            return _bands[20]
        else:
            return _floor

    def _calculate_niche_viability_score(self, category_id: Optional[int]) -> float:
        """Calculate niche viability based on category competition."""
        if not category_id:
            return FRESH_RISERS_CONFIG["niche_no_category"]

        avg_reviews = (
            self.db.query(func.avg(App.current_reviews))
            .filter(App.category_id == category_id)
            .filter(App.current_reviews.isnot(None))
            .scalar()
        )

        if not avg_reviews:
            return FRESH_RISERS_CONFIG["niche_default"]

        _bands = FRESH_RISERS_CONFIG["niche_avg_reviews_bands"]
        _floor = FRESH_RISERS_CONFIG["niche_floor"]
        if avg_reviews < 1_000:
            return _bands[1_000]
        elif avg_reviews < 5_000:
            return _bands[5_000]
        elif avg_reviews < 20_000:
            return _bands[20_000]
        else:
            return _floor

    def _is_weak_keyword(self, keyword: str) -> bool:
        """Check if keyword is weak (stopword or generic adjective)."""
        kw_lower = keyword.lower().strip()
        if not kw_lower or len(kw_lower) <= 1:
            return True
        if kw_lower in _STOPWORDS:
            return True
        if kw_lower in _WEAK_KEYWORDS:
            return True
        return False

    def _extract_phrases(
        self,
        text: str,
        min_words: int = None,
        max_words: int = None,
    ) -> List[str]:
        """Extract multi-word phrases from text (title/subtitle)."""
        if min_words is None:
            min_words = ENGINE_CONFIG["phrase_min_words"]
        if max_words is None:
            max_words = ENGINE_CONFIG["phrase_max_words"]
        if not text:
            return []
        words = text.split()
        phrases = []
        for n in range(min_words, max_words + 1):
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i+n]).lower().strip()
                if phrase:
                    phrase_words = phrase.split()
                    if any(self._is_weak_keyword(w) for w in phrase_words):
                        continue
                    phrases.append(phrase)
        return phrases

    def select_primary_keyword(self, app_id: int) -> Tuple[str, str]:
        """
        Select the best primary keyword for an app using 4-tier selection logic.
        
        Returns:
            Tuple of (primary_keyword, selection_method)
        """
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return "app", "fallback_empty"

        app_text = f"{app.name or ''} {app.subtitle or ''}".strip()

        # Tier 1: App Keyword Intelligence - select keyword with highest traffic_score
        intelligence = (
            self.db.query(AppKeywordIntelligence, Keyword)
            .join(Keyword, Keyword.id == AppKeywordIntelligence.keyword_id)
            .filter(AppKeywordIntelligence.app_id == app_id)
            .order_by(AppKeywordIntelligence.traffic_score.desc())
            .first()
        )
        if intelligence:
            aki, kw = intelligence
            if kw.term and not self._is_weak_keyword(kw.term):
                return kw.term, "intelligence"

        # Tier 2: Discovered Keywords - select best by opportunity_score
        discovered = (
            self.db.query(AppDiscoveredKeyword)
            .filter(AppDiscoveredKeyword.app_id == app_id)
            .filter(AppDiscoveredKeyword.opportunity_score > 0)
            .order_by(AppDiscoveredKeyword.opportunity_score.desc())
            .first()
        )
        if discovered and discovered.keyword:
            if not self._is_weak_keyword(discovered.keyword):
                return discovered.keyword, "discovered"

        # Tier 3: Extract Title/Subtitle Phrases (2-3 words)
        phrases = self._extract_phrases(app_text, min_words=2, max_words=3)
        if phrases:
            scored_phrases = []
            for phrase in phrases:
                kw_obj = self.db.query(Keyword).filter(Keyword.term == phrase).first()
                if kw_obj and kw_obj.opportunity_score:
                    scored_phrases.append((phrase, kw_obj.opportunity_score))
                else:
                    scored_phrases.append((phrase, 10.0))
            scored_phrases.sort(key=lambda x: x[1], reverse=True)
            if scored_phrases:
                return scored_phrases[0][0], "title_phrase"

        # Tier 4: Smart Fallback - extract best phrase using stopword filtering
        words = app_text.split()
        valid_words = [w for w in words if not self._is_weak_keyword(w)]
        
        if len(valid_words) >= 2:
            for i in range(len(valid_words) - 1):
                phrase = f"{valid_words[i]} {valid_words[i+1]}".lower()
                return phrase, "fallback_phrase"
        
        if valid_words:
            return valid_words[0].lower(), "fallback_single"

        return "app", "fallback_empty"
