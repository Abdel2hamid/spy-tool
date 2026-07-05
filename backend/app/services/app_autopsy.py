"""
App Autopsy Service
===================
Produces an aggregated "Why Is This App Winning?" report by combining:
  - Rating & review momentum
  - Chart rank trajectory
  - Version update cadence
  - Feature gap summary (what competitors are missing)
  - Revenue estimate
  - Install estimate

Optionally uses Claude to generate a narrative summary.
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import App, Ranking, Review, AppVersion, FeatureGap, AppAnalytics

logger = logging.getLogger(__name__)

_NARRATIVE_MODEL = "claude-haiku-4-5-20251001"

_NARRATIVE_PROMPT = """You are an App Store market analyst. Here is performance data for the app "{app_name}":

{data_json}

Write a concise 3-5 sentence "winning autopsy" explaining:
1. Why this app is succeeding (key strengths)
2. What data signals confirm its momentum
3. One strategic insight for competitors

Be direct, specific, and data-driven. Return only the narrative text (no JSON, no headers)."""


class AppAutopsyService:
    def __init__(self, db: Session):
        self.db = db

    def get_autopsy(self, app_id: int, use_llm: bool = True) -> Dict:
        """
        Build and return a comprehensive app autopsy report.
        """
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return {"error": "App not found"}

        data = {
            "app_id": app_id,
            "app_name": app.name,
            "developer": app.developer,
            "category": app.primary_category,
            "current_rating": app.current_rating,
            "current_reviews": app.current_reviews,
            "current_rank": app.current_rank,
            "price": app.price,
            "is_free": app.is_free,
            "has_iap": bool(app.in_app_purchases),
            "release_date": app.release_date.isoformat() if app.release_date else None,
        }

        # Install / revenue estimates
        data["estimated_installs_min"] = app.estimated_installs_min
        data["estimated_installs_max"] = app.estimated_installs_max
        data["install_confidence"] = app.install_confidence
        data["estimated_revenue_monthly_min"] = app.estimated_revenue_monthly_min
        data["estimated_revenue_monthly_max"] = app.estimated_revenue_monthly_max

        # Rating momentum (30d)
        data["rating_momentum"] = self._rating_momentum(app_id)

        # Review growth (30d vs previous 30d)
        data["review_growth_30d"] = self._review_growth(app_id, days=30)

        # Rank trajectory
        data["rank_trajectory"] = self._rank_trajectory(app_id)

        # Version cadence
        data["update_cadence"] = self._update_cadence(app_id)

        # Top feature gaps in competitors
        data["competitor_feature_gaps"] = self._competitor_gaps(app)

        # Strengths summary
        data["strengths"] = self._derive_strengths(data)

        # LLM narrative
        if use_llm:
            data["narrative"] = self._generate_narrative(app.name, data)
        else:
            data["narrative"] = None

        return data

    # ------------------------------------------------------------------

    def _rating_momentum(self, app_id: int) -> float:
        """
        Compare average rating of reviews in last 30d vs previous 30d.
        Positive = improving. Returns delta rounded to 2 dp.
        """
        now = datetime.now(timezone.utc)
        cutoff_recent = now - timedelta(days=30)
        cutoff_prev = now - timedelta(days=60)

        recent_avg = (
            self.db.query(func.avg(Review.rating))
            .filter(Review.app_id == app_id, Review.date >= cutoff_recent)
            .scalar()
        ) or 0.0

        prev_avg = (
            self.db.query(func.avg(Review.rating))
            .filter(
                Review.app_id == app_id,
                Review.date >= cutoff_prev,
                Review.date < cutoff_recent,
            )
            .scalar()
        ) or 0.0

        return round(float(recent_avg) - float(prev_avg), 2)

    def _review_growth(self, app_id: int, days: int = 30) -> float:
        """Review count percentage growth vs previous period."""
        now = datetime.now(timezone.utc)
        cutoff_recent = now - timedelta(days=days)
        cutoff_prev = now - timedelta(days=days * 2)

        recent = (
            self.db.query(func.count(Review.id))
            .filter(Review.app_id == app_id, Review.date >= cutoff_recent)
            .scalar()
        ) or 0

        prev = (
            self.db.query(func.count(Review.id))
            .filter(
                Review.app_id == app_id,
                Review.date >= cutoff_prev,
                Review.date < cutoff_recent,
            )
            .scalar()
        ) or 0

        if prev == 0:
            return 0.0
        return round((recent - prev) / prev * 100, 1)

    def _rank_trajectory(self, app_id: int) -> Dict:
        """Return rank 30 days ago vs today and the trend direction."""
        now = datetime.now(timezone.utc)

        current = (
            self.db.query(Ranking)
            .filter(Ranking.app_id == app_id)
            .order_by(Ranking.recorded_at.desc())
            .first()
        )

        month_ago = (
            self.db.query(Ranking)
            .filter(
                Ranking.app_id == app_id,
                Ranking.recorded_at <= now - timedelta(days=25),
            )
            .order_by(Ranking.recorded_at.desc())
            .first()
        )

        current_rank = current.rank if current else None
        prev_rank = month_ago.rank if month_ago else None

        if current_rank and prev_rank:
            delta = prev_rank - current_rank  # positive = improved
            trend = "improving" if delta > 0 else "declining" if delta < 0 else "stable"
        else:
            delta = 0
            trend = "unknown"

        return {
            "current_rank": current_rank,
            "rank_30d_ago": prev_rank,
            "rank_delta": delta,
            "trend": trend,
        }

    def _update_cadence(self, app_id: int) -> Dict:
        """Compute average days between releases and count recent versions."""
        versions = (
            self.db.query(AppVersion)
            .filter(AppVersion.app_id == app_id, AppVersion.release_date.isnot(None))
            .order_by(AppVersion.release_date.desc())
            .limit(20)
            .all()
        )

        if len(versions) < 2:
            return {"avg_days_between_releases": None, "versions_last_90d": len(versions)}

        dates = [v.release_date for v in versions]
        gaps = []
        for i in range(len(dates) - 1):
            d1 = dates[i].replace(tzinfo=timezone.utc) if dates[i].tzinfo is None else dates[i]
            d2 = dates[i + 1].replace(tzinfo=timezone.utc) if dates[i + 1].tzinfo is None else dates[i + 1]
            gaps.append(abs((d1 - d2).days))

        avg_gap = round(sum(gaps) / len(gaps)) if gaps else None

        cutoff_90 = datetime.now(timezone.utc) - timedelta(days=90)
        recent_count = sum(
            1 for v in versions
            if v.release_date and (
                v.release_date.replace(tzinfo=timezone.utc) if v.release_date.tzinfo is None
                else v.release_date
            ) >= cutoff_90
        )

        return {
            "avg_days_between_releases": avg_gap,
            "versions_last_90d": recent_count,
        }

    def _competitor_gaps(self, app: App) -> List[Dict]:
        """Top feature gaps from apps in the same category."""
        if not app.primary_category:
            return []

        same_cat_app_ids = (
            self.db.query(App.id)
            .filter(
                App.primary_category.ilike(f"%{app.primary_category}%"),
                App.id != app.id,
            )
            .subquery()
        )

        gaps = (
            self.db.query(
                FeatureGap.feature_name,
                func.sum(FeatureGap.mentions).label("total_mentions"),
                func.count(func.distinct(FeatureGap.app_id)).label("app_count"),
            )
            .filter(FeatureGap.app_id.in_(same_cat_app_ids))
            .group_by(FeatureGap.feature_name)
            .order_by(func.sum(FeatureGap.mentions).desc())
            .limit(5)
            .all()
        )

        return [
            {
                "feature": row.feature_name,
                "total_mentions": row.total_mentions,
                "apps_missing": row.app_count,
            }
            for row in gaps
        ]

    def _derive_strengths(self, data: Dict) -> List[str]:
        """Rule-based strength signals."""
        strengths = []
        if data.get("current_rating") and data["current_rating"] >= 4.5:
            strengths.append(f"Exceptional user rating ({data['current_rating']:.1f}★)")
        if data.get("review_growth_30d") and data["review_growth_30d"] > 20:
            strengths.append(f"Rapid review growth (+{data['review_growth_30d']:.0f}% in 30 days)")
        traj = data.get("rank_trajectory", {})
        if traj.get("rank_delta") and traj["rank_delta"] > 5:
            strengths.append(f"Strong chart momentum (improved {traj['rank_delta']} positions)")
        cadence = data.get("update_cadence", {})
        if cadence.get("avg_days_between_releases") and cadence["avg_days_between_releases"] < 21:
            strengths.append(f"Frequent updates (avg every {cadence['avg_days_between_releases']} days)")
        if data.get("rating_momentum") and data["rating_momentum"] > 0.2:
            strengths.append(f"Improving sentiment (+{data['rating_momentum']:.2f}★ in 30 days)")
        return strengths or ["Insufficient data for strength analysis"]

    def _generate_narrative(self, app_name: str, data: Dict) -> Optional[str]:
        """Use Claude Haiku to write a narrative autopsy."""
        try:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return None
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, timeout=30.0)

            # Trim data for prompt (remove verbose fields)
            slim = {
                k: v for k, v in data.items()
                if k not in ("competitor_feature_gaps",) and v is not None
            }
            slim["top_competitor_gaps"] = [g["feature"] for g in data.get("competitor_feature_gaps", [])]

            prompt = _NARRATIVE_PROMPT.format(
                app_name=app_name,
                data_json=json.dumps(slim, indent=2, default=str),
            )

            msg = client.messages.create(
                model=_NARRATIVE_MODEL,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()

        except Exception as exc:
            logger.warning(f"Narrative generation failed: {exc}")
            return None
