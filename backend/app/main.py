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
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_installs_min INTEGER",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_installs_max INTEGER",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS install_confidence FLOAT",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_revenue_monthly_min FLOAT",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_revenue_monthly_max FLOAT",
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
