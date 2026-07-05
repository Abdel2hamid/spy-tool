"""
seed_data.py
============
Populates the database with real data so dashboard features work:

  Step 1 — Apply schema migrations (creates app_trending_scores + any other new tables)
  Step 2 — Scrape top charts 3× with short delays → 3 ranking snapshots per app
  Step 3 — Run scoring worker → opportunities, market weakness, feature gaps, ideas
  Step 4 — Compute trending scores → app_trending_scores table
  Step 5 — Print verification stats

Run from the backend/ directory:
    python3 seed_data.py
"""

import asyncio
import logging
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed")

# ── silence noisy sub-loggers ────────────────────────────────────────────────
for noisy in ("sqlalchemy.engine", "urllib3", "asyncio", "apscheduler"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Step 0 — DB baseline
# ---------------------------------------------------------------------------

def print_stats(label: str = ""):
    from app.database import engine
    from sqlalchemy import text

    with engine.connect() as conn:
        apps         = conn.execute(text("SELECT COUNT(*) FROM apps")).scalar()
        ranked_apps  = conn.execute(text("SELECT COUNT(*) FROM apps WHERE current_rank IS NOT NULL")).scalar()
        rankings     = conn.execute(text("SELECT COUNT(*) FROM rankings")).scalar()
        kws          = conn.execute(text("SELECT COUNT(*) FROM keywords")).scalar()
        opps         = conn.execute(text("SELECT COUNT(*) FROM opportunities")).scalar()
        ideas        = conn.execute(text("SELECT COUNT(*) FROM app_ideas")).scalar()
        try:
            trending = conn.execute(text("SELECT COUNT(*) FROM app_trending_scores")).scalar()
        except Exception:
            trending = "table missing"
        try:
            daily = conn.execute(text("SELECT COUNT(*) FROM daily_reports")).scalar()
        except Exception:
            daily = 0

    tag = f"[{label}] " if label else ""
    logger.info(
        f"{tag}apps={apps} (ranked={ranked_apps}) | "
        f"rankings={rankings} | keywords={kws} | "
        f"opportunities={opps} | ideas={ideas} | "
        f"trending_scores={trending} | daily_reports={daily}"
    )


# ---------------------------------------------------------------------------
# Step 1 — Apply migrations
# ---------------------------------------------------------------------------

def step_apply_migrations():
    logger.info("─── Step 1: Apply schema migrations ───────────────────────────────")
    from app.main import _upgrade_database

    # Bring the schema to head via Alembic (builds a fresh DB; no-op otherwise).
    _upgrade_database()
    logger.info("  migrations done (alembic upgrade head)")


# ---------------------------------------------------------------------------
# Step 2 — Scrape top charts 3× (→ 3 fresh ranking snapshots per app)
# ---------------------------------------------------------------------------

async def _single_chart_run(n: int):
    from app.workers.tasks import ScraperWorker

    logger.info(f"  chart run #{n} starting…")
    worker = ScraperWorker()
    await worker.initialize()
    try:
        await worker.scrape_top_charts(chart_types=["topfree", "toppaid", "topgrossing"])
    finally:
        await worker.cleanup()
    logger.info(f"  chart run #{n} complete")


async def step_scrape_charts():
    logger.info("─── Step 2: Scrape top charts 3× for ranking history ───────────────")
    for n in range(1, 4):
        await _single_chart_run(n)
        if n < 3:
            delay = 90  # 90-second gap so timestamps differ meaningfully
            logger.info(f"  waiting {delay}s before next snapshot…")
            await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# Step 3 — Scoring (opportunities, market weakness, ideas, estimates)
# ---------------------------------------------------------------------------

def step_run_scoring():
    logger.info("─── Step 3: Run scoring worker ─────────────────────────────────────")
    from app.workers.tasks import run_scoring_task
    run_scoring_task()
    logger.info("  scoring complete")


# ---------------------------------------------------------------------------
# Step 4 — Trending compute
# ---------------------------------------------------------------------------

def step_compute_trending():
    logger.info("─── Step 4: Compute trending scores ────────────────────────────────")
    from app.database import SessionLocal
    from app.services.trending_compute_service import compute_trending_scores

    db = SessionLocal()
    try:
        count = compute_trending_scores(db)
        logger.info(f"  trending scores computed for {count} apps")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Step 5 — Keyword enrichment (fast, no external APIs)
# ---------------------------------------------------------------------------

def step_enrich_keywords():
    logger.info("─── Step 5: Enrich keyword metrics (Apple signals, no ext. APIs) ───")
    from app.database import SessionLocal
    from app.scoring.engine import ScoringEngine

    db = SessionLocal()
    try:
        engine = ScoringEngine(db)
        engine.update_keyword_metrics()
        db.commit()
        logger.info("  keyword metrics updated")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    t_start = time.monotonic()

    logger.info("══════════ AppStore Spy — Database Seeding ══════════")
    print_stats("before")

    step_apply_migrations()

    await step_scrape_charts()

    step_enrich_keywords()
    step_run_scoring()
    # Fresh session for trending compute — ensures all committed rankings are visible
    step_compute_trending()
    step_compute_trending()  # Run twice: second pass catches any apps missed by the first

    elapsed = time.monotonic() - t_start
    logger.info(f"══════════ Seeding complete in {elapsed:.0f}s ══════════")
    print_stats("after")

    # ── Dashboard verification ────────────────────────────────────────────
    from app.database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        ranked = conn.execute(text("SELECT COUNT(*) FROM apps WHERE current_rank IS NOT NULL")).scalar()
        trending = conn.execute(text("SELECT COUNT(*) FROM app_trending_scores")).scalar()
        opps = conn.execute(text("SELECT COUNT(*) FROM opportunities")).scalar()
        kws = conn.execute(text("SELECT COUNT(*) FROM keywords WHERE search_volume > 0")).scalar()

    logger.info("══ Dashboard readiness check ══")
    logger.info(f"  Apps tracked       : {ranked} {'✓' if ranked > 0 else '✗ (need chart scrape)'}")
    logger.info(f"  Trending apps      : {trending} {'✓' if trending > 0 else '✗ (need 3+ ranking snapshots)'}")
    logger.info(f"  Opportunities      : {opps} {'✓' if opps > 0 else '✗ (need scoring)'}")
    logger.info(f"  Keywords (enriched): {kws} {'✓' if kws > 0 else '✗ (need keyword metrics update)'}")

    if any([ranked == 0, trending == 0]):
        logger.warning("Some signals still missing — re-run this script or wait for scheduler jobs.")
    else:
        logger.info("Dashboard should be fully populated.")


if __name__ == "__main__":
    asyncio.run(main())
