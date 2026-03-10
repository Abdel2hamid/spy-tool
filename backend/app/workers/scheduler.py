"""
Recurring scraping, scoring, and discovery scheduler.

Job schedule:

  Job ID                   Interval  First run   Purpose
  ───────────────────────  ────────  ──────────  ─────────────────────────────────────────
  discovery_keywords         6 h      2 min       100+ keyword search → queue
  discovery_charts           2 h      5 min       Charts × all genres × 20 countries → queue
  discovery_developer        12 h     10 min      Developer expansion → queue
  queue_processor            30 min   15 min      Process discovery queue (full scrape)
  hourly_reviews_ratings     1 h      1 h         Quick refresh (rating/reviews for all apps)
  hourly_scoring             1 h      65 min      Recompute scores + daily report
  full_metadata              6 h      6 h         Full metadata refresh for all tracked apps
  keyword_discovery          24 h     20 min      Keyword expansion engine (10k-100k keywords)

Discovery jobs have short first-run delays so coverage starts building
immediately after deploy without waiting for the bootstrap endpoint.

To change an interval: edit the `hours=` / `minutes=` in setup_scheduler().
To disable a job:      comment out its scheduler.add_job() call.
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
# Job: every 6 h — keyword discovery (100+ keywords → discovery queue)
# ---------------------------------------------------------------------------

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

async def job_queue_processor():
    """
    Pick up to 25 pending items from the discovery queue, scrape full
    details (metadata + versions + reviews), persist to apps table.
    """
    job_id = "queue_processor"
    t0 = _log_start(job_id)
    try:
        from app.workers.discovery_engine import DiscoveryEngine
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            engine = DiscoveryEngine(db)
            scraped = await engine.process_queue(batch_size=25)
            _log_done(job_id, t0, f"{scraped} apps fully scraped from queue")
        finally:
            db.close()
    except Exception as exc:
        _log_fail(job_id, exc)


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
# Job: every 12 h — keyword intelligence pipeline (trends + Apple signals + scoring)
# ---------------------------------------------------------------------------

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
                        count = svc.discover_for_app(app_id)
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

                    # 1. Alphabet mining
                    alpha_svc = AlphabetMiningService(batch_db)
                    alpha_count = alpha_svc.mine_for_app(app_id)
                    total_alpha += alpha_count

                    # 2. Competitor mining
                    comp_svc = CompetitorKeywordService(batch_db)
                    comp_count = comp_svc.mine_for_app(app_id)
                    total_comp += comp_count

                    # 3. Gap analysis
                    gap_svc = KeywordGapService(batch_db)
                    gap_count = gap_svc.analyze_for_app(app_id)
                    total_gaps += gap_count
                    logger.info(f"[{job_id}] Found {gap_count} gap keywords for app {app_id}")

                    # 4. Opportunity scoring
                    opp_svc = OpportunityScoreService(batch_db)
                    opp_svc.score_for_app(app_id)

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
# Scheduler setup
# ---------------------------------------------------------------------------

def setup_scheduler() -> AsyncIOScheduler:
    """
    Register all recurring jobs against the module-level scheduler instance.
    Must be called before scheduler.start().
    """
    now = datetime.utcnow()

    # ── Discovery: keyword search (100+ keywords → queue) — every 6 h ──────
    # First run: 2 min after startup so discovery begins immediately on deploy.
    scheduler.add_job(
        job_discovery_keywords,
        trigger=IntervalTrigger(
            hours=6,
            start_date=now + timedelta(minutes=2),
            timezone="UTC",
        ),
        id="discovery_keywords",
        name="Every 6h: Keyword Discovery → Queue",
        **_JOB_DEFAULTS,
    )

    # ── Discovery: chart scraping (all genres × countries → queue) — every 2 h
    # First run: 5 min after startup; each run processes 12 chart pages.
    # Full coverage of all charts takes ~44 runs (~88 h) cycling continuously.
    scheduler.add_job(
        job_discovery_charts,
        trigger=IntervalTrigger(
            hours=2,
            start_date=now + timedelta(minutes=5),
            timezone="UTC",
        ),
        id="discovery_charts",
        name="Every 2h: Chart Discovery → Queue",
        **_JOB_DEFAULTS,
    )

    # ── Discovery: developer expansion — every 12 h ────────────────────────
    # First run: 10 min after startup.
    scheduler.add_job(
        job_discovery_developer,
        trigger=IntervalTrigger(
            hours=12,
            start_date=now + timedelta(minutes=10),
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
    # First run: 3 min after startup so keyword data starts enriching immediately.
    scheduler.add_job(
        job_keyword_intelligence,
        trigger=IntervalTrigger(
            hours=12,
            start_date=now + timedelta(minutes=3),
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
            start_date=now + timedelta(minutes=2),
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

    registered = [j.id for j in scheduler.get_jobs()]
    logger.info(f"[SCHEDULER] Registered {len(registered)} jobs: {registered}")
    return scheduler
