import logging
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.models import (
    AppIdea, App, FeatureGap, AppMarketWeakness, Keyword, AppKeyword, Ranking
)
from app.config.scoring_config import IDEA_GENERATOR_CONFIG as _IGCFG

logger = logging.getLogger(__name__)

# Country code → label map (mirrors frontend)
_COUNTRY_LABELS: Dict[str, str] = {
    "US": "United States", "GB": "United Kingdom", "DE": "Germany",
    "FR": "France", "JP": "Japan", "CN": "China", "KR": "South Korea",
    "AU": "Australia", "CA": "Canada", "BR": "Brazil", "IN": "India",
    "MX": "Mexico", "IT": "Italy", "ES": "Spain", "RU": "Russia",
    "NL": "Netherlands", "SE": "Sweden", "NO": "Norway", "DK": "Denmark",
    "FI": "Finland", "PL": "Poland", "TR": "Turkey", "AR": "Argentina",
    "CL": "Chile", "CO": "Colombia", "SG": "Singapore", "HK": "Hong Kong",
    "TW": "Taiwan", "TH": "Thailand", "ID": "Indonesia", "MY": "Malaysia",
    "PH": "Philippines", "VN": "Vietnam", "EG": "Egypt", "ZA": "South Africa",
    "NG": "Nigeria", "SA": "Saudi Arabia", "AE": "UAE", "IL": "Israel",
    "PT": "Portugal", "CZ": "Czech Republic", "HU": "Hungary", "RO": "Romania",
}


