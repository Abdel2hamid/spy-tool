"""
Recurring scraping, scoring, and discovery scheduler.

Job schedule:

  Job ID                   Interval  First run   Purpose
  ───────────────────────  ────────  ──────────  ─────────────────────────────────────────
  ranking_refresh            2 h      3 min       Chart RSS → ranking rows (skip if fresh)
  opportunity_compute        1 h      5 min       Precompute opportunity of the day → daily_reports
  blowing_up_compute         15 min   3 min       Precompute blowing-up scores → app_blowing_up_scores
  trending_compute           10 min   2 min       Precompute trending scores → app_trending_scores
  discovery_keywords         6 h      2 min       100+ keyword search → queue
  discovery_charts           2 h      5 min       Charts × all genres × 20 countries → queue
  discovery_developer        12 h     10 min      Developer expansion → queue
  queue_processor            30 min   15 min      Process discovery queue (full scrape)
  hourly_reviews_ratings     1 h      1 h         Quick refresh (rating/reviews for all apps)
  hourly_scoring             1 h      65 min      Recompute scores + daily report
  full_metadata              6 h      6 h         Full metadata refresh for all tracked apps
  keyword_discovery          24 h      2 min      Keyword expansion engine (10k-100k keywords)
  keyword_cleanup_daily      24 h     45 min      Prune low-value / stale keywords from DB
  review_scraper             6 h      90 min      Ingest up to 500 reviews for top 300 ranked apps
  sentiment_analysis         1 h      35 min      Rule-based sentiment classification + app analytics
  feature_gap                2 h      50 min      Feature gap analysis from negative reviews
  (analytics_update removed — redundant with sentiment_analysis step 2)

Discovery jobs have short first-run delays so coverage starts building
immediately after deploy without waiting for the bootstrap endpoint.

To change an interval: edit the `hours=` / `minutes=` in setup_scheduler().
To disable a job:      comment out its scheduler.add_job() call.
"""

import asyncio
import functools
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.utils.batch_utils import log_memory

logger = logging.getLogger(__name__)

# Module-level singleton – started and stopped by main.py lifespan.
scheduler = AsyncIOScheduler(timezone="UTC")

# ---------------------------------------------------------------------------
# Shared defaults applied to every job
# ---------------------------------------------------------------------------
_JOB_DEFAULTS = dict(
    max_instances=1,     # never run the same job twice concurrently
    replace_existing=True,
    coalesce=True,       # merge missed fire(s) into a single run
    misfire_grace_time=300,  # allow up to 5 min late start before skipping
)

# ---------------------------------------------------------------------------
# Job timeout configuration (seconds) — prevents hung jobs from blocking
# all future runs.  Default 30 min for unlisted jobs.
# ---------------------------------------------------------------------------
_JOB_TIMEOUTS = {
    "ranking_refresh": 600,            # 10 min (chart RSS only, no full scrape)
    "trending_compute": 300,           # 5 min (fast, SQL-only)
    "blowing_up_compute": 600,         # 10 min
    "opportunity_compute": 600,        # 10 min
    "weekly_opportunities_compute": 600,
    "sentiment_analysis": 600,         # 10 min
    # analytics_update: REMOVED — redundant with sentiment_analysis step 2
    "feature_gap": 1800,               # 30 min
    "hourly_reviews_ratings": 3600,    # 1 h (touches all apps)
    "hourly_scoring": 3600,            # 1 h
    "full_metadata": 7200,             # 2 h (full scrape)
    "discovery_keywords": 3600,        # 1 h
    "discovery_charts": 1800,          # 30 min
    "discovery_developer": 1800,       # 30 min
    "queue_processor": 3600,           # 1 h
    "keyword_intelligence": 7200,      # 2 h
    "keyword_scoring": 3600,           # 1 h
    "keyword_discovery": 7200,         # 2 h
    "keyword_discovery_daily": 7200,   # 2 h
    "keyword_discovery_phase1_daily": 7200,
    "keyword_cleanup_daily": 600,      # 10 min
    "keyword_quality_pruning": 600,    # 10 min
    "review_scraper": 3600,            # 1 h
    "mass_discovery_light": 3600,      # 1 h
    "tier_reclassify": 600,            # 10 min
    "enrich_hot": 1800,                # 30 min
    "enrich_warm": 3600,               # 1 h
    "enrich_cold": 3600,               # 1 h
    "keyword_rank_tracker": 3600,      # 1 h
    "ad_intelligence": 3600,           # 1 h
    "campaign_detection": 1800,        # 30 min
}
_DEFAULT_TIMEOUT = 1800  # 30 min

# ---------------------------------------------------------------------------
# Execution metrics — survives across runs, exposed via /health
# ---------------------------------------------------------------------------
_job_metrics = {}  # type: dict


def get_job_metrics() -> dict[str, dict]:
    """Return a copy of execution metrics for all jobs (used by /health)."""
    return dict(_job_metrics)


# ---------------------------------------------------------------------------
# Timeout + metrics decorator
# ---------------------------------------------------------------------------

def _with_timeout(job_id: str, timeout: int = None):
    """
    Decorator: wrap a scheduler job with timeout enforcement, execution
    metrics, and structured logging.

    - If the job exceeds *timeout* seconds, asyncio.TimeoutError is raised
      and the underlying task is cancelled.
    - Metrics (runs, successes, failures, timeouts, last_duration) are
      tracked in ``_job_metrics`` and exposed via ``get_job_metrics()``.
    """
    _timeout = timeout or _JOB_TIMEOUTS.get(job_id, _DEFAULT_TIMEOUT)

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper():
            m = _job_metrics.setdefault(job_id, {
                "runs": 0, "ok": 0, "fail": 0, "timeout": 0,
                "last_start": None, "last_end": None, "last_duration_s": None,
            })
            m["runs"] += 1
            m["last_start"] = datetime.utcnow().isoformat()
            try:
                await asyncio.wait_for(fn(), timeout=_timeout)
                m["ok"] += 1
            except asyncio.TimeoutError:
                m["timeout"] += 1
                logger.error(
                    f"[SCHEDULER] ⏰ {job_id} TIMED OUT after {_timeout}s "
                    f"(runs={m['runs']}, ok={m['ok']}, timeout={m['timeout']})"
                )
            except Exception:
                m["fail"] += 1
                raise
            finally:
                now = datetime.utcnow()
                m["last_end"] = now.isoformat()
                if m["last_start"]:
                    start = datetime.fromisoformat(m["last_start"])
                    m["last_duration_s"] = round((now - start).total_seconds(), 1)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Job helpers
# ---------------------------------------------------------------------------

