from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.models import App, Ranking, Review, Keyword, AppKeyword, Opportunity, Category, AppKeywordIntelligence, AppDiscoveredKeyword, KeywordStatus
from app.scoring.weights import SCORING_WEIGHTS

# ---------------------------------------------------------------------------
# Big-brand exclusion — developer names (normalised to lowercase substrings)
# ---------------------------------------------------------------------------

_BIG_BRAND_DEVELOPERS = frozenset({
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
    "duolingo",         # highly entrenched language app
    "bumble inc",
    "match group",      # Tinder, Hinge, OkCupid parent
    "unity technologies",
    "epic games",
    "activision publishing",
    "electronic arts",
    "zynga",
    "king",             # Candy Crush parent
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
})

# App name substrings that flag a big-brand product regardless of developer field
_BIG_BRAND_APP_KEYWORDS = (
    "chatgpt", "dall-e", "dall·e", "openai",
    "gemini", "google one", "google docs", "google sheets", "google drive",
    "youtube", "gmail", "chrome", "google maps", "google photos",
    "instagram", "facebook", "whatsapp", "messenger", "threads",
    "grok",
    "microsoft copilot", "bing ", "bing chat", "microsoft 365",
    "microsoft teams", "outlook", "onedrive", "xbox",
    "claude ",            # Anthropic
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
    "shazam",            # Apple subsidiary
    "garageband",        # Apple
    "iwork", "pages for", "numbers for", "keynote for",
)

# ---------------------------------------------------------------------------
# Market dominance thresholds — entrenched incumbents regardless of brand
# ---------------------------------------------------------------------------

