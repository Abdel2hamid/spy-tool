"""
trending_compute_service.py
===========================
Precomputes and persists trending scores for all apps that have recent ranking
history.  Called by the scheduler every 10 minutes so that the /trending
endpoint becomes a cheap read-only table scan rather than an expensive per-
request computation.
"""

import logging
import time
from datetime import datetime, timedelta

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.models import AppTrendingScore, Ranking

logger = logging.getLogger(__name__)


def compute_trending_scores(db: Session) -> int:
    """
    Compute and upsert trending scores for every app with ranking data in the
    last 14 days.

    Returns the number of apps successfully scored.
    """
    t0 = time.monotonic()

    # Local import to avoid circular dependency (engine → models → services)
    from app.scoring.engine import ScoringEngine  # noqa: PLC0415

    engine = ScoringEngine(db)

    cutoff = datetime.utcnow() - timedelta(days=14)
    app_ids = [
        row[0]
        for row in (
            db.query(Ranking.app_id)
            .filter(Ranking.recorded_at >= cutoff)
            .group_by(Ranking.app_id)
            .all()
        )
    ]

    if not app_ids:
        logger.info("[TRENDING_COMPUTE] No apps with recent ranking history — nothing to score")
        return 0

    scored = 0
    for app_id in app_ids:
        try:
            trend_data = engine.compute_trend_score(app_id, use_category_norm=True)

            if trend_data["final_score"] <= 0:
                continue

            stmt = (
                pg_insert(AppTrendingScore)
                .values(
                    app_id=app_id,
                    trend_score=trend_data["final_score"],
                    momentum_score=trend_data["momentum_weighted"],
                    momentum_3d=trend_data["momentum_3d"],
                    momentum_7d=trend_data["momentum_7d"],
                    consistency_score=trend_data["consistency_score"],
                    absolute_rank_bonus=trend_data["absolute_rank_bonus"],
                    review_momentum=trend_data["review_momentum"],
                    confidence_factor=trend_data["confidence_factor"],
                    computed_at=datetime.utcnow(),
                )
                .on_conflict_do_update(
                    index_elements=["app_id"],
                    set_={
                        "trend_score": trend_data["final_score"],
                        "momentum_score": trend_data["momentum_weighted"],
                        "momentum_3d": trend_data["momentum_3d"],
                        "momentum_7d": trend_data["momentum_7d"],
                        "consistency_score": trend_data["consistency_score"],
                        "absolute_rank_bonus": trend_data["absolute_rank_bonus"],
                        "review_momentum": trend_data["review_momentum"],
                        "confidence_factor": trend_data["confidence_factor"],
                        "computed_at": datetime.utcnow(),
                    },
                )
            )
            db.execute(stmt)
            scored += 1

        except Exception as exc:
            logger.warning(f"[TRENDING_COMPUTE] Failed to score app_id={app_id}: {exc}")

    db.commit()

    elapsed = time.monotonic() - t0
    logger.info(
        f"[TRENDING_COMPUTE] Scored {scored}/{len(app_ids)} apps in {elapsed:.1f}s"
    )
    return scored
