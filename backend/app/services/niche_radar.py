"""
Niche Radar Engine
==================
Detects emerging App Store micro-niches by combining:
  1. Keyword growth anomalies (search_volume vs historical average)
  2. Category ranking momentum (rank_velocity > 0 clusters)
  3. Feature gap clustering (features requested across multiple apps)

Returns ranked "niche briefs" — actionable summaries of emerging opportunities.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.models import Keyword, AppKeyword, Ranking, App, FeatureGap

logger = logging.getLogger(__name__)


class NicheRadarEngine:
    def __init__(self, db: Session):
        self.db = db

    def scan(self, limit: int = 20) -> List[Dict]:
        """
        Run all niche detection passes and return ranked niche briefs.

        Returns:
            List of niche dicts sorted by niche_score descending.
        """
        briefs: List[Dict] = []

        briefs.extend(self._keyword_growth_niches())
        briefs.extend(self._ranking_momentum_niches())
        briefs.extend(self._feature_gap_niches())

        # Deduplicate by niche_name (keep highest score)
        seen: Dict[str, Dict] = {}
        for b in briefs:
            key = b["niche_name"].lower()
            if key not in seen or b["niche_score"] > seen[key]["niche_score"]:
                seen[key] = b

        result = sorted(seen.values(), key=lambda x: x["niche_score"], reverse=True)
        return result[:limit]

    # ------------------------------------------------------------------
    # Pass 1: Keyword growth anomalies
    # ------------------------------------------------------------------

    def _keyword_growth_niches(self) -> List[Dict]:
        """Surface keywords with above-average search_volume and low difficulty."""
        keywords = (
            self.db.query(Keyword)
            .filter(
                Keyword.search_volume > 0,
                Keyword.difficulty < 50,
            )
            .order_by(Keyword.search_volume.desc())
            .limit(50)
            .all()
        )

        if not keywords:
            return []

        avg_volume = sum(k.search_volume for k in keywords) / len(keywords)

        briefs = []
        for kw in keywords:
            if kw.search_volume <= avg_volume * 1.3:
                continue  # only anomalies (30% above average)

            # Count apps competing for this keyword
            app_count = (
                self.db.query(func.count(AppKeyword.id))
                .filter(AppKeyword.keyword_id == kw.id)
                .scalar()
            ) or 0

            score = min(
                int((kw.search_volume / 1000) * 15 + (100 - kw.difficulty) * 0.5),
                95,
            )

            briefs.append({
                "niche_name": f"{kw.term.title()} Apps",
                "niche_score": score,
                "signal_type": "keyword_growth",
                "description": (
                    f"Keyword '{kw.term}' shows high search demand "
                    f"({kw.search_volume:,} monthly searches) "
                    f"with low competition (difficulty: {kw.difficulty:.0f}/100). "
                    f"Currently {app_count} apps tracked in this space."
                ),
                "keywords": [kw.term],
                "app_count": app_count,
                "trend": kw.trend or 0,
                "search_volume": kw.search_volume,
                "difficulty": kw.difficulty,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

        return briefs

    # ------------------------------------------------------------------
    # Pass 2: Category ranking momentum clusters
    # ------------------------------------------------------------------

    def _ranking_momentum_niches(self) -> List[Dict]:
        """Detect categories where multiple apps are rapidly climbing the charts."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)

        # Apps that moved up 5+ positions in the last 14 days
        movers = (
            self.db.query(App)
            .join(Ranking, Ranking.app_id == App.id)
            .filter(
                Ranking.rank_velocity > 5,
                Ranking.recorded_at >= cutoff,
            )
            .distinct()
            .all()
        )

        if not movers:
            return []

        # Cluster by primary category
        category_counts: Dict[str, List[App]] = {}
        for app in movers:
            cat = (app.primary_category or "Unknown").strip()
            category_counts.setdefault(cat, []).append(app)

        briefs = []
        for cat, apps in category_counts.items():
            if len(apps) < 2:
                continue

            score = min(len(apps) * 12, 85)
            app_names = [a.name for a in apps[:5]]

            briefs.append({
                "niche_name": f"{cat} (Trending)",
                "niche_score": score,
                "signal_type": "ranking_momentum",
                "description": (
                    f"{len(apps)} apps in the '{cat}' category are rapidly climbing "
                    f"the App Store charts. Early movers include: "
                    f"{', '.join(app_names[:3])}."
                ),
                "keywords": [],
                "app_count": len(apps),
                "trend": float(len(apps)),
                "search_volume": 0,
                "difficulty": 0,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

        return briefs

    # ------------------------------------------------------------------
    # Pass 3: Feature gap clustering
    # ------------------------------------------------------------------

    def _feature_gap_niches(self) -> List[Dict]:
        """Surface features requested across many apps — each is a niche opportunity."""
        rows = (
            self.db.query(
                FeatureGap.feature_name,
                func.count(func.distinct(FeatureGap.app_id)).label("app_count"),
                func.sum(FeatureGap.mentions).label("total_mentions"),
            )
            .group_by(FeatureGap.feature_name)
            .having(func.count(func.distinct(FeatureGap.app_id)) >= 3)
            .order_by(func.sum(FeatureGap.mentions).desc())
            .limit(30)
            .all()
        )

        briefs = []
        for row in rows:
            score = min(int(row.app_count * 8 + row.total_mentions * 1.5), 90)

            briefs.append({
                "niche_name": f"{row.feature_name.title()} Feature",
                "niche_score": score,
                "signal_type": "feature_gap",
                "description": (
                    f"'{row.feature_name}' is missing from {row.app_count} tracked apps "
                    f"and has been requested {row.total_mentions} times in reviews. "
                    f"Building this feature could serve an underserved user need."
                ),
                "keywords": [row.feature_name],
                "app_count": row.app_count,
                "trend": float(row.total_mentions),
                "search_volume": 0,
                "difficulty": 0,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

        return briefs
