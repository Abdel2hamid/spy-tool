"""
Competitor Comparison Service
=============================
Read-only aggregation that builds a side-by-side comparison of 2–5 apps
using data already in the database.  No scraping, no external API calls.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    App,
    AppDiscoveredKeyword,
    AppKeywordIntelligence,
    FeatureGap,
    Keyword,
    Review,
)

logger = logging.getLogger(__name__)


class CompetitorCompareService:
    def __init__(self, db: Session):
        self.db = db

    def compare(self, app_ids: List[int]) -> dict:
        # 1. Load apps preserving caller ordering
        apps_by_id: Dict[int, App] = {}
        for row in self.db.query(App).filter(App.id.in_(app_ids)).all():
            apps_by_id[row.id] = row
        ordered_ids = [aid for aid in app_ids if aid in apps_by_id]

        # 2. Review velocity (last 30 days)
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        velocity_rows = (
            self.db.query(Review.app_id, func.count(Review.id))
            .filter(Review.app_id.in_(ordered_ids), Review.date >= cutoff)
            .group_by(Review.app_id)
            .all()
        )
        velocity_map: Dict[int, int] = {app_id: cnt for app_id, cnt in velocity_rows}

        # 3. Keyword sets per app
        keyword_sets = self._keyword_sets(ordered_ids)

        # 4. Top 5 feature gaps per app
        feature_gaps_map = self._feature_gaps(ordered_ids)

        # 5. Per-app summary dicts
        summaries = []
        for aid in ordered_ids:
            app = apps_by_id[aid]
            summaries.append({
                "app_id": aid,
                "store_app_id": app.app_id,
                "name": app.name,
                "icon_url": app.icon_url,
                "developer": app.developer,
                "primary_category": app.primary_category,
                "current_rank": app.current_rank,
                "current_rating": app.current_rating,
                "current_reviews": app.current_reviews,
                "estimated_installs_min": app.estimated_installs_min,
                "estimated_installs_max": app.estimated_installs_max,
                "install_confidence": app.install_confidence,
                "estimated_revenue_monthly_min": app.estimated_revenue_monthly_min,
                "estimated_revenue_monthly_max": app.estimated_revenue_monthly_max,
                "is_free": app.is_free if app.is_free is not None else True,
                "price": app.price or 0,
                "review_velocity_30d": velocity_map.get(aid, 0),
                "keyword_count": len(keyword_sets.get(aid, set())),
                "feature_gaps": feature_gaps_map.get(aid, []),
            })

        # 6. Keyword overlap
        keyword_overlap = self._keyword_overlap(ordered_ids, keyword_sets, apps_by_id)

        # 7. Winners
        winners = self._compute_winners(summaries)

        return {
            "apps": summaries,
            "keyword_overlap": keyword_overlap,
            "winners": winners,
            "compared_count": len(ordered_ids),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── helpers ──────────────────────────────────────────────────────────

    def _keyword_sets(self, app_ids: List[int]) -> Dict[int, Set[str]]:
        """Build lowercased keyword sets per app.
        Primary source: AppKeywordIntelligence joined to Keyword.term.
        Fallback: AppDiscoveredKeyword.keyword for apps with no intelligence rows.
        """
        result: Dict[int, Set[str]] = {aid: set() for aid in app_ids}

        # Primary: intelligence table
        intel_rows = (
            self.db.query(AppKeywordIntelligence.app_id, Keyword.term)
            .join(Keyword, AppKeywordIntelligence.keyword_id == Keyword.id)
            .filter(AppKeywordIntelligence.app_id.in_(app_ids))
            .all()
        )
        apps_with_intel: Set[int] = set()
        for app_id, term in intel_rows:
            result[app_id].add(term.lower())
            apps_with_intel.add(app_id)

        # Fallback: discovered keywords for apps without intelligence rows
        fallback_ids = [aid for aid in app_ids if aid not in apps_with_intel]
        if fallback_ids:
            disc_rows = (
                self.db.query(AppDiscoveredKeyword.app_id, AppDiscoveredKeyword.keyword)
                .filter(AppDiscoveredKeyword.app_id.in_(fallback_ids))
                .all()
            )
            for app_id, kw in disc_rows:
                result[app_id].add(kw.lower())

        return result

    def _feature_gaps(self, app_ids: List[int]) -> Dict[int, List[dict]]:
        """Top 5 feature gaps per app ordered by mentions desc."""
        rows = (
            self.db.query(FeatureGap)
            .filter(FeatureGap.app_id.in_(app_ids))
            .order_by(FeatureGap.app_id, FeatureGap.mentions.desc())
            .all()
        )
        result: Dict[int, List[dict]] = {aid: [] for aid in app_ids}
        for gap in rows:
            if len(result[gap.app_id]) < 5:
                result[gap.app_id].append({
                    "feature": gap.feature_name,
                    "mentions": gap.mentions,
                    "detected_at": gap.detected_at.isoformat() if gap.detected_at else None,
                })
        return result

    def _keyword_overlap(
        self,
        app_ids: List[int],
        keyword_sets: Dict[int, Set[str]],
        apps_by_id: Dict[int, App],
    ) -> dict:
        sets = [keyword_sets.get(aid, set()) for aid in app_ids]
        if sets:
            shared_all = set.intersection(*sets) if len(sets) > 1 else sets[0]
        else:
            shared_all = set()
        shared_all_list = sorted(shared_all)[:30]

        per_app = []
        for aid in app_ids:
            own = keyword_sets.get(aid, set())
            others = set()
            for other_id in app_ids:
                if other_id != aid:
                    others |= keyword_sets.get(other_id, set())
            shared = own & others
            unique = own - others
            per_app.append({
                "app_id": aid,
                "name": apps_by_id[aid].name,
                "total": len(own),
                "shared": len(shared),
                "unique": len(unique),
                "unique_samples": sorted(unique)[:15],
            })

        return {
            "shared_by_all": shared_all_list,
            "shared_by_all_count": len(shared_all),
            "per_app": per_app,
        }

    @staticmethod
    def _compute_winners(summaries: List[dict]) -> Dict[str, Optional[int]]:
        """Pick winner per metric. Lower is better for current_rank."""
        def _best(key: str, lower_is_better: bool = False) -> Optional[int]:
            candidates = [(s["app_id"], s.get(key)) for s in summaries if s.get(key) is not None]
            if not candidates:
                return None
            if lower_is_better:
                return min(candidates, key=lambda x: x[1])[0]
            return max(candidates, key=lambda x: x[1])[0]

        def _best_midpoint(key_min: str, key_max: str) -> Optional[int]:
            candidates = []
            for s in summaries:
                lo = s.get(key_min)
                hi = s.get(key_max)
                if lo is not None or hi is not None:
                    mid = ((lo or 0) + (hi or 0)) / 2
                    candidates.append((s["app_id"], mid))
            if not candidates:
                return None
            return max(candidates, key=lambda x: x[1])[0]

        return {
            "current_rating": _best("current_rating"),
            "current_reviews": _best("current_reviews"),
            "current_rank": _best("current_rank", lower_is_better=True),
            "review_velocity_30d": _best("review_velocity_30d"),
            "estimated_installs": _best_midpoint("estimated_installs_min", "estimated_installs_max"),
            "estimated_revenue": _best_midpoint("estimated_revenue_monthly_min", "estimated_revenue_monthly_max"),
            "keyword_count": _best("keyword_count"),
        }