def _log_start(job_id: str) -> float:
    log_memory(job_id, "start")
    logger.info(f"[SCHEDULER] ▶  {job_id} started")
    return datetime.utcnow().timestamp()


def _log_done(job_id: str, t0: float, extra: str = ""):
    elapsed = datetime.utcnow().timestamp() - t0
    msg = f"[SCHEDULER] ✓  {job_id} finished in {elapsed:.1f}s"
    if extra:
        msg += f"  ({extra})"
    logger.info(msg)
    log_memory(job_id, "end")


def _log_fail(job_id: str, exc: Exception):
    logger.error(f"[SCHEDULER] ✗  {job_id} FAILED: {exc}", exc_info=True)
    log_memory(job_id, "fail")


# ---------------------------------------------------------------------------
# Job: every 1 h — quick reviews & ratings refresh
# ---------------------------------------------------------------------------

@_with_timeout("hourly_reviews_ratings")
async def job_hourly_reviews_ratings():
    """
    Lightweight hourly refresh for all tracked apps:
    - Update current rating, review count, current version (iTunes Lookup API)
    - Save any new reviews (iTunes RSS API)

    Does NOT re-scrape version history HTML (that is handled by full_metadata).
    """
    job_id = "hourly_reviews_ratings"
    t0 = _log_start(job_id)
    from app.workers.tasks import ScraperWorker  # local import avoids circular

    worker = ScraperWorker()
    await worker.initialize()
    try:
        count = await worker.scrape_quick_refresh_all()
        _log_done(job_id, t0, f"{count} apps refreshed")
    except Exception as exc:
        _log_fail(job_id, exc)
    finally:
        await worker.cleanup()


# ---------------------------------------------------------------------------
# Job: every 1 h — scoring & analytics recompute
# ---------------------------------------------------------------------------

@_with_timeout("hourly_scoring")
async def job_hourly_scoring():
    """
    Recompute opportunity scores and regenerate the daily dashboard report.
    Runs the synchronous ScoringWorker in a thread-pool executor so the
    event loop is never blocked.
    """
    job_id = "hourly_scoring"
    t0 = _log_start(job_id)
    from app.workers.tasks import run_scoring_task  # local import

    try:
        await asyncio.to_thread(run_scoring_task)
        _log_done(job_id, t0)
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 10 min — precompute trending scores
# ---------------------------------------------------------------------------

@_with_timeout("opportunity_compute")
async def job_opportunity_compute():
    """
    Precompute today's Opportunity of the Day (with related apps + AI summary).
    Persists to both daily_opportunities and legacy DailyReport tables.
    Runs every 1 h (first run +5 min) so the /opportunity-of-day endpoint is
    always a fast read — no on-demand computation needed.
    """
    job_id = "opportunity_compute"
    t0 = _log_start(job_id)
    from app.database import SessionLocal
    from app.services.opportunity_of_day_service import OpportunityOfDayService

    db = SessionLocal()
    try:
        svc = OpportunityOfDayService(db)
        result = await asyncio.to_thread(svc.get_or_generate)
        if result:
            today = result.get("app_name", "unknown")
            _log_done(job_id, t0, f"opportunity computed (app={today})")
        else:
            _log_done(job_id, t0, "no qualifying opportunity (insufficient data)")
    except Exception as exc:
        _log_fail(job_id, exc)
    finally:
        db.close()


@_with_timeout("weekly_opportunities_compute")
async def job_weekly_opportunities_compute():
    """
    Precompute this week's Top-5 Opportunities (Mon–Sun ISO week).
    Runs every 6 h. On first call of the week it generates and persists 5 ranked
    rows; subsequent calls within the same week hit the cache immediately.
    """
    job_id = "weekly_opportunities_compute"
    t0 = _log_start(job_id)
    from app.database import SessionLocal
    from app.services.weekly_opportunities_service import WeeklyOpportunitiesService

    db = SessionLocal()
    try:
        svc = WeeklyOpportunitiesService(db)
        items = await asyncio.to_thread(svc.get_or_generate)
        _log_done(job_id, t0, f"weekly opportunities: {len(items)} items")
    except Exception as exc:
        _log_fail(job_id, exc)
    finally:
        db.close()


@_with_timeout("blowing_up_compute")
async def job_blowing_up_compute():
    """
    Precompute and persist 'blowing up' momentum scores for all apps that
    have at least 2 ranking snapshots in the last 7 days.
    Keeps the /apps/blowing-up endpoint fast (read-only table scan).
    """
    job_id = "blowing_up_compute"
    t0 = _log_start(job_id)
    from app.database import SessionLocal
    from app.services.blowing_up_service import BlowingUpService

    db = SessionLocal()
    try:
        count = await asyncio.to_thread(
            lambda: BlowingUpService(db).compute_for_all_apps(timeframe_days=7)
        )
        _log_done(job_id, t0, f"{count} apps scored")
    except Exception as exc:
        _log_fail(job_id, exc)
    finally:
        db.close()


