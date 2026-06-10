"""
trending_compute_service.py
===========================
Precomputes and persists trending scores for all apps that have recent ranking
history.  Called by the scheduler every 10 minutes so that the /trending
endpoint becomes a cheap read-only table scan rather than an expensive per-
request computation.

Performance: uses batch-prefetch (4 SQL queries total) instead of per-app
queries (~10 per app).  For 1 000 apps this reduces DB round-trips from
~10 000 to 4.
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.models import AppTrendingScore, Ranking
from app.utils.batch_utils import log_memory

logger = logging.getLogger(__name__)

_COMMIT_BATCH = 200  # commit every N apps to bound ORM identity map


def compute_trending_scores(db: Session) -> int:
    """
    Compute and upsert trending scores for every app with ranking data in the
    last 14 days.

    Returns the number of apps successfully scored.
    """
    t0 = time.monotonic()
    log_memory("trending_compute", "start")

    from app.scoring.engine import ScoringEngine  # noqa: PLC0415

    engine = ScoringEngine(db)

    cutoff = datetime.utcnow() - timedelta(days=14)

    # ── Batch prefetch: 4 queries total ─────────────────────────────────
    # 1. All rankings in the last 14 days → group by app_id in Python.
    #    This replaces BOTH the initial GROUP BY query AND all per-app
    #    _get_ranking_history() calls (5 per app).
    rankings_by_app = defaultdict(list)  # {app_id: [ranking_dicts]}
    for row in db.execute(
        text(
            "SELECT app_id, rank, previous_rank, recorded_at "
            "FROM rankings "
            "WHERE recorded_at >= :cutoff "
            "ORDER BY app_id, recorded_at"
        ),
        {"cutoff": cutoff},
    ):
        rankings_by_app[row.app_id].append(
            {
                "rank": row.rank,
                "previous_rank": row.previous_rank,
                "recorded_at": row.recorded_at,
            }
        )

    app_ids = list(rankings_by_app.keys())
    if not app_ids:
        logger.info(
            "[TRENDING_COMPUTE] No apps with recent ranking history — nothing to score"
        )
        return 0

    # 2. App data (current_reviews, current_rank, category_id) for all apps.
    app_data_map = {}  # {app_id: {current_reviews, current_rank, category_id}}
    _BATCH = 2000
    for i in range(0, len(app_ids), _BATCH):
        batch = app_ids[i : i + _BATCH]
        stmt = text(
            "SELECT id, current_reviews, current_rank, category_id "
            "FROM apps WHERE id IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        for row in db.execute(stmt, {"ids": batch}):
            app_data_map[row.id] = {
                "current_reviews": row.current_reviews,
                "current_rank": row.current_rank,
                "category_id": row.category_id,
            }

    # 3. Review counts (last 7 days) for bounded review momentum.
    review_cutoff = datetime.utcnow() - timedelta(days=7)
    review_count_map = {}  # {app_id: review_count}
    for i in range(0, len(app_ids), _BATCH):
        batch = app_ids[i : i + _BATCH]
        stmt = text(
            "SELECT app_id, COUNT(*) AS cnt "
            "FROM reviews "
            "WHERE app_id IN :ids AND date >= :cutoff "
            "GROUP BY app_id"
        ).bindparams(bindparam("ids", expanding=True))
        for row in db.execute(stmt, {"ids": batch, "cutoff": review_cutoff}):
            review_count_map[row.app_id] = row.cnt

    # 4. Category ranks for normalization — one query per distinct category.
    category_ids = list(
        {d["category_id"] for d in app_data_map.values() if d.get("category_id")}
    )
    category_ranks_map = defaultdict(list)  # {category_id: [ranks]}
    if category_ids:
        for i in range(0, len(category_ids), _BATCH):
            batch = category_ids[i : i + _BATCH]
            stmt = text(
                "SELECT category_id, current_rank "
                "FROM apps "
                "WHERE category_id IN :cat_ids AND current_rank IS NOT NULL"
            ).bindparams(bindparam("cat_ids", expanding=True))
            for row in db.execute(stmt, {"cat_ids": batch}):
                category_ranks_map[row.category_id].append(row.current_rank)

    logger.info(
        f"[TRENDING_COMPUTE] Prefetched data for {len(app_ids)} apps "
        f"({len(category_ids)} categories) in {time.monotonic() - t0:.1f}s"
    )

    # ── Score each app using prefetched data (zero DB queries) ──────────
    scored = 0
    batch_count = 0
    for app_id in app_ids:
        try:
            history = rankings_by_app.get(app_id, [])
            app_info = app_data_map.get(app_id, {})
            cat_id = app_info.get("category_id")

            trend_data = engine.compute_trend_score_from_prefetch(
                app_id=app_id,
                ranking_history=history,
                current_reviews=app_info.get("current_reviews"),
                current_rank=app_info.get("current_rank"),
                category_id=cat_id,
                review_count_7d=review_count_map.get(app_id, 0),
                category_ranks=category_ranks_map.get(cat_id) if cat_id else None,
            )

            if not trend_data or trend_data["final_score"] <= 0:
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
            batch_count += 1

            # Intermediate commit to release ORM objects
            if batch_count >= _COMMIT_BATCH:
                db.commit()
                db.expire_all()
                batch_count = 0

        except Exception as exc:
            logger.warning(
                f"[TRENDING_COMPUTE] Failed to score app_id={app_id}: {exc}"
            )

    # Final commit for remaining rows
    if batch_count > 0:
        db.commit()

    log_memory("trending_compute", "end")
    elapsed = time.monotonic() - t0
    logger.info(
        f"[TRENDING_COMPUTE] Scored {scored}/{len(app_ids)} apps in {elapsed:.1f}s "
        f"(4 prefetch queries, 0 per-app queries)"
    )
    return scored
