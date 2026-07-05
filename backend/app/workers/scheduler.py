"""
Recurring scraping, scoring, and discovery scheduler.

Job schedule:

  Job ID                   Interval  First run   Purpose
  ───────────────────────  ────────  ──────────  ─────────────────────────────────────────
  ranking_refresh            2 h      3 min       Chart RSS → ranking rows (skip if fresh)
  opportunity_compute        1 h      5 min       Precompute opportunity of the day → daily_reports
  blowing_up_compute         30 min   4 min       Precompute blowing-up scores → app_blowing_up_scores
  trending_compute           30 min   2 min       Precompute trending scores → app_trending_scores
  discovery_keywords         6 h      2 min       100+ keyword search → queue
  discovery_charts           2 h      5 min       Charts × all genres × 20 countries → queue
  discovery_developer        12 h     10 min      Developer expansion → queue
  queue_processor            30 min   15 min      Process discovery queue (full scrape)
  hourly_reviews_ratings     1 h      1 h         Quick refresh (rating/reviews for all apps)
  hourly_scoring             1 h      65 min      Recompute scores + daily report
  full_metadata              6 h      6 h         Full metadata refresh for all tracked apps
  keyword_discovery          24 h      2 min      Keyword expansion engine (10k-100k keywords)
  keyword_discovery_daily    24 h     25 min      Per-app keyword discovery (200 apps/run, resumable)
  keyword_discovery_phase1   24 h     30 min      Phase-1 discovery: alphabet+competitor+gap (50 apps/run)
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
import time
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
    "country_charts": 1800,           # 30 min (per-country charts for Tier-1)
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

# ---------------------------------------------------------------------------
# Resumable-batch cursors — track the last-processed App.id so each run
# picks up where the previous one left off.  Reset on container restart,
# which is fine: the jobs cycle through all apps over multiple runs anyway.
# ---------------------------------------------------------------------------
_kw_discovery_daily_cursor: int = 0
_kw_discovery_phase1_cursor: int = 0


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
            except asyncio.CancelledError:
                m["fail"] += 1
                logger.warning(
                    f"[SCHEDULER] {job_id} CANCELLED "
                    f"(runs={m['runs']}, ok={m['ok']}, fail={m['fail']})"
                )
                raise
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
# Thread-owned DB session
# ---------------------------------------------------------------------------

def _run_in_thread_with_session(fn, *args, **kwargs):
    """Run ``fn(session, *args, **kwargs)`` in a worker thread with a
    SQLAlchemy Session that the thread creates, exclusively owns, and closes.

    Creating the Session *inside* the thread (never in the calling coroutine)
    guarantees two invariants for every scheduler job that offloads DB work:

      * A Session is never shared across threads.
      * A coroutine timeout/cancellation (via ``_with_timeout`` →
        ``asyncio.wait_for``) can never close a Session while the worker
        thread is still using it — the coroutine holds no reference to it, so
        the thread always creates, owns and disposes its own Session.

    Transaction handling mirrors the previous ``finally: db.close()`` contract:
    the invoked services commit their own work internally, so no commit is
    added here; on any exception the pending transaction is explicitly rolled
    back before the Session is closed (``close()`` alone already discards an
    open transaction, but the explicit rollback makes intent unambiguous).

    Returns the ``asyncio.to_thread`` awaitable — ``await`` it like
    ``asyncio.to_thread(...)``.
    """
    from app.database import SessionLocal

    def _runner():
        db = SessionLocal()
        try:
            return fn(db, *args, **kwargs)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return asyncio.to_thread(_runner)


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
        # 45 min wall-time budget (job timeout is 3600s / 1h).
        # Apps are sorted by freshness_score DESC, so highest-priority
        # apps are always refreshed first even if time runs out.
        count = await worker.scrape_quick_refresh_all(max_wall_time=2700)
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
    from app.services.opportunity_of_day_service import OpportunityOfDayService

    try:
        result = await _run_in_thread_with_session(
            lambda db: OpportunityOfDayService(db).get_or_generate()
        )
        if result:
            today = result.get("app_name", "unknown")
            _log_done(job_id, t0, f"opportunity computed (app={today})")
        else:
            _log_done(job_id, t0, "no qualifying opportunity (insufficient data)")
    except Exception as exc:
        _log_fail(job_id, exc)


@_with_timeout("weekly_opportunities_compute")
async def job_weekly_opportunities_compute():
    """
    Precompute this week's Top-5 Opportunities (Mon–Sun ISO week).
    Runs every 6 h. On first call of the week it generates and persists 5 ranked
    rows; subsequent calls within the same week hit the cache immediately.
    """
    job_id = "weekly_opportunities_compute"
    t0 = _log_start(job_id)
    from app.services.weekly_opportunities_service import WeeklyOpportunitiesService

    try:
        items = await _run_in_thread_with_session(
            lambda db: WeeklyOpportunitiesService(db).get_or_generate()
        )
        _log_done(job_id, t0, f"weekly opportunities: {len(items)} items")
    except Exception as exc:
        _log_fail(job_id, exc)


@_with_timeout("blowing_up_compute")
async def job_blowing_up_compute():
    """
    Precompute and persist 'blowing up' momentum scores for all apps that
    have at least 2 ranking snapshots in the last 7 days.
    Keeps the /apps/blowing-up endpoint fast (read-only table scan).
    """
    job_id = "blowing_up_compute"
    t0 = _log_start(job_id)
    from app.services.blowing_up_service import BlowingUpService

    try:
        count = await _run_in_thread_with_session(
            lambda db: BlowingUpService(db).compute_for_all_apps(timeframe_days=7)
        )
        _log_done(job_id, t0, f"{count} apps scored")
    except Exception as exc:
        _log_fail(job_id, exc)


@_with_timeout("trending_compute")
async def job_trending_compute():
    """
    Precompute and persist trending scores for all apps with recent ranking
    history.  Keeps the /trending endpoint fast (read-only table scan).
    """
    job_id = "trending_compute"
    t0 = _log_start(job_id)
    from app.services.trending_compute_service import compute_trending_scores

    try:
        count = await _run_in_thread_with_session(compute_trending_scores)
        _log_done(job_id, t0, f"{count} apps scored")
    except Exception as exc:
        _log_fail(job_id, exc)


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

    from app.models.models import Ranking
    from sqlalchemy import func as sqla_func

    # --- Freshness check: skip if recent rankings exist (query off-loop) ---
    newest = await _run_in_thread_with_session(
        lambda db: db.query(sqla_func.max(Ranking.recorded_at)).scalar()
    )
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

    # --- Scrape charts (ranking rows only, no full metadata) ---
    from app.workers.tasks import ScraperWorker

    worker = ScraperWorker()
    await worker.initialize()
    try:
        await worker.scrape_top_charts(
            chart_types=["topfree", "topgrossing"],
            categories=[None],  # all-genres only — lightweight
        )

        # Count what we just created (query off-loop)
        from app.models.models import Ranking as R2
        recent_count = await _run_in_thread_with_session(
            lambda db: (
                db.query(sqla_func.count(R2.id))
                .filter(R2.recorded_at >= datetime.utcnow() - timedelta(minutes=10))
                .scalar() or 0
            )
        )
        _log_done(job_id, t0, f"{recent_count} ranking rows created")

    except Exception as exc:
        _log_fail(job_id, exc)
    finally:
        await worker.cleanup()


# ---------------------------------------------------------------------------
# Job: every 6 h — per-country top charts (Tier-1 storefronts)
# ---------------------------------------------------------------------------

_COUNTRY_CHART_BATCH = 25  # max storefronts refreshed per run (bounds request cost)


@_with_timeout("country_charts")
async def job_country_charts():
    """
    Fetch top charts (free + grossing, all-genres) for the most-overdue
    storefronts and write per-country ranking rows.

    SLA-weighted rotation over ALL enabled storefronts: a country is "due" once
    it hasn't been covered within its tier's sla_hours; each run picks up to
    _COUNTRY_CHART_BATCH of the most-overdue (by staleness ratio =
    hours_since_covered / sla_hours). High tiers (short SLA) refresh often; a
    never-covered / long-overdue country has an ever-growing ratio and is always
    eventually picked, so no country starves. US is covered by ranking_refresh.
    """
    job_id = "country_charts"
    t0 = _log_start(job_id)
    try:
        from sqlalchemy import text as _sa_text

        def _due_countries(db):
            rows = db.execute(
                _sa_text(
                    """
                    SELECT code FROM countries
                    WHERE enabled AND code <> 'us'
                      AND (charts_last_covered_at IS NULL
                           OR now() - charts_last_covered_at > make_interval(hours => sla_hours))
                    ORDER BY
                      EXTRACT(EPOCH FROM (now() - COALESCE(charts_last_covered_at, 'epoch'::timestamptz)))
                      / GREATEST(sla_hours, 1) DESC
                    LIMIT :lim
                    """
                ),
                {"lim": _COUNTRY_CHART_BATCH},
            ).scalars().all()
            return list(rows)

        codes = await _run_in_thread_with_session(_due_countries)
        if not codes:
            _log_done(job_id, t0, "no storefronts due for refresh")
            return

        def _mark_covered(db, cc):
            db.execute(
                _sa_text("UPDATE countries SET charts_last_covered_at = now() WHERE code = :c"),
                {"c": cc},
            )
            db.commit()

        from app.workers.tasks import ScraperWorker
        worker = ScraperWorker()
        await worker.initialize()
        try:
            done = 0
            for cc in codes:
                await worker.scrape_top_charts(
                    chart_types=["topfree", "topgrossing"],
                    categories=[None],
                    country=cc,
                )
                # Mark covered per-country so a mid-run timeout is resumable.
                await _run_in_thread_with_session(_mark_covered, cc)
                done += 1
                await asyncio.sleep(0.5)  # gentle pacing between storefronts
            _log_done(job_id, t0, f"top charts fetched for {done}/{len(codes)} due storefronts: {codes}")
        finally:
            await worker.cleanup()
    except Exception as exc:
        _log_fail(job_id, exc)


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
# Job: every 2 h — backfill incomplete apps (missing description/screenshots)
# ---------------------------------------------------------------------------

@_with_timeout("backfill_incomplete")
async def job_backfill_incomplete():
    """
    Fast bulk backfill for apps missing metadata (no description).
    Uses iTunes batch lookup API (200 IDs per request) for ~100x speed vs
    individual full scrapes.  Processes up to 1000 apps per run.
    """
    job_id = "backfill_incomplete"
    t0 = _log_start(job_id)
    import urllib.request
    import json as _json
    from app.models.models import App

    def _backfill(db):
        # Entire batch loop — including the blocking urlopen(timeout=30) — runs
        # in a worker thread so the event loop is never blocked. Per-batch
        # commits and behaviour are preserved exactly.
        total_updated = 0
        max_apps = 1000
        while total_updated < max_apps:
            rows = (
                db.query(App)
                .filter(App.description.is_(None))
                .order_by(App.created_at.desc())
                .limit(200)
                .all()
            )
            if not rows:
                break

            store_ids = [a.app_id for a in rows]
            app_map = {str(a.app_id): a for a in rows}

            ids_param = ",".join(str(sid) for sid in store_ids)
            url = f"https://itunes.apple.com/lookup?id={ids_param}&country=us&entity=software"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "RankSpy/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = _json.loads(resp.read().decode())
            except Exception as e:
                logger.warning(f"[SCHEDULER]    {job_id}: iTunes batch lookup failed: {e}")
                break

            results = data.get("results", [])
            batch_updated = 0
            for r in results:
                track_id = str(r.get("trackId", ""))
                app_obj = app_map.get(track_id)
                if not app_obj:
                    continue
                app_obj.description = r.get("description") or app_obj.description
                app_obj.subtitle = r.get("subtitle") or app_obj.subtitle
                app_obj.developer = r.get("sellerName") or r.get("artistName") or app_obj.developer
                app_obj.icon_url = r.get("artworkUrl512") or r.get("artworkUrl100") or app_obj.icon_url
                genres = r.get("genres", [])
                app_obj.primary_category = r.get("primaryGenreName") or (genres[0] if genres else None) or app_obj.primary_category
                app_obj.current_rating = r.get("averageUserRating") or app_obj.current_rating
                app_obj.current_reviews = r.get("userRatingCount") or app_obj.current_reviews or 0
                app_obj.current_version = r.get("version") or app_obj.current_version
                app_obj.is_free = r.get("price", 0) == 0
                app_obj.price = r.get("price", 0)
                screenshots = r.get("screenshotUrls", []) + r.get("ipadScreenshotUrls", [])
                if screenshots:
                    app_obj.screenshots = screenshots
                if r.get("releaseDate"):
                    try:
                        from datetime import datetime as _dt, timezone as _tz
                        app_obj.release_date = _dt.fromisoformat(r["releaseDate"].replace("Z", "+00:00"))
                    except Exception:
                        pass
                if r.get("currentVersionReleaseDate"):
                    try:
                        from datetime import datetime as _dt
                        app_obj.last_updated = _dt.fromisoformat(r["currentVersionReleaseDate"].replace("Z", "+00:00"))
                    except Exception:
                        pass
                app_obj.url = r.get("trackViewUrl") or app_obj.url
                batch_updated += 1

            # Mark apps that weren't in iTunes results (removed from store)
            for sid in store_ids:
                if str(sid) not in {str(r.get("trackId", "")) for r in results}:
                    orphan = app_map.get(str(sid))
                    if orphan and not orphan.description:
                        orphan.description = "(Removed from App Store)"

            db.commit()
            total_updated += batch_updated
            logger.info(f"[SCHEDULER]    {job_id}: batch {batch_updated} updated, {total_updated} total")

        return total_updated

    try:
        total_updated = await _run_in_thread_with_session(_backfill)
        _log_done(job_id, t0, f"{total_updated} apps backfilled via iTunes batch lookup")
    except Exception as exc:
        _log_fail(job_id, exc)


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
            scraped = await engine.process_queue(batch_size=100, concurrency=5)
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
        updated = await _run_in_thread_with_session(
            lambda db: AppTieringService(db).reclassify_all()
        )
        _log_done(job_id, t0, f"{updated} rows reclassified")
    except Exception as exc:
        _log_fail(job_id, exc)


@_with_timeout("enrich_hot")
async def job_enrich_hot():
    """
    Enqueue HOT light-stage apps for full enrichment and process up to
    200 items with concurrency=5 (highest priority tier).
    """
    job_id = "enrich_hot"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine
        from app.database import SessionLocal
        # Phase 1: enqueue (quick DB operation) — thread owns its own session
        enqueued = await _run_in_thread_with_session(
            lambda db: DiscoveryEngine(db)._enqueue_light_apps_for_tier("hot", 200)
        )
        # Phase 2: scrape (long HTTP I/O) — fresh session for queue reads
        db2 = SessionLocal()
        try:
            engine2 = DiscoveryEngine(db2)
            scraped = await engine2.process_queue(batch_size=200, concurrency=5, tier="hot")
            _log_done(job_id, t0, f"enqueued={enqueued}, scraped={scraped}")
        finally:
            db2.close()
    except Exception as exc:
        _log_fail(job_id, exc)


@_with_timeout("enrich_warm")
async def job_enrich_warm():
    """
    Enqueue WARM light-stage apps for full enrichment and process up to
    500 items with concurrency=5.
    """
    job_id = "enrich_warm"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine
        from app.database import SessionLocal
        enqueued = await _run_in_thread_with_session(
            lambda db: DiscoveryEngine(db)._enqueue_light_apps_for_tier("warm", 500)
        )
        db2 = SessionLocal()
        try:
            engine2 = DiscoveryEngine(db2)
            scraped = await engine2.process_queue(batch_size=500, concurrency=5, tier="warm")
            _log_done(job_id, t0, f"enqueued={enqueued}, scraped={scraped}")
        finally:
            db2.close()
    except Exception as exc:
        _log_fail(job_id, exc)


@_with_timeout("enrich_cold")
async def job_enrich_cold():
    """
    Enqueue COLD light-stage apps for full enrichment and process up to
    1000 items with concurrency=3 (background, lowest priority).
    """
    job_id = "enrich_cold"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine
        from app.database import SessionLocal
        enqueued = await _run_in_thread_with_session(
            lambda db: DiscoveryEngine(db)._enqueue_light_apps_for_tier("cold", 1000)
        )
        db2 = SessionLocal()
        try:
            engine2 = DiscoveryEngine(db2)
            scraped = await engine2.process_queue(batch_size=1000, concurrency=3, tier="cold")
            _log_done(job_id, t0, f"enqueued={enqueued}, scraped={scraped}")
        finally:
            db2.close()
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
    Per-app keyword discovery via Apple autocomplete + affix expansions.

    Batch-limited & resumable: processes up to MAX_APPS apps per run,
    resuming from the last-processed App.id.  A wall-time budget prevents
    the job from exceeding its timeout even if individual HTTP calls are slow.
    Over successive daily runs, every app in the database is eventually covered.
    """
    global _kw_discovery_daily_cursor
    job_id = "keyword_discovery_daily"
    t0 = _log_start(job_id)

    MAX_APPS = 200          # apps per run (8000 apps → covered in ~40 runs)
    WALL_TIME_BUDGET = 6000  # 100 min hard stop (timeout is 7200s)
    BATCH = 10

    try:
        from app.services.keyword_discovery_service import KeywordDiscoveryService
        from app.database import SessionLocal
        from app.models.models import App

        # ── Load the next chunk of app IDs from the cursor ────────────────
        db = SessionLocal()
        try:
            apps = (
                db.query(App.id)
                .filter(App.id > _kw_discovery_daily_cursor)
                .order_by(App.id)
                .limit(MAX_APPS)
                .all()
            )
            if not apps:
                # Wrapped around — start from the beginning
                _kw_discovery_daily_cursor = 0
                apps = (
                    db.query(App.id)
                    .order_by(App.id)
                    .limit(MAX_APPS)
                    .all()
                )
            app_ids = [row[0] for row in apps]
        finally:
            db.close()

        if not app_ids:
            _log_done(job_id, t0, "no apps found")
            return

        logger.info(
            f"[{job_id}] Processing {len(app_ids)} apps "
            f"(cursor={_kw_discovery_daily_cursor}, range={app_ids[0]}..{app_ids[-1]})"
        )

        # ── Process apps in small batches ─────────────────────────────────
        total_discovered = 0
        processed = 0
        last_id = _kw_discovery_daily_cursor
        wall_start = time.monotonic()

        for i in range(0, len(app_ids), BATCH):
            if time.monotonic() - wall_start > WALL_TIME_BUDGET:
                logger.warning(
                    f"[{job_id}] Wall-time budget ({WALL_TIME_BUDGET}s) hit "
                    f"after {processed}/{len(app_ids)} apps — stopping early"
                )
                break

            batch = app_ids[i: i + BATCH]
            for app_id in batch:
                try:
                    count = await _run_in_thread_with_session(
                        lambda db, aid=app_id: KeywordDiscoveryService(db).discover_for_app(aid)
                    )
                    total_discovered += count
                except Exception as exc:
                    logger.warning(f"[{job_id}] app {app_id} failed: {exc}")
                processed += 1
                last_id = app_id
            await asyncio.sleep(2)

        _kw_discovery_daily_cursor = last_id
        _log_done(
            job_id, t0,
            f"{processed}/{len(app_ids)} apps (cursor→{last_id}), "
            f"{total_discovered} new keywords"
        )
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Job: every 24 h — Phase-1 discovery (alphabet + competitor + gap + scoring)
# ---------------------------------------------------------------------------

