"""
Data quality / coverage metrics.

Exposes the numbers needed to answer "how good is our data right now?":
distinct apps by source and storefront, ranking/review freshness, and
pipeline throughput.

All queries are read-only and use indexed columns where possible so they can
be polled from the admin dashboard and /health without harming the DB.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.models import App, Country, Ranking, Review


def get_data_quality_metrics(db: Session) -> Dict:
    """
    Return a snapshot of current data coverage and freshness.

    The result is intentionally cheap to compute; it is meant to be polled
    every few minutes by the admin dashboard and /health.
    """
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)

    # ------------------------------------------------------------------
    # App inventory
    # ------------------------------------------------------------------
    total_apps = db.query(func.count(App.id)).scalar() or 0

    apps_by_source: List[Dict] = (
        db.query(App.source, func.count(App.id))
        .group_by(App.source)
        .all()
    )

    # Distinct apps seen in rankings, by country (storefront coverage)
    ranked_apps_by_country: List[Dict] = (
        db.query(Ranking.country, func.count(func.distinct(Ranking.app_id)))
        .group_by(Ranking.country)
        .all()
    )

    # ------------------------------------------------------------------
    # Rankings
    # ------------------------------------------------------------------
    rankings_24h = (
        db.query(func.count(Ranking.id))
        .filter(Ranking.recorded_at >= cutoff_24h)
        .scalar()
        or 0
    )

    newest_ranking = db.query(func.max(Ranking.recorded_at)).scalar()
    ranking_age_hours: Optional[float] = None
    if newest_ranking is not None:
        if newest_ranking.tzinfo is None:
            newest_ranking = newest_ranking.replace(tzinfo=timezone.utc)
        ranking_age_hours = round((now - newest_ranking).total_seconds() / 3600, 1)

    ranking_freshness_by_country: List[Dict] = (
        db.query(
            Ranking.country,
            func.count(func.distinct(Ranking.app_id)).label("app_count"),
            func.max(Ranking.recorded_at).label("latest"),
        )
        .group_by(Ranking.country)
        .all()
    )

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------
    total_reviews = db.query(func.count(Review.id)).scalar() or 0

    reviews_by_storefront: List[Dict] = (
        db.query(
            func.coalesce(Review.storefront, "unknown"),
            func.count(Review.id),
        )
        .group_by(Review.storefront)
        .all()
    )

    review_apps_by_storefront: List[Dict] = (
        db.query(
            func.coalesce(Review.storefront, "unknown"),
            func.count(func.distinct(Review.app_id)),
        )
        .group_by(Review.storefront)
        .all()
    )

    # ------------------------------------------------------------------
    # App freshness
    # ------------------------------------------------------------------
    oldest_enriched = db.query(func.min(App.last_enriched_at)).scalar()
    oldest_enriched_hours: Optional[float] = None
    if oldest_enriched is not None:
        if oldest_enriched.tzinfo is None:
            oldest_enriched = oldest_enriched.replace(tzinfo=timezone.utc)
        oldest_enriched_hours = round((now - oldest_enriched).total_seconds() / 3600, 1)

    apps_enriched_24h = (
        db.query(func.count(App.id))
        .filter(App.last_enriched_at >= cutoff_24h)
        .scalar()
        or 0
    )

    apps_enriched_7d = (
        db.query(func.count(App.id))
        .filter(App.last_enriched_at >= cutoff_7d)
        .scalar()
        or 0
    )

    # ------------------------------------------------------------------
    # Countries configured for acquisition
    # ------------------------------------------------------------------
    countries_enabled = (
        db.query(func.count(Country.code))
        .filter(Country.enabled == True)
        .scalar()
        or 0
    )

    return {
        "generated_at": now.isoformat(),
        "apps": {
            "total": total_apps,
            "by_source": [{"source": s, "count": c} for s, c in apps_by_source],
            "enriched_last_24h": apps_enriched_24h,
            "enriched_last_7d": apps_enriched_7d,
            "oldest_enriched_hours": oldest_enriched_hours,
        },
        "rankings": {
            "total_last_24h": rankings_24h,
            "newest_recorded_at": newest_ranking.isoformat() if newest_ranking else None,
            "age_hours": ranking_age_hours,
            "countries": [
                {
                    "country": country,
                    "distinct_apps": app_count,
                    "latest_recorded_at": latest.isoformat() if latest else None,
                    "age_hours": round((now - latest).total_seconds() / 3600, 1)
                    if latest
                    else None,
                }
                for country, app_count, latest in ranking_freshness_by_country
            ],
        },
        "reviews": {
            "total": total_reviews,
            "by_storefront": [
                {"storefront": sf, "count": c} for sf, c in reviews_by_storefront
            ],
            "apps_by_storefront": [
                {"storefront": sf, "count": c} for sf, c in review_apps_by_storefront
            ],
        },
        "countries": {
            "enabled": countries_enabled,
        },
    }