_DOMINANCE_REVIEW_HARD = 500_000   # absolute behemoth
_DOMINANCE_REVIEW_RATED = 100_000  # entrenched with high rating
_DOMINANCE_RATED_FLOOR = 4.5       # "entrenched + beloved"
_DOMINANCE_TOP_RANK = 3            # chart dominator rank threshold
_DOMINANCE_TOP_REVIEWS = 50_000    # chart dominator review threshold


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

        competition_boost = min(app_count * 2, 30)
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

        return min(recent_count * 5, 100)

    def calculate_ai_potential(self, app_id: int, app_name: str, description: str = "") -> float:
        ai_keywords = [
            "ai", "chat", "gpt", "llm", "assistant", "bot", "smart", "automation",
            "generate", "create", "write", "image", "voice", "transcribe",
            "translate", "summarize", "analyze", "predict", "learn"
        ]

        text = f"{app_name or ''} {description or ''}".lower()
        matches = sum(1 for kw in ai_keywords if kw in text)

        base_score = (matches / len(ai_keywords)) * 100

        if matches > 0:
            return min(base_score + 20, 100)

        app = self.db.query(App).filter(App.id == app_id).first()
        if app and app.category_id:
            ai_categories = [1, 2, 3]
            if app.category_id in ai_categories:
                return 60.0

        return 30.0

    def calculate_success_probability(
        self,
        rank_velocity: float,
        review_growth: float,
        competition_score: float,
        ai_potential: float,
        category_growth: float
    ) -> float:
        rank_factor = min(rank_velocity * 10, 30) if rank_velocity > 0 else 10
        review_factor = min(review_growth * 0.5, 25)
        competition_factor = (100 - competition_score) * 0.2
        ai_factor = ai_potential * 0.15
        category_factor = category_growth * 0.1

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

        trend_score = min(
            (rank_velocity * 20 + review_growth * 0.3 + category_growth * 0.4),
            100
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

        if success_prob > 70:
            recommendations.append(f"High-potential app! {app_name} shows strong growth metrics.")
        elif success_prob > 50:
            recommendations.append(f"Moderate opportunity. {app_name} has decent metrics.")
        else:
            recommendations.append("Low immediate potential. Consider different keywords.")

        if trend_score > 60:
            recommendations.append("Strong upward trend - enter soon!")

        if competition < 40:
            recommendations.append("Low competition - good keyword targeting opportunity.")
        elif competition > 70:
            recommendations.append("High competition - need strong differentiation.")

        if ai_potential > 60:
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
            if len(brand) > 5 and brand in dev:
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
        self, app: App, competition_score: float
    ) -> Tuple[float, Dict]:
        """
        Score how feasible it is for an indie developer to win in this space.

        Components (100 pts total):
          review_pts      (25) — fewer reviews = easier to enter
          competition_pts (25) — lower keyword difficulty = easier ASO
          gap_pts         (20) — feature-gap requests = clear differentiation path
          rating_pts      (15) — lower avg rating = unhappy users to win over
          rank_pts        (15) — rank > 20 = not locked out of charts
        """
        from app.models.models import FeatureGap

        reviews = app.current_reviews or 0
        rating = app.current_rating or 3.0
        rank = app.current_rank or 999

        # 1. Review scarcity
        if reviews < 500:
            review_pts = 25.0
        elif reviews < 5_000:
            review_pts = 20.0
        elif reviews < 20_000:
            review_pts = 12.0
        elif reviews < 50_000:
            review_pts = 6.0
        elif reviews < 100_000:
            review_pts = 2.0
        else:
            review_pts = 0.0

        # 2. Low keyword competition
        competition_pts = max(0.0, (100.0 - competition_score) / 4.0)

        # 3. Feature gap signals
        gap_count = (
            self.db.query(FeatureGap)
            .filter(FeatureGap.app_id == app.id)
            .count()
        )
        gap_pts = min(gap_count * 4.0, 20.0)

        # 4. Rating weakness — lower rating means more room to win
        if rating < 2.0:
            rating_pts = 15.0
        elif rating < 3.0:
            rating_pts = 12.0
        elif rating < 3.5:
            rating_pts = 8.0
        elif rating < 4.0:
            rating_pts = 4.0
        else:
            rating_pts = 0.0

        # 5. Rank accessibility — not locked out of charts
        if rank > 100:
            rank_pts = 15.0
        elif rank > 50:
            rank_pts = 10.0
        elif rank > 20:
            rank_pts = 5.0
        else:
            rank_pts = 0.0

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

        if feasibility_score >= 65:
            parts.append(f"High winnability — realistic indie opportunity in the '{app_name}' niche.")
        elif feasibility_score >= 45:
            parts.append(f"Moderate winnability — competition is manageable around '{app_name}'.")
        else:
            parts.append(f"Tough space — '{app_name}' category is crowded but micro-niches exist.")

        gap_count = feasibility_details.get("gap_count", 0)
        if gap_count >= 3:
            parts.append(f"{gap_count} feature gaps reported by users — clear differentiation path.")
        if feasibility_details.get("rating_pts", 0) >= 8:
            parts.append("Users are unhappy with existing options — quality gap to exploit.")
        if feasibility_details.get("review_pts", 0) >= 20:
            parts.append("Low review count — early-mover advantage still available.")
        if feasibility_details.get("competition_pts", 0) >= 18:
            parts.append("Low keyword competition — strong ASO opportunity.")

        return " ".join(parts[:3])

    # ------------------------------------------------------------------
    # Opportunity of the Day
    # ------------------------------------------------------------------

    def generate_opportunity_of_day(self) -> Optional[Dict]:
        """
        Generate the Opportunity of the Day by scoring all tracked apps.
        
        Previous naive implementation used `app.name.split()[0].lower()` to extract
        the primary keyword, which is flawed because:
        - First token is often a brand name (e.g., "Spotify", "Instagram")
        - Adjectives like "Best", "Easy", "Smart" provide no ASO value
        - Single tokens miss multi-word keyword opportunities
        - No consideration of actual keyword performance data
        
        The new `select_primary_keyword()` method uses 4-tier selection:
        1. AppKeywordIntelligence - highest traffic_score from extracted keywords
        2. AppDiscoveredKeyword - highest opportunity_score from discovery
        3. Title/Subtitle phrases - 2-3 word phrases from app metadata
        4. Smart fallback - stopword-filtered phrase extraction
        """
        apps = self.db.query(App).filter(App.current_rank.isnot(None)).all()

        if not apps:
            return None

        scored = []

        for app in apps:
            # Hard exclusion: major brand developer or product name
            excluded, _excl_reason = self._is_excluded_big_brand(app)
            if excluded:
                continue

            # Hard exclusion: entrenched market incumbent
            dominated, _dom_reason = self._is_dominated_market(app)
            if dominated:
                continue

            primary_keyword, _ = self.select_primary_keyword(app.id)
            competition_score = self.calculate_keyword_competition(primary_keyword)
            ai_potential = self.calculate_ai_potential(app.id, app.name, app.description or "")

            # Attractiveness (45%) — market size + demand signals
            rank_score = max(0.0, 100.0 - (app.current_rank * 2)) if app.current_rank else 0.0
            rating_score = (app.current_rating or 0.0) * 20.0
            attractiveness = min(
                (rank_score * 0.45) +
                (rating_score * 0.30) +
                ((100.0 - competition_score) * 0.15) +
                (ai_potential * 0.10),
                100.0,
            )

            # Feasibility / Winnability (55%)
            feasibility, feasibility_details = self.calculate_feasibility_score(app, competition_score)

            combined = attractiveness * 0.45 + feasibility * 0.55

            category_name = "general"
            if app.category_id:
                category_obj = self.db.query(Category).filter(Category.id == app.category_id).first()
                if category_obj and category_obj.name:
                    category_name = category_obj.name

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
                "rank_velocity": round(self.calculate_rank_velocity(app.id), 2),
                "review_growth": round(self.calculate_review_growth(app.id), 2),
                "rating_velocity": round(self.calculate_rating_velocity(app.id), 2),
                "category_growth": round(self.calculate_category_growth(app.category_id), 2) if app.category_id else 0.0,
                "category": category_name,
                "recommendation": self._generate_winnability_recommendation(
                    app.name,
                    feasibility,
                    feasibility_details,
                    attractiveness,
                ),
            })

        if not scored:
            return None

        scored.sort(key=lambda x: x["success_probability"], reverse=True)
        return scored[0]

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
        history_3d = self._get_ranking_history(app_id, days=3)
        history_7d = self._get_ranking_history(app_id, days=7)
        history_14d = self._get_ranking_history(app_id, days=14)

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

        momentum_weighted = (mom_3d * 0.2) + (mom_7d * 0.35) + (mom_14d * 0.45)

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
        if best_rank <= 5:
            base_bonus = 20.0
        elif best_rank <= 10:
            base_bonus = 15.0
        elif best_rank <= 25:
            base_bonus = 10.0
        elif best_rank <= 50:
            base_bonus = 5.0
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
        
        if base_reviews < 100:
            dampen_factor = 0.3
        elif base_reviews < 1000:
            dampen_factor = 0.6
        elif base_reviews < 10000:
            dampen_factor = 0.85
        else:
            dampen_factor = 1.0

        bounded_score = review_growth_7d * dampen_factor
        
        return round(min(bounded_score, 20), 2)

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

        # Normalize momentum to 0-60 range (max ~20 pos/day → 60)
        momentum_normalized = min(momentum["momentum_weighted"] * 3, 60)
        
        # Normalize consistency to 0-15 range
        consistency_normalized = consistency * 0.15
        
        # Rank bonus already 0-20
        rank_bonus_normalized = rank_bonus
        
        # Normalize review momentum to 0-10 range
        review_normalized = review_momentum * 0.5

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

    def get_top_trending_apps_v2(self, limit: int = 10, category_id: int = None) -> List[Dict]:
        """
        New improved trending algorithm.
        
        Addresses:
        - Multi-window momentum (3d, 7d, 14d)
        - Confidence penalty for sparse data
        - Consistency bonus for sustained movers
        - Absolute rank bonus for strong positions
        - Bounded review growth (tiny apps don't dominate)
        - Category normalization
        """
        cutoff = datetime.utcnow() - timedelta(days=14)
        
        query = (
            self.db.query(Ranking.app_id)
            .filter(Ranking.recorded_at >= cutoff)
            .group_by(Ranking.app_id)
        )
        
        if category_id:
            query = query.filter(Ranking.category_id == category_id)
        
        app_ids = [r[0] for r in query.all()]
        
        trending = []
        for app_id in app_ids:
            app = self.db.query(App).filter(App.id == app_id).first()
            if not app:
                continue

            trend_data = self.compute_trend_score(app_id, use_category_norm=True)
            
            if trend_data["final_score"] <= 0:
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

        The iTunes Search API does not expose search-volume or difficulty figures,
        so all keywords are saved with 0 values by default.  This method derives
        reasonable estimates so dashboard charts and opportunity scores are useful:

          search_volume ≈ app_count × 850   (more ranked apps → higher search volume)
          difficulty    ≈ min(app_count, 60) (caps at 60 so keywords remain visible
                                              in the default max_difficulty=60 view)
          trend         ≈ category-based estimate (AI/chat keywords score higher)
        """
        TREND_MAP = {
            "ai": 8.5, "gpt": 8.0, "chat": 7.5, "game": 6.5, "gaming": 6.5,
            "fitness": 5.5, "health": 5.5, "productivity": 5.0, "social": 5.0,
            "finance": 4.5, "education": 4.5, "music": 4.0, "travel": 3.5,
        }
        keywords = self.db.query(Keyword).all()
        for kw in keywords:
            if not kw.term:
                continue
            app_count = (
                self.db.query(AppKeyword)
                .filter(AppKeyword.keyword_id == kw.id)
                .count()
            )
            kw.search_volume = app_count * 850
            kw.difficulty = min(float(app_count), 60.0)
            kw.trend = TREND_MAP.get(kw.term.lower(), 3.0)
        self.db.commit()

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

        MIN_REVIEWS = 20

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
        total_metrics = 5
        
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
                return 0.4
            age = datetime.utcnow() - keyword.last_updated
        else:
            age = datetime.utcnow() - keyword.last_enriched
        
        days_old = age.days
        
        if days_old < 7:
            return 1.0
        elif days_old < 30:
            return 0.85
        elif days_old < 90:
            return 0.65
        else:
            return 0.4

    def _calculate_source_reliability_factor(self, keyword: Keyword) -> float:
        """
        Calculate source reliability factor based on data source.
        
        Returns:
        - Observed/real data = 1.0
        - Unknown source = 0.5
        """
        if keyword.status == KeywordStatus.ENRICHED.value:
            return 1.0
        elif keyword.status == KeywordStatus.RAW.value:
            return 0.5
        elif keyword.quality_tier == 'A':
            return 1.0
        elif keyword.quality_tier == 'B':
            return 0.8
        elif keyword.quality_tier == 'C':
            return 0.6
        
        return 0.5

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

            base_opportunity_score = (
                (100 - difficulty) * 0.3 +
                trend * 0.4 +
                (search_volume / 1000) * 0.2 +
                (1 / (app_count + 1)) * 10
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

    STOPWORDS = frozenset({
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "up", "about", "into", "through", "during",
        "before", "after", "above", "below", "between", "under", "again", "further",
        "then", "once", "here", "there", "when", "where", "why", "how", "all", "each",
        "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
        "own", "same", "so", "than", "too", "very", "can", "will", "just", "should",
        "now", "your", "you", "its", "this", "that", "these", "those", "i", "we",
        "they", "he", "she", "it", "my", "our", "their", "his", "her", "what", "which",
        "who", "whom", "is", "are", "was", "were", "be", "been", "being", "have", "has",
        "had", "doing", "doing", "game", "app", "free", "pro", "lite", "hd", "ios",
    })

    WEAK_KEYWORDS = frozenset({
        "best", "top", "new", "latest", "easy", "simple", "fast", "quick", "smart",
        "awesome", "cool", "amazing", "great", "perfect", "fun", "good", "nice",
        "beautiful", "lovely", "amazing", "fantastic", "wonderful", "excellent",
        "premium", "ultimate", "super", "mega", "power", "world", "day", "today",
    })

    def _is_weak_keyword(self, keyword: str) -> bool:
        """Check if keyword is weak (brand, stopword, or generic adjective)."""
        kw_lower = keyword.lower().strip()
        if not kw_lower or len(kw_lower) <= 1:
            return True
        if kw_lower in self.STOPWORDS:
            return True
        if kw_lower in self.WEAK_KEYWORDS:
            return True
        return False

    def _extract_phrases(self, text: str, min_words: int = 2, max_words: int = 3) -> List[str]:
        """Extract multi-word phrases from text (title/subtitle)."""
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