class IdeaGenerator:
    def __init__(self, db: Session):
        self.db = db

    def generate_all(self) -> int:
        ideas: List[Dict] = []

        try:
            ideas.extend(self._ideas_from_feature_gaps())
        except Exception as e:
            logger.error(f"Feature gap ideas failed: {e}")

        try:
            ideas.extend(self._ideas_from_weak_markets())
        except Exception as e:
            logger.error(f"Weak market ideas failed: {e}")

        try:
            ideas.extend(self._ideas_from_keywords())
        except Exception as e:
            logger.error(f"Keyword gap ideas failed: {e}")

        return self._save_ideas(ideas)

    # ------------------------------------------------------------------
    # Pattern A — Feature Gap Demand
    # ------------------------------------------------------------------
    def _ideas_from_feature_gaps(self) -> List[Dict]:
        rows = (
            self.db.query(
                FeatureGap.feature_name,
                func.count(func.distinct(FeatureGap.app_id)).label("app_count"),
                func.sum(FeatureGap.mentions).label("total_mentions"),
            )
            .group_by(FeatureGap.feature_name)
            .having(func.count(func.distinct(FeatureGap.app_id)) >= _IGCFG["feature_gap_min_apps"])
            .having(func.sum(FeatureGap.mentions) >= _IGCFG["feature_gap_min_mentions"])
            .order_by(func.sum(FeatureGap.mentions).desc())
            .limit(_IGCFG["feature_gap_limit"])
            .all()
        )

        ideas = []
        for row in rows:
            feature = row.feature_name
            app_count = row.app_count
            total_mentions = int(row.total_mentions or 0)

            score = min(
                app_count      * _IGCFG["feature_gap_app_count_scale"] +
                total_mentions * _IGCFG["feature_gap_mentions_scale"],
                _IGCFG["feature_gap_score_cap"],
            )

            # Get category from top related apps
            related_apps = (
                self.db.query(App)
                .join(FeatureGap, FeatureGap.app_id == App.id)
                .filter(FeatureGap.feature_name == feature)
                .limit(10)
                .all()
            )
            related_ids = [a.id for a in related_apps]
            category = None
            for a in related_apps:
                if a.primary_category:
                    category = a.primary_category
                    break

            title = f"{feature.title()} — Most Requested Missing Feature"
            ideas.append({
                "idea_title": title,
                "idea_description": (
                    f"Build an app that solves the '{feature}' gap. "
                    f"This feature is missing or poorly implemented across {app_count} apps "
                    f"with {total_mentions} total user mentions."
                ),
                "opportunity_score": float(score),
                "pattern_type": "feature_gap",
                "related_app_ids": related_ids,
                "reasoning": [
                    f"'{feature}' requested across {app_count} apps ({total_mentions} total mentions)",
                ],
                "signals": {
                    "feature_name": feature,
                    "app_count": app_count,
                    "total_mentions": total_mentions,
                },
                "primary_keyword": feature.lower(),
                "category": category,
            })

        return ideas

    # ------------------------------------------------------------------
    # Pattern B — Weak Market
    # ------------------------------------------------------------------
    def _ideas_from_weak_markets(self) -> List[Dict]:
        rows = (
            self.db.query(AppMarketWeakness)
            .filter(
                AppMarketWeakness.negative_ratio >= _IGCFG["weak_market_min_negative_ratio"],
                AppMarketWeakness.average_rating <= _IGCFG["weak_market_max_avg_rating"],
                AppMarketWeakness.total_reviews >= _IGCFG["weak_market_min_reviews"],
            )
            .order_by(AppMarketWeakness.negative_ratio.desc())
            .limit(_IGCFG["weak_market_limit"])
            .all()
        )

        # Deduplicate by (category, country)
        seen: set = set()
        ideas = []

        for row in rows:
            app = self.db.query(App).filter(App.id == row.app_id).first()
            if not app:
                continue

            category = app.primary_category or "App"
            country_label = _COUNTRY_LABELS.get(row.country.upper(), row.country)
            dedup_key = (category, row.country)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Find a low-difficulty keyword for this category
            keyword: Optional[str] = None
            diff_val: Optional[float] = None
            kw_row = (
                self.db.query(Keyword)
                .join(AppKeyword, AppKeyword.keyword_id == Keyword.id)
                .join(App, App.id == AppKeyword.app_id)
                .filter(
                    App.primary_category == category,
                    Keyword.difficulty < _IGCFG["keyword_difficulty_low"],
                )
                .order_by(Keyword.difficulty.asc())
                .first()
            )
            if kw_row:
                keyword = kw_row.term
                diff_val = kw_row.difficulty

            score = min(
                int(
                    row.negative_ratio * _IGCFG["weak_market_ratio_scale"] +
                    (_IGCFG["weak_market_rating_base"] - row.average_rating) * _IGCFG["weak_market_rating_scale"]
                ),
                _IGCFG["weak_market_score_cap"],
            )

            reasoning = [
                f"{country_label} has {row.negative_ratio * 100:.0f}% negative reviews ({row.total_reviews} total)",
                f"Avg rating in {country_label}: {row.average_rating:.1f}",
            ]
            if keyword and diff_val is not None:
                reasoning.append(
                    f"Keyword '{keyword}' has low competition (difficulty: {diff_val:.0f})"
                )

            title = f"{category} App for {country_label} Market"
            ideas.append({
                "idea_title": title,
                "idea_description": (
                    f"Create a {category.lower()} app tailored for {country_label} users. "
                    f"Current apps have a {row.negative_ratio * 100:.0f}% negative review rate "
                    f"with an average rating of {row.average_rating:.1f} in this market."
                ),
                "opportunity_score": float(score),
                "pattern_type": "weak_market",
                "related_app_ids": [row.app_id],
                "reasoning": reasoning,
                "signals": {
                    "country": row.country,
                    "negative_ratio": row.negative_ratio,
                    "average_rating": row.average_rating,
                    "total_reviews": row.total_reviews,
                },
                "primary_keyword": keyword,
                "category": category,
            })

        return ideas

    # ------------------------------------------------------------------
    # Pattern C — Keyword Opportunity
    # ------------------------------------------------------------------
    def _ideas_from_keywords(self) -> List[Dict]:
        rows = (
            self.db.query(Keyword)
            .filter(
                Keyword.difficulty < _IGCFG["keyword_gap_max_difficulty"],
                Keyword.search_volume >= _IGCFG["keyword_gap_min_volume"],
            )
            .order_by(Keyword.search_volume.desc())
            .limit(_IGCFG["keyword_gap_limit"])
            .all()
        )

        # Trending categories: recent rankings with positive velocity
        trending_categories: set = set()
        trending_rows = (
            self.db.query(App.primary_category)
            .join(Ranking, Ranking.app_id == App.id)
            .filter(
                Ranking.rank_velocity > 0,
                App.primary_category.isnot(None),
            )
            .distinct()
            .limit(20)
            .all()
        )
        for r in trending_rows:
            if r.primary_category:
                trending_categories.add(r.primary_category)

        ideas = []
        for kw in rows:
            # Find category for this keyword from linked apps
            app_row = (
                self.db.query(App)
                .join(AppKeyword, AppKeyword.app_id == App.id)
                .filter(
                    AppKeyword.keyword_id == kw.id,
                    App.primary_category.isnot(None),
                )
                .first()
            )
            category = app_row.primary_category if app_row else None

            trend = kw.trend or 0.0
            score = min(
                int(
                    (100 - kw.difficulty)      * _IGCFG["keyword_gap_difficulty_scale"] +
                    (kw.search_volume / 1000)  * _IGCFG["keyword_gap_volume_scale"] +
                    trend                      * _IGCFG["keyword_gap_trend_scale"]
                ),
                _IGCFG["keyword_gap_score_cap"],
            )

            reasoning = [
                f"Keyword '{kw.term}' has low competition (difficulty: {kw.difficulty:.0f})",
                f"Estimated {kw.search_volume:,} monthly searches",
            ]
            if category and category in trending_categories:
                reasoning.append(f"'{category}' category is trending")

            title = f'"{kw.term.title()}" App — Low Competition Opportunity'
            ideas.append({
                "idea_title": title,
                "idea_description": (
                    f"Build an app targeting the '{kw.term}' keyword. "
                    f"With only {kw.difficulty:.0f} difficulty and ~{kw.search_volume:,} monthly searches, "
                    f"this is an underserved market."
                ),
                "opportunity_score": float(score),
                "pattern_type": "keyword_gap",
                "related_app_ids": [],
                "reasoning": reasoning,
                "signals": {
                    "keyword": kw.term,
                    "search_volume": kw.search_volume,
                    "difficulty": kw.difficulty,
                    "trend": trend,
                },
                "primary_keyword": kw.term,
                "category": category,
            })

        return ideas

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _save_ideas(self, ideas: List[Dict]) -> int:
        if not ideas:
            return 0

        count = 0
        for idea in ideas:
            try:
                stmt = (
                    pg_insert(AppIdea)
                    .values(
                        idea_title=idea["idea_title"],
                        idea_description=idea.get("idea_description"),
                        opportunity_score=idea["opportunity_score"],
                        pattern_type=idea["pattern_type"],
                        related_app_ids=idea.get("related_app_ids", []),
                        reasoning=idea.get("reasoning", []),
                        signals=idea.get("signals", {}),
                        primary_keyword=idea.get("primary_keyword"),
                        category=idea.get("category"),
                    )
                    .on_conflict_do_update(
                        index_elements=["idea_title"],
                        set_={
                            "opportunity_score": idea["opportunity_score"],
                            "idea_description": idea.get("idea_description"),
                            "reasoning": idea.get("reasoning", []),
                            "signals": idea.get("signals", {}),
                            "related_app_ids": idea.get("related_app_ids", []),
                            "primary_keyword": idea.get("primary_keyword"),
                            "category": idea.get("category"),
                            "updated_at": func.now(),
                        },
                    )
                )
                self.db.execute(stmt)
                count += 1
            except Exception as e:
                logger.error(f"Failed to save idea '{idea.get('idea_title')}': {e}")
                self.db.rollback()
                continue

        self.db.commit()
        return count

    def get_ideas(
        self,
        sort_by: str = "opportunity_score",
        sort_order: str = "desc",
        pattern_type: Optional[str] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[AppIdea], int]:
        query = self.db.query(AppIdea)

        if pattern_type:
            query = query.filter(AppIdea.pattern_type == pattern_type)
        if category:
            query = query.filter(AppIdea.category.ilike(f"%{category}%"))
        if keyword:
            query = query.filter(
                AppIdea.primary_keyword.ilike(f"%{keyword}%")
            )

        valid_sort = {
            "opportunity_score": AppIdea.opportunity_score,
            "category": AppIdea.category,
            "primary_keyword": AppIdea.primary_keyword,
            "generated_at": AppIdea.generated_at,
        }
        sort_col = valid_sort.get(sort_by, AppIdea.opportunity_score)
        if sort_order == "asc":
            query = query.order_by(sort_col.asc().nullslast())
        else:
            query = query.order_by(sort_col.desc().nullslast())

        total = query.count()
        ideas = query.offset(skip).limit(limit).all()
        return ideas, total