@_with_timeout("keyword_discovery_phase1_daily")
async def job_keyword_discovery_phase1_daily():
    """
    Phase-1 keyword discovery: alphabet mining, competitor mining, gap
    analysis, and opportunity scoring for each app.

    Batch-limited & resumable: processes up to MAX_APPS apps per run
    (4 HTTP-heavy service calls per app), resuming from the last cursor.
    Wall-time budget prevents exceeding timeout.
    """
    global _kw_discovery_phase1_cursor
    job_id = "keyword_discovery_phase1_daily"
    t0 = _log_start(job_id)

    MAX_APPS = 50            # 4 calls/app → ~50 apps keeps runtime under 30 min
    WALL_TIME_BUDGET = 6000  # 100 min hard stop (timeout is 7200s)
    BATCH = 10

    try:
        from app.services.alphabet_mining_service import AlphabetMiningService
        from app.services.competitor_keyword_service import CompetitorKeywordService
        from app.services.keyword_gap_service import KeywordGapService
        from app.services.opportunity_service import OpportunityScoreService
        from app.database import SessionLocal
        from app.models.models import App

        # ── Load the next chunk of app IDs from the cursor ────────────────
        db = SessionLocal()
        try:
            apps = (
                db.query(App.id)
                .filter(App.id > _kw_discovery_phase1_cursor)
                .order_by(App.id)
                .limit(MAX_APPS)
                .all()
            )
            if not apps:
                _kw_discovery_phase1_cursor = 0
                apps = (
                    db.query(App.id)
                    .order_by(App.id)
                    .limit(MAX_APPS)
                    .all()
                )
            app_ids = [row[0] for row in apps]
        finally:
            db.close()

        if not app_ids:
            _log_done(job_id, t0, "no apps found")
            return

        logger.info(
            f"[{job_id}] Processing {len(app_ids)} apps "
            f"(cursor={_kw_discovery_phase1_cursor}, range={app_ids[0]}..{app_ids[-1]})"
        )

        # ── Process apps in small batches ─────────────────────────────────
        total_alpha = 0
        total_comp = 0
        total_gaps = 0
        processed = 0
        last_id = _kw_discovery_phase1_cursor
        wall_start = time.monotonic()

        def _run_phase1(db, aid):
            # All four steps share ONE thread-owned session (same semantics as
            # the previous single per-app session), run sequentially in-thread.
            a = AlphabetMiningService(db).mine_for_app(aid)
            c = CompetitorKeywordService(db).mine_for_app(aid)
            g = KeywordGapService(db).analyze_for_app(aid)
            OpportunityScoreService(db).score_for_app(aid)
            return a, c, g

        for i in range(0, len(app_ids), BATCH):
            if time.monotonic() - wall_start > WALL_TIME_BUDGET:
                logger.warning(
                    f"[{job_id}] Wall-time budget ({WALL_TIME_BUDGET}s) hit "
                    f"after {processed}/{len(app_ids)} apps — stopping early"
                )
                break

            batch = app_ids[i: i + BATCH]
            for app_id in batch:
                try:
                    alpha_count, comp_count, gap_count = await _run_in_thread_with_session(
                        _run_phase1, app_id
                    )
                    total_alpha += alpha_count
                    total_comp += comp_count
                    total_gaps += gap_count
                except Exception as exc:
                    logger.warning(f"[{job_id}] app {app_id} failed: {exc}")
                processed += 1
                last_id = app_id
            await asyncio.sleep(3)

        _kw_discovery_phase1_cursor = last_id
        _log_done(
            job_id, t0,
            f"{processed}/{len(app_ids)} apps (cursor→{last_id}) — "
            f"alphabet={total_alpha}, competitor={total_comp}, gaps={total_gaps}"
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
        from sqlalchemy import text

        def _cleanup(db):
            # Bulk DELETEs (potentially seconds on a large keywords table) +
            # commit run in a worker thread so the event loop is not blocked.
            result_kw = db.execute(
                text(
                    "DELETE FROM keywords "
                    "WHERE search_volume = 0 "
                    "AND last_updated < NOW() - INTERVAL '30 days'"
                )
            )
            deleted_kw = result_kw.rowcount or 0

            result_adk = db.execute(
                text(
                    "DELETE FROM app_discovered_keywords "
                    "WHERE opportunity_score < 5 "
                    "AND created_at < NOW() - INTERVAL '30 days'"
                )
            )
            deleted_adk = result_adk.rowcount or 0

            db.commit()
            return deleted_kw, deleted_adk

        deleted_kw, deleted_adk = await _run_in_thread_with_session(_cleanup)
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

        def _run_sentiment(db):
            # Both steps share ONE thread-owned session (same as before).
            svc = ReviewSentimentService(db)
            classified = svc.classify_pending_reviews()
            updated = svc.update_all_app_analytics()
            return classified, updated

        classified, updated = await _run_in_thread_with_session(_run_sentiment)
        _log_done(job_id, t0, f"classified={classified}, analytics_updated={updated}")
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

        processed = await _run_in_thread_with_session(
            lambda db: FeatureGapService(db).compute_for_all_apps()
        )
        _log_done(job_id, t0, f"{processed} apps processed")
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

        stats = await _run_in_thread_with_session(prune_keywords_job)
        _log_done(
            job_id, t0,
            f"total_deleted={stats['total_deleted']}, "
            f"remaining={stats['remaining_keywords']}"
        )
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
    from app.services.ad_intelligence_service import AdIntelligenceService
    import os

    meta_token = os.environ.get("FACEBOOK_ACCESS_TOKEN")
    try:
        result = await _run_in_thread_with_session(
            lambda db: AdIntelligenceService(db, meta_access_token=meta_token).run_for_candidates()
        )
        _log_done(job_id, t0, f"{result['candidates']} candidates, {result['creatives_upserted']} creatives")
    except Exception as exc:
        _log_fail(job_id, exc)


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
    from app.services.campaign_tracking_service import CampaignTrackingService

    try:
        result = await _run_in_thread_with_session(
            lambda db: CampaignTrackingService(db).run_for_all()
        )
        _log_done(job_id, t0, f"{result['events_created']} events created")
    except Exception as exc:
        _log_fail(job_id, exc)


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
        from sqlalchemy import func as sqla_func
        from app.models.models import Ranking as RankingModel, App as AppModel
        from app.services.bootstrap_data_service import run_full_bootstrap

        def _bootstrap(db):
            # Pre-checks + bootstrap all run in one thread-owned session.
            # Returns (status, payload) so the coroutine can log without
            # touching the session.
            ranking_count = db.query(sqla_func.count(RankingModel.id)).scalar() or 0
            if ranking_count > 0:
                return ("skip_existing", ranking_count)
            rankable = (
                db.query(sqla_func.count(AppModel.id))
                .filter(AppModel.current_rank.isnot(None), AppModel.current_rank > 0)
                .scalar() or 0
            )
            if rankable == 0:
                return ("skip_norank", 0)
            logger.info(f"[{job_id}] Rankings empty but {rankable} apps have current_rank — bootstrapping...")
            return ("done", run_full_bootstrap(db))

        status, payload = await _run_in_thread_with_session(_bootstrap)
        if status == "skip_existing":
            _log_done(job_id, t0, f"Rankings already exist ({payload} rows) — skipping bootstrap")
        elif status == "skip_norank":
            _log_done(job_id, t0, "No apps with current_rank — bootstrap skipped (run /admin/bootstrap first)")
        else:
            _log_done(job_id, t0, f"Bootstrap complete: {payload}")
    except Exception as exc:
        _log_fail(job_id, exc)


# ---------------------------------------------------------------------------
# Alert evaluation
# ---------------------------------------------------------------------------

async def job_evaluate_alerts():
    """Evaluate user-defined alert rules and create events for matches."""
    job_id = "evaluate_alerts"
    t0 = _log_start(job_id)
    try:
        from app.models import models

        def _evaluate_all(db):
            # Whole per-alert evaluation (N+1 queries + inserts) runs in a
            # worker thread so the event loop is not blocked. Returns
            # (num_alerts, events_created) for logging in the coroutine.
            alerts = (
                db.query(models.Alert)
                .filter(models.Alert.is_active == True)
                .all()
            )
            if not alerts:
                return (0, 0)
            created = 0
            for alert in alerts:
                try:
                    created += _evaluate_single_alert(db, alert)
                except Exception as exc:
                    logger.warning(f"[{job_id}] Alert {alert.id} ({alert.alert_type}) failed: {exc}")
            db.commit()
            return (len(alerts), created)

        num_alerts, created = await _run_in_thread_with_session(_evaluate_all)
        if num_alerts == 0:
            _log_done(job_id, t0, "no active alerts")
        else:
            _log_done(job_id, t0, f"evaluated {num_alerts} alerts, created {created} events")
    except Exception as exc:
        _log_fail(job_id, exc)


def _evaluate_single_alert(db, alert) -> int:
    """Evaluate a single alert rule and insert events. Returns count of new events."""
    from app.models import models
    from datetime import datetime, timezone as tz

    config = alert.config or {}
    created = 0

    # Avoid duplicate events: skip if we already created an event for this
    # alert in the last 6 hours
    cutoff = datetime.now(tz.utc) - timedelta(hours=6)
    recent = (
        db.query(models.AlertEvent.id)
        .filter(
            models.AlertEvent.alert_id == alert.id,
            models.AlertEvent.created_at >= cutoff,
        )
        .first()
    )
    if recent:
        return 0

    if alert.alert_type == "app_trending":
        threshold = float(config.get("threshold", 60))
        app_name = config.get("app_name", "")

        q = db.query(
            models.AppTrendingScore.app_id,
            models.AppTrendingScore.trend_score,
            models.App.name,
        ).join(models.App, models.App.id == models.AppTrendingScore.app_id)

        if app_name:
            q = q.filter(models.App.name.ilike(f"%{app_name}%"))

        q = q.filter(models.AppTrendingScore.trend_score >= threshold)
        hits = q.order_by(models.AppTrendingScore.trend_score.desc()).limit(5).all()

        for app_id, score, name in hits:
            event = models.AlertEvent(
                alert_id=alert.id,
                workspace_id=alert.workspace_id,
                title=f"{name} is trending (score {score:.0f})",
                message=f"App \"{name}\" reached a trending score of {score:.1f}, above your threshold of {threshold}.",
                data={"app_id": app_id, "score": round(score, 1), "threshold": threshold},
            )
            db.add(event)
            created += 1

    elif alert.alert_type == "keyword_rising":
        threshold = float(config.get("threshold", 70))
        keyword_filter = config.get("keyword", "")

        from app.models.models import Keyword, KeywordMetrics

        q = db.query(
            Keyword.id,
            Keyword.term,
            Keyword.opportunity_score,
        ).filter(Keyword.opportunity_score >= threshold)

        if keyword_filter:
            q = q.filter(Keyword.term.ilike(f"%{keyword_filter}%"))

        hits = q.order_by(Keyword.opportunity_score.desc()).limit(5).all()

        for kw_id, term, score in hits:
            event = models.AlertEvent(
                alert_id=alert.id,
                workspace_id=alert.workspace_id,
                title=f"Keyword \"{term}\" rising (score {score:.0f})",
                message=f"Keyword \"{term}\" opportunity score reached {score:.1f}, above your threshold of {threshold}.",
                data={"keyword_id": kw_id, "keyword": term, "score": round(score, 1), "threshold": threshold},
            )
            db.add(event)
            created += 1

    elif alert.alert_type == "new_opportunity":
        from app.models.models import DailyOpportunity

        min_score = float(config.get("min_score", 75))
        category_filter = config.get("category", "")

        q = db.query(DailyOpportunity).filter(
            DailyOpportunity.success_probability >= min_score / 100.0,
            DailyOpportunity.date >= (datetime.now(tz.utc) - timedelta(days=1)).date(),
        )

        hits = q.order_by(DailyOpportunity.success_probability.desc()).limit(3).all()

        for opp in hits:
            niche = opp.niche or opp.keyword or "Unknown"
            if category_filter and category_filter.lower() not in (niche or "").lower():
                continue
            prob = (opp.success_probability or 0) * 100
            event = models.AlertEvent(
                alert_id=alert.id,
                workspace_id=alert.workspace_id,
                title=f"New opportunity: {niche} ({prob:.0f}%)",
                message=opp.ai_summary or f"A new opportunity in \"{niche}\" was detected with {prob:.0f}% success probability.",
                data={"niche": niche, "probability": round(prob, 1)},
            )
            db.add(event)
            created += 1

    elif alert.alert_type == "rank_drop":
        drop_threshold = int(config.get("drop_positions", 20))
        app_name = config.get("app_name", "")

        # Compare latest ranking vs 24h-ago ranking
        from sqlalchemy import func as sqla_func

        q = db.query(
            models.App.id,
            models.App.name,
            models.App.current_rank,
        ).filter(models.App.current_rank.isnot(None))

        if app_name:
            q = q.filter(models.App.name.ilike(f"%{app_name}%"))

        apps = q.limit(100).all()

        cutoff_24h = datetime.now(tz.utc) - timedelta(hours=24)
        for app_id, name, current_rank in apps:
            prev_rank_row = (
                db.query(sqla_func.min(models.Ranking.rank))
                .filter(
                    models.Ranking.app_id == app_id,
                    models.Ranking.recorded_at >= cutoff_24h - timedelta(hours=24),
                    models.Ranking.recorded_at < cutoff_24h,
                )
                .scalar()
            )
            if prev_rank_row and current_rank and current_rank - prev_rank_row >= drop_threshold:
                event = models.AlertEvent(
                    alert_id=alert.id,
                    workspace_id=alert.workspace_id,
                    title=f"{name} dropped {current_rank - prev_rank_row} positions",
                    message=f"App \"{name}\" dropped from rank {prev_rank_row} to {current_rank} (lost {current_rank - prev_rank_row} positions).",
                    data={"app_id": app_id, "prev_rank": prev_rank_row, "current_rank": current_rank, "drop": current_rank - prev_rank_row},
                )
                db.add(event)
                created += 1

    return created


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

    # ── Per-country top charts (Tier-1 storefronts) — every 6 h ───────────
    scheduler.add_job(
        job_country_charts,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(minutes=8),
            timezone="UTC",
        ),
        id="country_charts",
        name="Every 6h: Per-country Top Charts (Tier-1)",
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
            start_date=now + timedelta(minutes=20),
            timezone="UTC",
        ),
        id="full_metadata",
        name="Every 6h: Full App Metadata",
        **_JOB_DEFAULTS,
    )

    # ── every 2 h: backfill apps missing descriptions/screenshots ─────────
    scheduler.add_job(
        job_backfill_incomplete,
        trigger=IntervalTrigger(
            hours=1,
            start_date=now + timedelta(minutes=3),
            timezone="UTC",
        ),
        id="backfill_incomplete",
        name="Every 1h: Backfill Incomplete Apps (iTunes batch)",
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

    # ── every 30 min: precompute blowing-up scores ────────────────────────────
    # First run: 4 min after startup (staggered from trending_compute at 2 min).
    # Was 15 min — too frequent, holds a connection each time.
    scheduler.add_job(
        job_blowing_up_compute,
        trigger=IntervalTrigger(
            minutes=30,
            start_date=now + timedelta(minutes=4),
            timezone="UTC",
        ),
        id="blowing_up_compute",
        name="Every 30min: Precompute Blowing-Up Scores",
        **_JOB_DEFAULTS,
    )

    # ── every 30 min: precompute trending scores ─────────────────────────────
    # First run: 2 min after startup so the /trending endpoint serves data soon.
    # Was 10 min — too frequent, holds a connection each time.
    scheduler.add_job(
        job_trending_compute,
        trigger=IntervalTrigger(
            minutes=30,
            start_date=now + timedelta(minutes=2),
            timezone="UTC",
        ),
        id="trending_compute",
        name="Every 30min: Precompute Trending Scores",
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

    # ── every 1 h: evaluate user-defined alert rules ───────────────────────
    # First run: 40 min after startup (after trending/blowing-up scores are fresh).
    scheduler.add_job(
        job_evaluate_alerts,
        trigger=IntervalTrigger(
            hours=1,
            start_date=now + timedelta(minutes=40),
            timezone="UTC",
        ),
        id="evaluate_alerts",
        name="Every 1h: Evaluate User Alert Rules",
        **_JOB_DEFAULTS,
    )

    registered = [j.id for j in scheduler.get_jobs()]
    logger.info(f"[SCHEDULER] Registered {len(registered)} jobs: {registered}")
    return scheduler
