"""
Bootstrap Data Service
======================
Creates initial ranking snapshots and metric snapshots from existing app
metadata so that trending, blowing-up, and opportunity pipelines can
compute scores.

This is NOT fake data — it records the current known state of each app.
Apps already have `current_rank` from the discovery/ingestion pipeline;
this service materialises that into the `rankings` table so the scoring
pipelines have data points to work with.

Usage:
    POST /admin/bootstrap-data   (runs in background)
    or from Python:
        from app.services.bootstrap_data_service import run_bootstrap
        result = run_bootstrap(db)
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.models import App, Ranking, Category

logger = logging.getLogger(__name__)

_BATCH_SIZE = 200


def run_bootstrap(db: Session) -> Dict:
    """
    Create ranking snapshots from apps that have current_rank set.

    Strategy:
      - Select apps where current_rank IS NOT NULL and current_rank > 0
      - For each, create 3 ranking snapshots spread over 4 days:
          now - 4 days, now - 2 days, now  (all with the same truthful rank)
      - This gives the trending algorithm 3 data points in its 14-day window
      - Momentum = 0 (truthful — rank hasn't changed), but confidence > 0
      - Apps with good rank + reviews will surface in trending with modest scores

    Skips apps that already have ranking history in the last 7 days.

    Returns summary dict with counts.
    """
    t0 = time.monotonic()
    now = datetime.now(timezone.utc)

    # Find apps that already have recent rankings (skip them)
    cutoff_7d = now - timedelta(days=7)
    apps_with_rankings = set(
        row[0] for row in
        db.execute(
            text("SELECT DISTINCT app_id FROM rankings WHERE recorded_at >= :cutoff"),
            {"cutoff": cutoff_7d},
        )
    )

    # Find apps eligible for bootstrap
    candidates = (
        db.query(App.id, App.current_rank, App.category_id)
        .filter(
            App.current_rank.isnot(None),
            App.current_rank > 0,
            App.current_rank <= 500,  # only chart-level apps (rank 1-500)
        )
        .order_by(App.current_rank.asc())  # best-ranked first
        .limit(2000)  # cap to avoid overwhelming the first run
        .all()
    )

    skipped_existing = 0
    skipped_no_rank = 0
    created = 0

    # Timestamps for the 3 snapshots
    timestamps = [
        now - timedelta(days=4),
        now - timedelta(days=2),
        now,
    ]

    batch_count = 0
    for app_id, current_rank, category_id in candidates:
        if app_id in apps_with_rankings:
            skipped_existing += 1
            continue

        # Create 3 ranking snapshots with the same truthful rank
        for i, ts in enumerate(timestamps):
            previous_rank = current_rank if i > 0 else None
            ranking = Ranking(
                app_id=app_id,
                category_id=category_id,
                chart_type="topfree",  # default chart type
                rank=current_rank,
                previous_rank=previous_rank,
                rank_velocity=0.0,  # no change — truthful
                recorded_at=ts,
            )
            db.add(ranking)
            created += 1

        batch_count += 1
        if batch_count % _BATCH_SIZE == 0:
            db.commit()
            db.expire_all()
            logger.info(
                f"[BOOTSTRAP] Progress: {batch_count} apps bootstrapped, "
                f"{created} ranking rows created"
            )

    if batch_count % _BATCH_SIZE != 0:
        db.commit()

    elapsed = time.monotonic() - t0
    logger.info(
        f"[BOOTSTRAP] Ranking bootstrap complete: "
        f"{batch_count} apps, {created} ranking rows, "
        f"skipped {skipped_existing} (already have rankings) "
        f"in {elapsed:.1f}s"
    )

    return {
        "apps_bootstrapped": batch_count,
        "ranking_rows_created": created,
        "skipped_existing": skipped_existing,
        "elapsed_seconds": round(elapsed, 2),
    }


def run_metric_snapshot_bootstrap(db: Session) -> Dict:
    """
    Run metric snapshot computation for apps that have rankings but
    no metric snapshots yet.
    """
    from app.services.metric_snapshot_service import MetricSnapshotService

    t0 = time.monotonic()
    logger.info("[BOOTSTRAP] Starting metric snapshot bootstrap...")

    svc = MetricSnapshotService(db)
    count = svc.compute_all()

    elapsed = time.monotonic() - t0
    logger.info(
        f"[BOOTSTRAP] Metric snapshots complete: {count} apps in {elapsed:.1f}s"
    )
    return {"metric_snapshots_computed": count, "elapsed_seconds": round(elapsed, 2)}


def run_scoring_bootstrap(db: Session) -> Dict:
    """
    Trigger trending and blowing-up score computation after rankings exist.
    """
    t0 = time.monotonic()
    results = {}

    # 1. Trending scores
    logger.info("[BOOTSTRAP] Computing trending scores...")
    from app.services.trending_compute_service import compute_trending_scores
    trending_count = compute_trending_scores(db)
    results["trending_scored"] = trending_count
    logger.info(f"[BOOTSTRAP] Trending: {trending_count} apps scored")

    # 2. Blowing-up scores
    logger.info("[BOOTSTRAP] Computing blowing-up scores...")
    try:
        from app.services.blowing_up_service import BlowingUpService
        bu_svc = BlowingUpService(db)
        bu_count = bu_svc.compute_for_all_apps()
        results["blowing_up_scored"] = bu_count
        logger.info(f"[BOOTSTRAP] Blowing-up: {bu_count} apps scored")
    except Exception as exc:
        logger.warning(f"[BOOTSTRAP] Blowing-up scoring failed: {exc}")
        results["blowing_up_scored"] = 0

    # 3. Opportunity of the day
    logger.info("[BOOTSTRAP] Computing opportunity of the day...")
    try:
        from app.services.opportunity_of_day_service import OpportunityOfDayService
        opp_svc = OpportunityOfDayService(db)
        opp = opp_svc.get_or_generate()
        results["opportunity_generated"] = opp is not None
        logger.info(f"[BOOTSTRAP] Opportunity: {'generated' if opp else 'no qualifying apps'}")
    except Exception as exc:
        logger.warning(f"[BOOTSTRAP] Opportunity generation failed: {exc}")
        results["opportunity_generated"] = False

    elapsed = time.monotonic() - t0
    results["elapsed_seconds"] = round(elapsed, 2)
    return results


def run_full_bootstrap(db: Session) -> Dict:
    """
    Run the complete bootstrap pipeline:
      1. Create ranking snapshots from app metadata
      2. Compute metric snapshots
      3. Compute trending + blowing-up + opportunity scores
    """
    logger.info("[BOOTSTRAP] ═══════ Starting full data bootstrap ═══════")
    results = {}

    # Phase 1: Rankings
    ranking_result = run_bootstrap(db)
    results["rankings"] = ranking_result

    if ranking_result["ranking_rows_created"] == 0 and ranking_result["skipped_existing"] == 0:
        logger.warning(
            "[BOOTSTRAP] No apps with current_rank found. "
            "Run the chart scraper first (POST /admin/bootstrap) or wait for "
            "discovery jobs to populate app ranks."
        )
        results["status"] = "no_rankable_apps"
        return results

    # Phase 2: Metric snapshots
    metric_result = run_metric_snapshot_bootstrap(db)
    results["metrics"] = metric_result

    # Phase 3: Scoring
    scoring_result = run_scoring_bootstrap(db)
    results["scoring"] = scoring_result

    results["status"] = "complete"
    logger.info(
        f"[BOOTSTRAP] ═══════ Bootstrap complete ═══════\n"
        f"  Rankings: {ranking_result['ranking_rows_created']} rows\n"
        f"  Metrics: {metric_result['metric_snapshots_computed']} snapshots\n"
        f"  Trending: {scoring_result['trending_scored']} apps\n"
        f"  Blowing-up: {scoring_result.get('blowing_up_scored', 0)} apps"
    )
    return results
