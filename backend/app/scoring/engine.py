from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.models import App, Ranking, Review, Keyword, AppKeyword, Opportunity, Category
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

            primary_keyword = app.name.split()[0].lower() if app.name else "app"
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

            opportunity_score = (
                (100 - difficulty) * 0.3 +
                trend * 0.4 +
                (search_volume / 1000) * 0.2 +
                (1 / (app_count + 1)) * 10
            )

            opportunities.append({
                "keyword": kw.term,
                "search_volume": search_volume,
                "difficulty": difficulty,
                "trend": trend,
                "opportunity_score": round(opportunity_score, 2),
                "current_apps": app_count
            })

        opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return opportunities[:20]
