"""
Recurring scraping and scoring scheduler.

Job schedule (first run is offset from startup because the lifespan already
runs a full scrape; subsequent runs follow the interval exactly):

  Job ID                  Interval  First run after startup
  ──────────────────────  ────────  ─────────────────────────────
  hourly_reviews_ratings    1 h     1 h   (ratings, review count, new reviews)
  hourly_scoring            1 h     65 min (trails the reviews job by 5 min)
  full_metadata             6 h     6 h   (full metadata + version history)
  discovery                12 h    12 h   (keyword search + top charts)

To change an interval: edit the `hours=` / `minutes=` in setup_scheduler().
To disable a job:      comment out its scheduler.add_job() call.
To add a job:          define an async job function and add it below.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

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
# Job helpers
# ---------------------------------------------------------------------------

def _log_start(job_id: str) -> float:
    logger.info(f"[SCHEDULER] ▶  {job_id} started")
    return datetime.utcnow().timestamp()


def _log_done(job_id: str, t0: float, extra: str = ""):
    elapsed = datetime.utcnow().timestamp() - t0
    msg = f"[SCHEDULER] ✓  {job_id} finished in {elapsed:.1f}s"
    if extra:
        msg += f"  ({extra})"
    logger.info(msg)


def _log_fail(job_id: str, exc: Exception):
    logger.error(f"[SCHEDULER] ✗  {job_id} FAILED: {exc}", exc_info=True)


# ---------------------------------------------------------------------------
# Job: every 1 h — quick reviews & ratings refresh
# ---------------------------------------------------------------------------

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
# Job: every 6 h — full app metadata refresh
# ---------------------------------------------------------------------------

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
# Job: every 12 h — app discovery
# ---------------------------------------------------------------------------

_DISCOVERY_KEYWORDS = [
    "productivity", "ai", "chat", "fitness", "finance",
    "education", "game", "health", "travel", "music",
]


async def job_discovery():
    """
    Discover new apps via keyword search results and top charts.
    Newly found apps are added to the DB and picked up by subsequent
    metadata/review jobs.
    """
    job_id = "discovery"
    t0 = _log_start(job_id)
    from app.workers.tasks import ScraperWorker

    worker = ScraperWorker()
    await worker.initialize()
    try:
        await worker.scrape_search_results(_DISCOVERY_KEYWORDS)
        logger.info(f"[SCHEDULER]    {job_id}: keyword search done, attempting top charts")
        try:
            await worker.scrape_top_charts()
        except Exception as exc:
            logger.warning(f"[SCHEDULER]    {job_id}: top charts skipped — {exc}")
        _log_done(job_id, t0)
    except Exception as exc:
        _log_fail(job_id, exc)
    finally:
        await worker.cleanup()


# ---------------------------------------------------------------------------
# Job: every 6 h — keyword rank tracking (App Store search scraping)
# ---------------------------------------------------------------------------

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
# Scheduler setup
# ---------------------------------------------------------------------------

def setup_scheduler() -> AsyncIOScheduler:
    """
    Register all recurring jobs against the module-level scheduler instance.
    Must be called before scheduler.start().
    """
    now = datetime.utcnow()

    # ── every 1 h: quick reviews & ratings refresh ─────────────────────────
    # First run: 1 h after startup (startup already ran a full scrape)
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
    # First run: 65 min after startup so it trails the reviews job by 5 min
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

    # ── every 12 h: app discovery ──────────────────────────────────────────
    scheduler.add_job(
        job_discovery,
        trigger=IntervalTrigger(
            hours=12,
            start_date=now + timedelta(hours=12),
            timezone="UTC",
        ),
        id="discovery",
        name="Every 12h: App Discovery",
        **_JOB_DEFAULTS,
    )

    # ── every 6 h: keyword rank tracking ───────────────────────────────────
    # First run: 30 min after startup (light enough to run early)
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

    registered = [j.id for j in scheduler.get_jobs()]
    logger.info(f"[SCHEDULER] Registered jobs: {registered}")
    return scheduler
