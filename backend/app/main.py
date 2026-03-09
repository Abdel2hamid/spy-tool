from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base
from app.api import router
from app.workers.tasks import run_scrape_task, run_scoring_task
from app.workers.scheduler import scheduler, setup_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    logger.info("Scheduler started — 4 recurring jobs registered")

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
    return {"status": "healthy"}
