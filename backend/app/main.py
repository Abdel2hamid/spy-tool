from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
import time
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base
from app.api import router
from app.workers.tasks import run_scrape_task, run_scoring_task
from app.workers.scheduler import scheduler, setup_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_APP_START_TIME = time.monotonic()


_MIGRATIONS = [
    # Platform upgrade columns (Session 5)
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_installs_min INTEGER",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_installs_max INTEGER",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS install_confidence FLOAT",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_revenue_monthly_min FLOAT",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_revenue_monthly_max FLOAT",
    # Freshness priority system (Session 12)
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS freshness_score FLOAT DEFAULT 0.0",
    # Performance indexes (Session 12) — CREATE INDEX IF NOT EXISTS is idempotent
    "CREATE INDEX IF NOT EXISTS idx_app_rating ON apps (current_rating)",
    "CREATE INDEX IF NOT EXISTS idx_app_reviews ON apps (current_reviews)",
    "CREATE INDEX IF NOT EXISTS idx_app_rank ON apps (current_rank)",
    "CREATE INDEX IF NOT EXISTS idx_app_release_date ON apps (release_date)",
    "CREATE INDEX IF NOT EXISTS idx_app_created_at ON apps (created_at)",
    "CREATE INDEX IF NOT EXISTS idx_app_freshness ON apps (freshness_score)",
    "CREATE INDEX IF NOT EXISTS idx_app_developer ON apps (developer)",
    "CREATE INDEX IF NOT EXISTS idx_app_primary_category ON apps (primary_category)",
    # Keyword intelligence pipeline (Session 17)
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS trend_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS trend_growth FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS trend_velocity FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS apps_count INTEGER DEFAULT 0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS dominance_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS competition_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS cpc FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS opportunity_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS feasibility_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS last_enriched TIMESTAMPTZ",
    # keyword_trends table (Session 17) — explicit DDL since create_all won't add new cols
    """CREATE TABLE IF NOT EXISTS keyword_trends (
        id SERIAL PRIMARY KEY,
        keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
        week_start TIMESTAMPTZ NOT NULL,
        interest_score INTEGER DEFAULT 0,
        captured_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(keyword_id, week_start)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_ktrend_keyword ON keyword_trends (keyword_id)",
    # Keyword discovery engine (Session 21)
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS keyword_source VARCHAR(50)",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS discovered_from VARCHAR(255)",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ",
    # Keyword lifecycle status (Session 22)
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'raw'",
    # App keyword intelligence — extracted from title/subtitle/description (Session 22)
    """CREATE TABLE IF NOT EXISTS app_keyword_intelligence (
        id SERIAL PRIMARY KEY,
        app_id INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
        keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
        source VARCHAR(50),
        app_rank INTEGER,
        result_count INTEGER DEFAULT 0,
        search_volume INTEGER DEFAULT 0,
        difficulty FLOAT DEFAULT 0.0,
        traffic_score FLOAT DEFAULT 0.0,
        extracted_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(app_id, keyword_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_aki_app ON app_keyword_intelligence (app_id)",
    "CREATE INDEX IF NOT EXISTS idx_aki_traffic ON app_keyword_intelligence (app_id, traffic_score DESC)",
    # Keyword queue — decouples discovery from enrichment (Session 22)
    """CREATE TABLE IF NOT EXISTS keyword_queue (
        id SERIAL PRIMARY KEY,
        term VARCHAR(255) UNIQUE NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        priority INTEGER NOT NULL DEFAULT 0,
        source VARCHAR(50),
        added_at TIMESTAMPTZ DEFAULT NOW(),
        processed_at TIMESTAMPTZ
    )""",
    "CREATE INDEX IF NOT EXISTS idx_kwq_status_priority ON keyword_queue (status, priority)",
    "CREATE INDEX IF NOT EXISTS idx_kwq_added_at ON keyword_queue (added_at)",
    # App discovered keywords — autocomplete + affix expansion per app (Session 23)
    """CREATE TABLE IF NOT EXISTS app_discovered_keywords (
        id SERIAL PRIMARY KEY,
        app_id INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
        keyword VARCHAR(255) NOT NULL,
        source VARCHAR(50),
        source_keyword VARCHAR(255),
        search_volume INTEGER DEFAULT 0,
        difficulty FLOAT DEFAULT 0.0,
        traffic_score FLOAT DEFAULT 0.0,
        app_rank INTEGER,
        trend_score FLOAT DEFAULT 0.0,
        trend_direction VARCHAR(20) DEFAULT 'stable',
        opportunity_score FLOAT DEFAULT 0.0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(app_id, keyword)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_adk_app ON app_discovered_keywords (app_id)",
    "CREATE INDEX IF NOT EXISTS idx_adk_opp_score ON app_discovered_keywords (app_id, opportunity_score DESC)",
    # Phase-1 keyword discovery: competitor_rank + keyword_gap (Session 24)
    "ALTER TABLE app_discovered_keywords ADD COLUMN IF NOT EXISTS competitor_rank INTEGER",
    "ALTER TABLE app_discovered_keywords ADD COLUMN IF NOT EXISTS keyword_gap BOOLEAN DEFAULT FALSE",
    "CREATE INDEX IF NOT EXISTS idx_adk_gap ON app_discovered_keywords (app_id, keyword_gap)",
    # 3-table keyword architecture (Session 26)
    # keyword_metrics: normalised metrics separated from the keyword dictionary
    """CREATE TABLE IF NOT EXISTS keyword_metrics (
        id SERIAL PRIMARY KEY,
        keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
        search_volume INTEGER DEFAULT 0,
        difficulty FLOAT DEFAULT 0.0,
        trend_score FLOAT DEFAULT 0.0,
        last_updated TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(keyword_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_km_keyword_id ON keyword_metrics (keyword_id)",
    "CREATE INDEX IF NOT EXISTS idx_km_search_volume ON keyword_metrics (search_volume)",
    "CREATE INDEX IF NOT EXISTS idx_km_difficulty ON keyword_metrics (difficulty)",
    # app_keywords: add target-architecture columns (legacy position/relevance kept)
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS rank INTEGER",
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS traffic FLOAT DEFAULT 0.0",
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS opportunity_score FLOAT DEFAULT 0.0",
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS source VARCHAR(50)",
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
    "CREATE INDEX IF NOT EXISTS idx_ak_app_id ON app_keywords (app_id)",
    "CREATE INDEX IF NOT EXISTS idx_ak_keyword_id ON app_keywords (keyword_id)",
    "CREATE INDEX IF NOT EXISTS idx_ak_opportunity ON app_keywords (app_id, opportunity_score DESC)",
    # Keyword quality engine columns (new session)
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS quality_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS quality_tier VARCHAR(1)",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS validation_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS relevance_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS canonical_term VARCHAR(255)",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS times_seen INTEGER DEFAULT 1",
    "CREATE INDEX IF NOT EXISTS idx_kw_quality_score ON keywords (quality_score)",
    "CREATE INDEX IF NOT EXISTS idx_kw_quality_tier ON keywords (quality_tier)",
    "CREATE INDEX IF NOT EXISTS idx_kw_canonical ON keywords (canonical_term)",
    "CREATE INDEX IF NOT EXISTS idx_kw_last_seen ON keywords (last_seen_at)",
    # Precomputed trending scores (refreshed every 10 min by scheduler)
    """
    CREATE TABLE IF NOT EXISTS app_trending_scores (
        app_id INTEGER PRIMARY KEY REFERENCES apps(id) ON DELETE CASCADE,
        trend_score FLOAT NOT NULL DEFAULT 0.0,
        momentum_score FLOAT DEFAULT 0.0,
        momentum_3d FLOAT DEFAULT 0.0,
        momentum_7d FLOAT DEFAULT 0.0,
        consistency_score FLOAT DEFAULT 0.0,
        absolute_rank_bonus FLOAT DEFAULT 0.0,
        review_momentum FLOAT DEFAULT 0.0,
        confidence_factor FLOAT DEFAULT 1.0,
        computed_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_trending_score ON app_trending_scores (trend_score DESC)",
]


def _run_migrations(db_engine):
    """Apply additive migrations (ADD COLUMN IF NOT EXISTS) on every startup."""
    with db_engine.connect() as conn:
        for sql in _MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as exc:
                logger.warning(f"Migration skipped ({exc})")


async def _initial_scrape_background():
    """Run initial scrape + scoring in the background so server starts immediately."""
    try:
        logger.info("Background: starting initial scrape...")
        await run_scrape_task()
        logger.info("Background: initial scrape complete")
    except Exception as e:
        logger.warning(f"Background: initial scrape failed: {e}")
    try:
        await asyncio.to_thread(run_scoring_task)
        logger.info("Background: initial scoring complete")
    except Exception as e:
        logger.warning(f"Background: initial scoring failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AppStore Spy AI...")

    # Ensure all DB tables exist
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

    # Safe migrations: add new columns to existing tables if absent
    _run_migrations(engine)

    # Startup scrape disabled — the scheduler handles all scraping on its own schedule.
    # asyncio.create_task(_initial_scrape_background())

    # Start the recurring scheduler.  Jobs are registered with start_date
    # offsets so they don't pile on top of the startup scrape.
    setup_scheduler()
    scheduler.start()
    logger.info(f"Scheduler started — {len(scheduler.get_jobs())} recurring jobs registered")

    yield

    # Graceful shutdown: don't wait for running jobs to finish
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
    logger.info("Shutting down AppStore Spy AI...")


app = FastAPI(
    title=settings.app_name,
    description="AI-powered App Store intelligence and opportunity detection",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
def health_check():
    """Real health check: verifies DB connectivity and scheduler state."""
    t0 = time.monotonic()
    status = "healthy"
    checks: dict = {}

    # 1. Database connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        status = "degraded"

    # 2. Scheduler
    try:
        if scheduler.running:
            checks["scheduler"] = "running"
        else:
            checks["scheduler"] = "stopped"
            status = "degraded"
    except Exception as exc:
        checks["scheduler"] = f"error: {exc}"
        status = "degraded"

    # 3. Scheduled jobs — next run times
    jobs = []
    try:
        for job in scheduler.get_jobs():
            nrt = job.next_run_time
            jobs.append({
                "id": job.id,
                "next_run": nrt.isoformat() if nrt else None,
            })
    except Exception:
        pass

    return {
        "status": status,
        "uptime_seconds": round(time.monotonic() - _APP_START_TIME, 1),
        "checks": checks,
        "scheduler_jobs": jobs,
        "response_ms": round((time.monotonic() - t0) * 1000, 1),
    }