@_with_timeout("trending_compute")
async def job_trending_compute():
    """
    Precompute and persist trending scores for all apps with recent ranking
    history.  Keeps the /trending endpoint fast (read-only table scan).
    """
    job_id = "trending_compute"
    t0 = _log_start(job_id)
    from app.database import SessionLocal  # local import avoids circular
    from app.services.trending_compute_service import compute_trending_scores

    db = SessionLocal()
    try:
        count = await asyncio.to_thread(compute_trending_scores, db)
        _log_done(job_id, t0, f"{count} apps scored")
    except Exception as exc:
        _log_fail(job_id, exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job: every 2 h — lightweight ranking refresh (chart RSS only)
#
# Fixes the ranking starvation bug: full_metadata has start_date=now+6h,
# so if the container restarts within 6h, Ranking rows are never created.
# This job fires at +3 min after startup and every 2h thereafter, calling
# ONLY scrape_top_charts().  Skips if fresh rankings exist (< 6h old).
# ---------------------------------------------------------------------------

_RANKING_FRESHNESS_HOURS = 6  # skip if newest ranking is younger than this


@_with_timeout("ranking_refresh")
async def job_ranking_refresh():
    """
    Lightweight ranking-only job.  Calls scrape_top_charts() for the two
    highest-value chart types (topfree + topgrossing) with categories=None
    (all-genres).  Skips entirely if rankings were created within the last
    _RANKING_FRESHNESS_HOURS.

    This is NOT a full metadata refresh — it touches ONLY the rankings table.
    """
    job_id = "ranking_refresh"
    t0 = _log_start(job_id)

    from app.database import SessionLocal
    from app.models.models import Ranking
    from sqlalchemy import func as sqla_func

    db = SessionLocal()
    try:
        # --- Freshness check: skip if recent rankings exist ---
        newest = db.query(sqla_func.max(Ranking.recorded_at)).scalar()
        if newest is not None:
            from datetime import timezone as _tz
            if newest.tzinfo is None:
                newest = newest.replace(tzinfo=_tz.utc)
            age_hours = (
                datetime.now(_tz.utc) - newest
            ).total_seconds() / 3600
            if age_hours < _RANKING_FRESHNESS_HOURS:
                _log_done(
                    job_id, t0,
                    f"SKIPPED — rankings are fresh ({age_hours:.1f}h old, "
                    f"threshold={_RANKING_FRESHNESS_HOURS}h)"
                )
                return
            logger.info(
                f"[{job_id}] Rankings are {age_hours:.1f}h old "
                f"(threshold={_RANKING_FRESHNESS_HOURS}h) — refreshing"
            )
        else:
            logger.info(f"[{job_id}] No rankings in DB — refreshing")
    finally:
        db.close()

    # --- Scrape charts (ranking rows only, no full metadata) ---
    from app.workers.tasks import ScraperWorker

    worker = ScraperWorker()
    await worker.initialize()
    try:
        await worker.scrape_top_charts(
            chart_types=["topfree", "topgrossing"],
            categories=[None],  # all-genres only — lightweight
        )

        # Count what we just created
        db2 = SessionLocal()
        try:
            from app.models.models import Ranking as R2
            recent_count = (
                db2.query(sqla_func.count(R2.id))
                .filter(R2.recorded_at >= datetime.utcnow() - timedelta(minutes=10))
                .scalar() or 0
            )
            _log_done(job_id, t0, f"{recent_count} ranking rows created")
        finally:
            db2.close()

    except Exception as exc:
        _log_fail(job_id, exc)
    finally:
        await worker.cleanup()


# ---------------------------------------------------------------------------
# Job: every 6 h — full app metadata refresh
# ---------------------------------------------------------------------------

@_with_timeout("full_metadata")
async def job_full_metadata():
    """
    Full re-scrape for all tracked apps:
    - App metadata (iTunes Lookup API)
    - Version history (App Store HTML, with iTunes fallback)
    - Reviews (iTunes RSS API)
    - Top chart rankings (iTunes RSS feed, category-based)
    """
    job_id = "full_metadata"
    t0 = _log_start(job_id)
    from app.workers.tasks import ScraperWorker

    worker = ScraperWorker()
    await worker.initialize()
    try:
        count = await worker.scrape_all_tracked_apps()
        logger.info(f"[SCHEDULER]    {job_id}: metadata done, updating chart rankings")
        try:
            await worker.scrape_top_charts(chart_types=["topfree", "topgrossing"])
        except Exception as exc:
            logger.warning(f"[SCHEDULER]    {job_id}: chart rankings skipped — {exc}")
        _log_done(job_id, t0, f"{count} apps fully scraped")
    except Exception as exc:
        _log_fail(job_id, exc)
    finally:
        await worker.cleanup()


# ---------------------------------------------------------------------------
# Job: every 6 h — keyword discovery (100+ keywords → discovery queue)
# ---------------------------------------------------------------------------

@_with_timeout("discovery_keywords")
async def job_discovery_keywords():
    """
    Run keyword search for all 100+ DISCOVERY_KEYWORDS not yet run today.
    Newly found app IDs are enqueued in discovery_queue for full scraping.
    """
    job_id = "discovery_keywords"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            engine = DiscoveryEngine(db)
            new_ids = await engine.run_keyword_discovery()
            _log_done(job_id, t0, f"{new_ids} new app IDs queued")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 2 h — chart discovery (all genres × all countries → queue)
# ---------------------------------------------------------------------------

@_with_timeout("discovery_charts")
async def job_discovery_charts():
    """
    Fetch the next batch of (chart × genre × country) combinations not yet
    run today. Each batch processes 12 chart pages → up to 2,400 app IDs.
    """
    job_id = "discovery_charts"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            engine = DiscoveryEngine(db)
            new_ids = await engine.run_chart_discovery_batch(batch_size=12)
            _log_done(job_id, t0, f"{new_ids} new app IDs queued")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 12 h — developer expansion (all apps per developer → queue)
# ---------------------------------------------------------------------------

@_with_timeout("discovery_developer")
async def job_discovery_developer():
    """
    For recently added apps whose developer hasn't been expanded yet,
    fetch all other apps by that developer and enqueue them.
    """
    job_id = "discovery_developer"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            engine = DiscoveryEngine(db)
            new_ids = await engine.run_developer_expansion(limit=100)
            _log_done(job_id, t0, f"{new_ids} new app IDs queued via developer expansion")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 30 min — queue processor (scrape queued app IDs)
# ---------------------------------------------------------------------------

@_with_timeout("queue_processor")
async def job_queue_processor():
    """
    Pick up to 100 pending items from the discovery queue, scrape full
    details (metadata + versions + reviews) with up to 10 concurrent
    workers, persist to apps table.
    """
    job_id = "queue_processor"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            engine = DiscoveryEngine(db)
            scraped = await engine.process_queue(batch_size=100, concurrency=10)
            _log_done(job_id, t0, f"{scraped} apps fully scraped from queue")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Scalable Ingestion Pipeline Jobs (500K target)
# ---------------------------------------------------------------------------

@_with_timeout("mass_discovery_light")
async def job_mass_discovery_light():
    """
    Run keyword discovery for 1000+ long-tail MASS_KEYWORDS.
    Uses the pre-filter (score >= 15) → light insert pipeline.
    Light inserts: sets ingestion_stage='light', deferred full enrichment.
    """
    job_id = "mass_discovery_light"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine, MASS_KEYWORDS
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            engine = DiscoveryEngine(db)
            stats = await engine.run_mass_keyword_discovery(MASS_KEYWORDS)
            _log_done(
                job_id, t0,
                f"discovered={stats['discovered']}, "
                f"filtered_out={stats['filtered_out']}, "
                f"inserted={stats['inserted']}"
            )
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


@_with_timeout("tier_reclassify")
async def job_tier_reclassify():
    """
    Reclassify all App rows into HOT / WARM / COLD tiers using a single
    SQL CASE WHEN UPDATE.  Skips rows updated < 6h ago.
    """
    job_id = "tier_reclassify"
    t0 = _log_start(job_id)
    try:
        from app.services.app_tiering_service import AppTieringService
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            updated = await asyncio.to_thread(AppTieringService(db).reclassify_all)
            _log_done(job_id, t0, f"{updated} rows reclassified")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


@_with_timeout("enrich_hot")
async def job_enrich_hot():
    """
    Enqueue HOT light-stage apps for full enrichment and process up to
    200 items with concurrency=15 (highest priority tier).
    """
    job_id = "enrich_hot"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            engine = DiscoveryEngine(db)
            enqueued = await asyncio.to_thread(
                engine._enqueue_light_apps_for_tier, "hot", 200
            )
            scraped = await engine.process_queue(batch_size=200, concurrency=15, tier="hot")
            _log_done(job_id, t0, f"enqueued={enqueued}, scraped={scraped}")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


@_with_timeout("enrich_warm")
async def job_enrich_warm():
    """
    Enqueue WARM light-stage apps for full enrichment and process up to
    500 items with concurrency=8.
    """
    job_id = "enrich_warm"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            engine = DiscoveryEngine(db)
            enqueued = await asyncio.to_thread(
                engine._enqueue_light_apps_for_tier, "warm", 500
            )
            scraped = await engine.process_queue(batch_size=500, concurrency=8, tier="warm")
            _log_done(job_id, t0, f"enqueued={enqueued}, scraped={scraped}")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


@_with_timeout("enrich_cold")
async def job_enrich_cold():
    """
    Enqueue COLD light-stage apps for full enrichment and process up to
    1000 items with concurrency=5 (background, lowest priority).
    """
    job_id = "enrich_cold"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            engine = DiscoveryEngine(db)
            enqueued = await asyncio.to_thread(
                engine._enqueue_light_apps_for_tier, "cold", 1000
            )
            scraped = await engine.process_queue(batch_size=1000, concurrency=5, tier="cold")
            _log_done(job_id, t0, f"enqueued={enqueued}, scraped={scraped}")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 6 h — keyword rank tracking (App Store search scraping)
# ---------------------------------------------------------------------------

@_with_timeout("keyword_rank_tracker")
async def job_keyword_rank_tracker():
    """
    For each tracked keyword: scrape real App Store search results,
    detect sponsored placements, save to keyword_search_snapshots.
    """
    job_id = "keyword_rank_tracker"
    t0 = _log_start(job_id)
    try:
        from app.jobs.keyword_rank_tracker import run_keyword_rank_tracker
        summary = await run_keyword_rank_tracker(country="us")
        _log_done(
            job_id, t0,
            f"{summary['keywords_scanned']} keywords, "
            f"{summary['total_results']} results, "
            f"{summary['sponsored_results']} sponsored"
        )
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 12 h — keyword intelligence pipeline (trends + Apple signals + scoring)
# ---------------------------------------------------------------------------

@_with_timeout("keyword_intelligence")
async def job_keyword_intelligence():
    """
    Full keyword intelligence pipeline:
    - Discover new keywords from Google Trends rising queries + seed list
    - Enrich with Google Trends (trend_score, trend_growth, trend_velocity)
    - Enrich with Apple App Store signals (apps_count, dominance_score)
    - Optionally enrich with DataForSEO (search_volume, difficulty, cpc)
    - Recompute opportunity_score + feasibility_score for all keywords
    """
    job_id = "keyword_intelligence"
    t0 = _log_start(job_id)
    try:
        from app.services.keyword_intelligence_pipeline import KeywordIntelligencePipeline
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            pipeline = KeywordIntelligencePipeline(db)
            summary = await pipeline.run_full_pipeline(max_keywords=5000)
            _log_done(
                job_id, t0,
                f"discovered={summary['discovered']}, "
                f"trends={summary['trends_updated']}, "
                f"apple={summary['apple_updated']}, "
                f"seo={summary['seo_updated']}, "
                f"scored={summary['scored']}",
            )
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 6 h — keyword scoring only (fast, no external API calls)
# ---------------------------------------------------------------------------

@_with_timeout("keyword_scoring")
async def job_keyword_scoring():
    """
    Recompute opportunity_score + feasibility_score for all keywords
    using existing stored signals (no external API calls — very fast).
    Runs more frequently than the full intelligence pipeline.
    """
    job_id = "keyword_scoring"
    t0 = _log_start(job_id)
    try:
        from app.services.keyword_intelligence_pipeline import KeywordIntelligencePipeline
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            pipeline = KeywordIntelligencePipeline(db)
            count = await pipeline.run_scoring_only()
            _log_done(job_id, t0, f"{count} keywords scored")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 24 h — keyword expansion engine (discover 10k-100k new keywords)
# ---------------------------------------------------------------------------

@_with_timeout("keyword_discovery")
async def job_keyword_discovery():
    """
    Run the keyword discovery engine to generate new keyword candidates:
    - Phase A: static alphabet/modifier expansion (~11k candidates)
    - Phase B: Apple MZSearchHints autocomplete suggestions (~21k)
    - Phase C: iTunes app metadata n-gram extraction (~39k)
    Persists new keywords to the keywords table for enrichment by the
    keyword_intelligence pipeline.
    """
    job_id = "keyword_discovery"
    t0 = _log_start(job_id)
    try:
        from app.services.keyword_discovery_engine import KeywordDiscoveryEngine
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            engine = KeywordDiscoveryEngine(db)
            stats = await engine.run_keyword_discovery()
            _log_done(
                job_id, t0,
                f"seeds={stats['seeds']}, candidates={stats['candidates']}, "
                f"inserted={stats['inserted']}, skipped={stats['skipped']}"
            )
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 24 h — per-app keyword discovery (autocomplete + affix expansion)
# ---------------------------------------------------------------------------

@_with_timeout("keyword_discovery_daily")
async def job_keyword_discovery_daily():
    """
    For each tracked app, discover new keyword candidates via:
    - Apple MZSearchHints autocomplete (from seed keywords)
    - Prefix/suffix affix expansions ("best {kw}", "{kw} app", …)
    Enriches each candidate with iTunes + Google Trends signals and
    stores results in app_discovered_keywords.
    Processes apps in batches of 10 to respect API rate limits.
    """
    job_id = "keyword_discovery_daily"
    t0 = _log_start(job_id)
    try:
        from app.services.keyword_discovery_service import KeywordDiscoveryService
        from app.database import SessionLocal
        from app.models.models import App

        db = SessionLocal()
        try:
            apps = db.query(App.id).order_by(App.id).all()
            app_ids = [row[0] for row in apps]
            total_discovered = 0
            BATCH = 10

            for i in range(0, len(app_ids), BATCH):
                batch = app_ids[i: i + BATCH]
                for app_id in batch:
                    batch_db = SessionLocal()
                    try:
                        svc = KeywordDiscoveryService(batch_db)
                        # discover_for_app is synchronous (DB + HTTP); run in a thread
                        # so the event loop stays free to serve API requests.
                        count = await asyncio.to_thread(svc.discover_for_app, app_id)
                        total_discovered += count
                    except Exception as exc:
                        logger.warning(f"[{job_id}] app {app_id} failed: {exc}")
                    finally:
                        batch_db.close()
                # brief pause between batches to avoid hammering APIs
                await asyncio.sleep(2)

            _log_done(job_id, t0, f"{len(app_ids)} apps, {total_discovered} new keywords")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 24 h — Phase-1 discovery (alphabet + competitor + gap + scoring)
# ---------------------------------------------------------------------------

@_with_timeout("keyword_discovery_phase1_daily")
async def job_keyword_discovery_phase1_daily():
    """
    For each tracked app, run the full Phase-1 keyword discovery pipeline:
      1. Alphabet mining  — seed × a-z × Apple autocomplete → enriched keywords
      2. Competitor mining — iTunes search for seeds → competitor n-gram phrases
      3. Gap analysis     — marks keyword_gap=True where competitor≤10 & we rank>30
      4. Opportunity score — recomputes opportunity_score for all discovered keywords

    Processes apps in batches of 10 with a 3-second pause between batches.
    """
    job_id = "keyword_discovery_phase1_daily"
    t0 = _log_start(job_id)
    try:
        from app.services.alphabet_mining_service import AlphabetMiningService
        from app.services.competitor_keyword_service import CompetitorKeywordService
        from app.services.keyword_gap_service import KeywordGapService
        from app.services.opportunity_service import OpportunityScoreService
        from app.database import SessionLocal
        from app.models.models import App

        db = SessionLocal()
        try:
            apps = db.query(App.id).order_by(App.id).all()
            app_ids = [row[0] for row in apps]
            db.close()
        except Exception:
            db.close()
            raise

        total_alpha = 0
        total_comp = 0
        total_gaps = 0
        BATCH = 10

        for i in range(0, len(app_ids), BATCH):
            batch = app_ids[i: i + BATCH]
            for app_id in batch:
                batch_db = SessionLocal()
                try:
                    logger.info(f"[{job_id}] Running Phase-1 discovery for app {app_id}")

                    # Each service call is synchronous (DB + HTTP); run in a thread
                    # so the event loop stays free to serve API requests.

                    # 1. Alphabet mining
                    alpha_svc = AlphabetMiningService(batch_db)
                    alpha_count = await asyncio.to_thread(alpha_svc.mine_for_app, app_id)
                    total_alpha += alpha_count

                    # 2. Competitor mining
                    comp_svc = CompetitorKeywordService(batch_db)
                    comp_count = await asyncio.to_thread(comp_svc.mine_for_app, app_id)
                    total_comp += comp_count

                    # 3. Gap analysis
                    gap_svc = KeywordGapService(batch_db)
                    gap_count = await asyncio.to_thread(gap_svc.analyze_for_app, app_id)
                    total_gaps += gap_count
                    logger.info(f"[{job_id}] Found {gap_count} gap keywords for app {app_id}")

                    # 4. Opportunity scoring
                    opp_svc = OpportunityScoreService(batch_db)
                    await asyncio.to_thread(opp_svc.score_for_app, app_id)

                except Exception as exc:
                    logger.warning(f"[{job_id}] app {app_id} failed: {exc}")
                finally:
                    batch_db.close()

            # Brief pause between batches to respect API rate limits
            await asyncio.sleep(3)

        _log_done(
            job_id, t0,
            f"{len(app_ids)} apps — alphabet={total_alpha}, "
            f"competitor={total_comp}, gaps={total_gaps}"
        )
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 24 h — keyword pruning (delete low-value stale rows)
# ---------------------------------------------------------------------------

@_with_timeout("keyword_cleanup_daily")
async def job_keyword_cleanup_daily():
    """
    Delete low-value keywords that have not been enriched and are stale.

    Cleanup rules
    -------------
    Global keywords table:
      DELETE WHERE search_volume = 0 AND last_updated < NOW() - 30 days

    App-specific discovered keywords:
      DELETE WHERE opportunity_score < 5 AND created_at < NOW() - 30 days
    """
    job_id = "keyword_cleanup_daily"
    t0 = _log_start(job_id)
    try:
        from app.database import SessionLocal
        from app.models.models import Keyword, AppDiscoveredKeyword
        from sqlalchemy import text

        db = SessionLocal()
        try:
            # ── 1. Prune global keywords ──────────────────────────────────
            result_kw = db.execute(
                text(
                    "DELETE FROM keywords "
                    "WHERE search_volume = 0 "
                    "AND last_updated < NOW() - INTERVAL '30 days'"
                )
            )
            deleted_kw = result_kw.rowcount or 0

            # ── 2. Prune app discovered keywords ──────────────────────────
            result_adk = db.execute(
                text(
                    "DELETE FROM app_discovered_keywords "
                    "WHERE opportunity_score < 5 "
                    "AND created_at < NOW() - INTERVAL '30 days'"
                )
            )
            deleted_adk = result_adk.rowcount or 0

            db.commit()

            _log_done(
                job_id, t0,
                f"removed {deleted_kw} stale keywords, "
                f"{deleted_adk} low-value discovered keywords"
            )
            if deleted_kw or deleted_adk:
                logger.info(
                    f"[KeywordCleanup] removed {deleted_kw} old keywords, "
                    f"{deleted_adk} low-value app keywords"
                )
        except Exception as exc:
            db.rollback()
            raise exc
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 24 h — keyword quality pruning (multi-rule DB cleanup)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Job: every 6 h — deep review ingestion (up to 500 reviews per app)
# ---------------------------------------------------------------------------

@_with_timeout("review_scraper")
async def job_review_scraper():
    """
    Fetch up to 500 reviews for the top 300 ranked apps (iTunes RSS pagination).
    New reviews are persisted; existing reviews (by review_id) are skipped.
    """
    job_id = "review_scraper"
    t0 = _log_start(job_id)
    try:
        from app.services.review_scraper_service import ReviewScraperService
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            svc = ReviewScraperService(db)
            stats = await svc.scrape_reviews_for_top_apps(limit=300)
            _log_done(
                job_id, t0,
                f"apps={stats['apps_processed']}, "
                f"+reviews={stats['new_reviews']}, "
                f"errors={stats['errors']}",
            )
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 1 h — rule-based sentiment classification
# ---------------------------------------------------------------------------

@_with_timeout("sentiment_analysis")
async def job_sentiment_analysis():
    """
    Classify all unclassified reviews (sentiment IS NULL) and roll up
    per-app averages into app_analytics.
    """
    job_id = "sentiment_analysis"
    t0 = _log_start(job_id)
    try:
        from app.services.review_sentiment_service import ReviewSentimentService
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            svc = ReviewSentimentService(db)
            classified = await asyncio.to_thread(svc.classify_pending_reviews)
            updated = await asyncio.to_thread(svc.update_all_app_analytics)
            _log_done(job_id, t0, f"classified={classified}, analytics_updated={updated}")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 2 h — feature gap analysis
# ---------------------------------------------------------------------------

@_with_timeout("feature_gap")
async def job_feature_gap():
    """
    Run FeatureGapAnalyzer for all apps with ≥5 reviews and upsert results
    into the feature_gaps table.
    """
    job_id = "feature_gap"
    t0 = _log_start(job_id)
    try:
        from app.services.feature_gap_service import FeatureGapService
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            svc = FeatureGapService(db)
            processed = await asyncio.to_thread(svc.compute_for_all_apps)
            _log_done(job_id, t0, f"{processed} apps processed")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 2 h — analytics update (growth + rating-change roll-up)
# ---------------------------------------------------------------------------

@_with_timeout("keyword_quality_pruning")
async def job_keyword_quality_pruning():
    """
    Multi-rule quality pruning for the global keywords table:
      1. Delete low-quality + stale keywords (quality_score < 30, unseen > 14 d)
      2. Delete PRUNED-status keywords (pipeline rejects)
      3. Delete orphaned weak keywords (no app links, not enriched recently)
      4. Delete weak alphabet keywords (score < 50, seen < 2 times)
      5. Delete zero-signal stale keywords (no Apple data, unseen > 90 d)
      6. Enforce global Tier-C cap (prune weakest until count < 850k)
    """
    job_id = "keyword_quality_pruning"
    t0 = _log_start(job_id)
    try:
        from app.workers.tasks import prune_keywords_job
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            stats = await asyncio.to_thread(prune_keywords_job, db)
            _log_done(
                job_id, t0,
                f"total_deleted={stats['total_deleted']}, "
                f"remaining={stats['remaining_keywords']}"
            )
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Growth Intelligence Jobs
# ---------------------------------------------------------------------------

@_with_timeout("ad_intelligence")
async def job_ad_intelligence():
    """
    Phase 3 of Growth Intelligence pipeline.
    Selects candidate apps showing momentum signals and runs ad detection
    (Apple Search Ads heuristic + Meta Ads Library if token available).
    Only processes apps already flagged by blowing_up_compute or trending_compute.
    """
    job_id = "ad_intelligence"
    t0 = _log_start(job_id)
    from app.database import SessionLocal
    from app.services.ad_intelligence_service import AdIntelligenceService
    import os

    db = SessionLocal()
    try:
        meta_token = os.environ.get("FACEBOOK_ACCESS_TOKEN")
        result = await asyncio.to_thread(
            lambda: AdIntelligenceService(db, meta_access_token=meta_token).run_for_candidates()
        )
        _log_done(job_id, t0, f"{result['candidates']} candidates, {result['creatives_upserted']} creatives")
    except Exception as exc:
        _log_fail(job_id, exc)
    finally:
        db.close()


@_with_timeout("campaign_detection")
async def job_campaign_detection():
    """
    Phase 4 of Growth Intelligence pipeline.
    Pure signal engine: classifies growth patterns from existing data.
    Consumes rankings, reviews, metric snapshots, and ad campaign data.
    No scraping — only reads existing tables.
    """
    job_id = "campaign_detection"
    t0 = _log_start(job_id)
    from app.database import SessionLocal
    from app.services.campaign_tracking_service import CampaignTrackingService

    db = SessionLocal()
    try:
        result = await asyncio.to_thread(
            lambda: CampaignTrackingService(db).run_for_all()
        )
        _log_done(job_id, t0, f"{result['events_created']} events created")
    except Exception as exc:
        _log_fail(job_id, exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# One-shot bootstrap: auto-create ranking snapshots if rankings table is empty
# ---------------------------------------------------------------------------

async def job_bootstrap_data():
    """
    One-shot job: if rankings table is empty but apps have current_rank,
    create initial ranking snapshots so trending/blowing-up pipelines can compute.
    Runs once at startup, then removes itself.
    """
    job_id = "bootstrap_data"
    t0 = _log_start(job_id)
    try:
        from app.database import SessionLocal
        from sqlalchemy import func as sqla_func
        from app.models.models import Ranking as RankingModel, App as AppModel

        db = SessionLocal()
        try:
            # Check if rankings already exist
            ranking_count = db.query(sqla_func.count(RankingModel.id)).scalar() or 0
            if ranking_count > 0:
                _log_done(job_id, t0, f"Rankings already exist ({ranking_count} rows) — skipping bootstrap")
                return

            # Check if there are apps with current_rank
            rankable = (
                db.query(sqla_func.count(AppModel.id))
                .filter(AppModel.current_rank.isnot(None), AppModel.current_rank > 0)
                .scalar() or 0
            )
            if rankable == 0:
                _log_done(job_id, t0, "No apps with current_rank — bootstrap skipped (run /admin/bootstrap first)")
                return

            logger.info(f"[{job_id}] Rankings empty but {rankable} apps have current_rank — bootstrapping...")
            from app.services.bootstrap_data_service import run_full_bootstrap
            result = await asyncio.to_thread(lambda: run_full_bootstrap(db))
            _log_done(job_id, t0, f"Bootstrap complete: {result}")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------

def setup_scheduler() -> AsyncIOScheduler:
    """
    Register all recurring jobs against the module-level scheduler instance.
    Must be called before scheduler.start().
    """
    now = datetime.utcnow()

    # ── One-shot: bootstrap ranking data if rankings table is empty ─────────
    # Runs 1 minute after startup, checks if bootstrap is needed, auto-removes.
    from apscheduler.triggers.date import DateTrigger
    scheduler.add_job(
        job_bootstrap_data,
        trigger=DateTrigger(run_date=now + timedelta(minutes=1), timezone="UTC"),
        id="bootstrap_data",
        name="One-shot: Auto-bootstrap ranking data if empty",
        max_instances=1,
        replace_existing=True,
    )

    # ── Ranking refresh: lightweight chart-only scrape — every 2 h ──────────
    # First run: 3 min after startup (fixes ranking starvation bug).
    # Skips if rankings are < 6h old.  Does NOT do full metadata enrichment.
    scheduler.add_job(
        job_ranking_refresh,
        trigger=IntervalTrigger(
            hours=2,
            start_date=now + timedelta(minutes=3),
            timezone="UTC",
        ),
        id="ranking_refresh",
        name="Every 2h: Ranking Refresh (chart RSS only)",
        **_JOB_DEFAULTS,
    )

    # ── Discovery: keyword search (100+ keywords → queue) — every 6 h ──────
    # First run staggered to 6 min (was 2 min — avoid startup storm).
    scheduler.add_job(
        job_discovery_keywords,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(minutes=6),
            timezone="UTC",
        ),
        id="discovery_keywords",
        name="Every 6h: Keyword Discovery → Queue",
        **_JOB_DEFAULTS,
    )

    # ── Discovery: chart scraping (all genres × countries → queue) — every 2 h
    # First run: 10 min after startup (was 5 — staggered).
    scheduler.add_job(
        job_discovery_charts,
        trigger=IntervalTrigger(
            hours=2,
            start_date=now + timedelta(minutes=10),
            timezone="UTC",
        ),
        id="discovery_charts",
        name="Every 2h: Chart Discovery → Queue",
        **_JOB_DEFAULTS,
    )

    # ── Discovery: developer expansion — every 12 h ────────────────────────
    # First run: 14 min after startup (was 10 — staggered).
    scheduler.add_job(
        job_discovery_developer,
        trigger=IntervalTrigger(
            hours=12,
            start_date=now + timedelta(minutes=14),
            timezone="UTC",
        ),
        id="discovery_developer",
        name="Every 12h: Developer Expansion → Queue",
        **_JOB_DEFAULTS,
    )

    # ── Queue processor: full scrape of queued app IDs — every 30 min ──────
    # First run: 15 min after startup (enough time for keywords/charts to queue some IDs).
    scheduler.add_job(
        job_queue_processor,
        trigger=IntervalTrigger(
            minutes=30,
            start_date=now + timedelta(minutes=15),
            timezone="UTC",
        ),
        id="queue_processor",
        name="Every 30min: Process Discovery Queue",
        **_JOB_DEFAULTS,
    )

    # ── every 1 h: quick reviews & ratings refresh ─────────────────────────
    scheduler.add_job(
        job_hourly_reviews_ratings,
        trigger=IntervalTrigger(
            hours=1,
            start_date=now + timedelta(hours=1),
            timezone="UTC",
        ),
        id="hourly_reviews_ratings",
        name="Every 1h: Reviews & Ratings Refresh",
        **_JOB_DEFAULTS,
    )

    # ── every 1 h: scoring recompute ───────────────────────────────────────
    scheduler.add_job(
        job_hourly_scoring,
        trigger=IntervalTrigger(
            hours=1,
            start_date=now + timedelta(minutes=65),
            timezone="UTC",
        ),
        id="hourly_scoring",
        name="Every 1h: Scoring & Analytics",
        **_JOB_DEFAULTS,
    )

    # ── every 6 h: full metadata refresh ───────────────────────────────────
    scheduler.add_job(
        job_full_metadata,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(hours=6),
            timezone="UTC",
        ),
        id="full_metadata",
        name="Every 6h: Full App Metadata",
        **_JOB_DEFAULTS,
    )

    # ── every 6 h: keyword rank tracking (App Store search scraping) ────────
    scheduler.add_job(
        job_keyword_rank_tracker,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(minutes=30),
            timezone="UTC",
        ),
        id="keyword_rank_tracker",
        name="Every 6h: Keyword Rank Tracking",
        **_JOB_DEFAULTS,
    )

    # ── every 12 h: full keyword intelligence pipeline ───────────────────────
    # First run: 8 min after startup (was 3 — staggered from discovery).
    scheduler.add_job(
        job_keyword_intelligence,
        trigger=IntervalTrigger(
            hours=12,
            start_date=now + timedelta(minutes=8),
            timezone="UTC",
        ),
        id="keyword_intelligence",
        name="Every 12h: Keyword Intelligence Pipeline",
        **_JOB_DEFAULTS,
    )

    # ── every 6 h: fast keyword scoring (no external API) ────────────────────
    # First run: 70 min after startup (after hourly_scoring so data is fresh).
    scheduler.add_job(
        job_keyword_scoring,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(minutes=70),
            timezone="UTC",
        ),
        id="keyword_scoring",
        name="Every 6h: Keyword Scoring",
        **_JOB_DEFAULTS,
    )

    # ── every 24 h: keyword discovery engine ─────────────────────────────────
    # First run: 20 min after startup so new keywords are available for
    # the intelligence pipeline's next scheduled run.
    scheduler.add_job(
        job_keyword_discovery,
        trigger=IntervalTrigger(
            hours=24,
            start_date=now + timedelta(minutes=20),
            timezone="UTC",
        ),
        id="keyword_discovery",
        name="Every 24h: Keyword Discovery Engine",
        **_JOB_DEFAULTS,
    )

    # ── every 24 h: per-app keyword discovery (autocomplete + affixes) ───────
    # First run: 25 min after startup (just after keyword_discovery).
    scheduler.add_job(
        job_keyword_discovery_daily,
        trigger=IntervalTrigger(
            hours=24,
            start_date=now + timedelta(minutes=25),
            timezone="UTC",
        ),
        id="keyword_discovery_daily",
        name="Every 24h: Per-App Keyword Discovery",
        **_JOB_DEFAULTS,
    )

    # ── every 24 h: Phase-1 keyword discovery (alphabet + competitor + gap) ──
    # First run: 30 min after startup (after keyword_discovery_daily starts).
    scheduler.add_job(
        job_keyword_discovery_phase1_daily,
        trigger=IntervalTrigger(
            hours=24,
            start_date=now + timedelta(minutes=30),
            timezone="UTC",
        ),
        id="keyword_discovery_phase1_daily",
        name="Every 24h: Phase-1 Alphabet+Competitor+Gap Discovery",
        **_JOB_DEFAULTS,
    )

    # ── every 1 h: precompute opportunity of the day ──────────────────────────
    # First run: 5 min after startup so the dashboard shows data soon after deploy.
    scheduler.add_job(
        job_opportunity_compute,
        trigger=IntervalTrigger(
            hours=1,
            start_date=now + timedelta(minutes=5),
            timezone="UTC",
        ),
        id="opportunity_compute",
        name="Every 1h: Precompute Opportunity of the Day",
        **_JOB_DEFAULTS,
    )

    # ── every 6 h: precompute weekly top-5 opportunities ─────────────────────
    # First run: 7 min after startup (after opportunity_compute starts).
    scheduler.add_job(
        job_weekly_opportunities_compute,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(minutes=7),
            timezone="UTC",
        ),
        id="weekly_opportunities_compute",
        name="Every 6h: Precompute Weekly Top-5 Opportunities",
        **_JOB_DEFAULTS,
    )

    # ── every 15 min: precompute blowing-up scores ────────────────────────────
    # First run: 4 min after startup (staggered from trending_compute at 2 min).
    scheduler.add_job(
        job_blowing_up_compute,
        trigger=IntervalTrigger(
            minutes=15,
            start_date=now + timedelta(minutes=4),
            timezone="UTC",
        ),
        id="blowing_up_compute",
        name="Every 15min: Precompute Blowing-Up Scores",
        **_JOB_DEFAULTS,
    )

    # ── every 10 min: precompute trending scores ─────────────────────────────
    # First run: 2 min after startup so the /trending endpoint serves data soon.
    scheduler.add_job(
        job_trending_compute,
        trigger=IntervalTrigger(
            minutes=10,
            start_date=now + timedelta(minutes=2),
            timezone="UTC",
        ),
        id="trending_compute",
        name="Every 10min: Precompute Trending Scores",
        **_JOB_DEFAULTS,
    )

    # ── every 24 h: keyword pruning / cleanup ────────────────────────────────
    # First run: 45 min after startup (well after discovery jobs have run).
    scheduler.add_job(
        job_keyword_cleanup_daily,
        trigger=IntervalTrigger(
            hours=24,
            start_date=now + timedelta(minutes=45),
            timezone="UTC",
        ),
        id="keyword_cleanup_daily",
        name="Every 24h: Keyword Cleanup (prune low-value stale keywords)",
        **_JOB_DEFAULTS,
    )

    # ── every 24 h: keyword quality pruning (multi-rule quality gate) ─────────
    # First run: 2 h after startup (after cleanup_daily and discovery jobs settle).
    scheduler.add_job(
        job_keyword_quality_pruning,
        trigger=IntervalTrigger(
            hours=24,
            start_date=now + timedelta(hours=2),
            timezone="UTC",
        ),
        id="keyword_quality_pruning",
        name="Every 24h: Keyword Quality Pruning (multi-rule quality gate)",
        **_JOB_DEFAULTS,
    )

    # ── every 6 h: deep review ingestion (500 reviews × top 300 apps) ───────
    # First run: 90 min after startup (after hourly refresh has run once).
    scheduler.add_job(
        job_review_scraper,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(minutes=90),
            timezone="UTC",
        ),
        id="review_scraper",
        name="Every 6h: Deep Review Ingestion",
        **_JOB_DEFAULTS,
    )

    # ── every 1 h: rule-based sentiment classification ────────────────────
    # First run: 35 min after startup (after initial reviews are present).
    scheduler.add_job(
        job_sentiment_analysis,
        trigger=IntervalTrigger(
            hours=1,
            start_date=now + timedelta(minutes=35),
            timezone="UTC",
        ),
        id="sentiment_analysis",
        name="Every 1h: Sentiment Classification + App Analytics",
        **_JOB_DEFAULTS,
    )

    # ── every 2 h: feature gap analysis ──────────────────────────────────
    # First run: 50 min after startup.
    scheduler.add_job(
        job_feature_gap,
        trigger=IntervalTrigger(
            hours=2,
            start_date=now + timedelta(minutes=50),
            timezone="UTC",
        ),
        id="feature_gap",
        name="Every 2h: Feature Gap Analysis",
        **_JOB_DEFAULTS,
    )

    # analytics_update: REMOVED — 100% redundant with sentiment_analysis
    # (both call ReviewSentimentService.update_all_app_analytics)

    # ── GROWTH INTELLIGENCE PIPELINE ──────────────────────────────────────────
    # Phase 3: Ad Intelligence — runs AFTER metric snapshots are fresh.
    # First run: 70 min (after hourly_scoring at 65 min).
    scheduler.add_job(
        job_ad_intelligence,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(minutes=70),
            timezone="UTC",
        ),
        id="ad_intelligence",
        name="Every 6h: Ad Intelligence (candidate-based ad detection)",
        **_JOB_DEFAULTS,
    )

    # Phase 4: Campaign detection — runs AFTER ad intelligence updates.
    # First run: 80 min (after ad_intelligence).
    scheduler.add_job(
        job_campaign_detection,
        trigger=IntervalTrigger(
            hours=2,
            start_date=now + timedelta(minutes=80),
            timezone="UTC",
        ),
        id="campaign_detection",
        name="Every 2h: Campaign / Growth Signal Detection",
        **_JOB_DEFAULTS,
    )

    # ── SCALABLE INGESTION PIPELINE (500K target) ──────────────────────────────
    # Mass keyword discovery with light insert — every 6h (reduced from 1h;
    # results are deduplicated and the discovery_keywords job already covers
    # the same keyword list every 6h).
    scheduler.add_job(
        job_mass_discovery_light,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(minutes=20),
            timezone="UTC",
        ),
        id="mass_discovery_light",
        name="Every 6h: Mass Keyword Discovery (light insert)",
        **_JOB_DEFAULTS,
    )

    # Tier reclassification — every 6h, first +25min
    scheduler.add_job(
        job_tier_reclassify,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(minutes=25),
            timezone="UTC",
        ),
        id="tier_reclassify",
        name="Every 6h: App Tier Reclassification (HOT/WARM/COLD)",
        **_JOB_DEFAULTS,
    )

    # HOT tier enrichment — every 1h, first +30min
    scheduler.add_job(
        job_enrich_hot,
        trigger=IntervalTrigger(
            hours=1,
            start_date=now + timedelta(minutes=30),
            timezone="UTC",
        ),
        id="enrich_hot",
        name="Every 1h: Enrich HOT tier light apps",
        **_JOB_DEFAULTS,
    )

    # WARM tier enrichment — every 6h, first +90min
    scheduler.add_job(
        job_enrich_warm,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(minutes=90),
            timezone="UTC",
        ),
        id="enrich_warm",
        name="Every 6h: Enrich WARM tier light apps",
        **_JOB_DEFAULTS,
    )

    # COLD tier enrichment — every 24h, first +4h
    scheduler.add_job(
        job_enrich_cold,
        trigger=IntervalTrigger(
            hours=24,
            start_date=now + timedelta(hours=4),
            timezone="UTC",
        ),
        id="enrich_cold",
        name="Every 24h: Enrich COLD tier light apps",
        **_JOB_DEFAULTS,
    )

    registered = [j.id for j in scheduler.get_jobs()]
    logger.info(f"[SCHEDULER] Registered {len(registered)} jobs: {registered}")
    return scheduler
