from fastapi import FastAPI, Header, HTTPException, Request
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import logging
import time
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.api import router
from app.api.auth_router import router as auth_router
from app.workers.tasks import run_scrape_task, run_scoring_task
from app.workers.scheduler import scheduler, setup_scheduler, get_job_metrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_APP_START_TIME = time.monotonic()




def _upgrade_database() -> None:
    """Bring the database schema to head via Alembic.

    Replaces the old create_all + inline-DDL approach: schema is now managed by
    versioned revisions (backend/alembic/versions). The baseline revision builds
    a fresh database and is a no-op on an already-provisioned one; future changes
    are separate revisions. Idempotent and safe to run on every startup.
    """
    import os
    from alembic.config import Config
    from alembic import command

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../backend
    cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    command.upgrade(cfg, "head")


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
    logger.info("Starting RankSpy...")

    # Bring the schema to head via Alembic (builds a fresh DB; no-op otherwise).
    _upgrade_database()
    logger.info("Database schema at head (Alembic)")

    # Startup scrape disabled — the scheduler handles all scraping on its own schedule.
    # asyncio.create_task(_initial_scrape_background())

    # Start the recurring scheduler.  Jobs are registered with start_date
    # offsets so they don't pile on top of the startup scrape.
    # ENABLE_SCHEDULER=0 lets extra replicas run API-only — the scheduler
    # is in-process state; two replicas running it means duplicate scraping,
    # duplicate writes, and racing queue claims.
    import os as _os
    _scheduler_enabled = _os.getenv("ENABLE_SCHEDULER", "1").lower() not in ("0", "false", "no")
    if _scheduler_enabled:
        setup_scheduler()
        scheduler.start()
        logger.info(f"Scheduler started — {len(scheduler.get_jobs())} recurring jobs registered")
    else:
        logger.info("Scheduler disabled via ENABLE_SCHEDULER — API-only instance")

    yield

    # Graceful shutdown: don't wait for running jobs to finish
    if _scheduler_enabled:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    logger.info("Shutting down RankSpy...")


app = FastAPI(
    title=settings.app_name,
    description="AI-powered App Store intelligence and opportunity detection",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token", "Stripe-Signature"],
)

from app.api.admin_console_router import router as admin_console_router
from app.api.stripe_router import router as stripe_router


# ── Global auth middleware ────────────────────────────────────────────────
# Requires a valid Bearer JWT on all /api/v1/ routes except a small
# whitelist (auth endpoints, Stripe webhooks, health, categories).
# This is a safety net — individual endpoints still declare their own
# auth dependencies, but this catches any that were missed.
# ────────────────────────────────────────────────────────────────────────

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as StarletteJSON


_PUBLIC_PREFIXES = (
    "/api/v1/auth/",           # login, register, me
    "/api/v1/stripe/webhook",  # Stripe webhook (has its own sig verification)
    "/api/v1/stripe/config",   # public publishable key
    "/api/v1/admin-console/announcements/active",  # public announcements
)

_PUBLIC_EXACT = {
    "/", "/health", "/api/v1/categories",
}


class _AuthGateMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated requests to /api/v1/ data endpoints."""

    def _cors_headers(self, request) -> dict[str, str]:
        """Build CORS headers for error responses (middleware is outermost)."""
        origin = request.headers.get("origin", "")
        allowed = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
        if origin and origin in allowed:
            return {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
            }
        return {}

    async def dispatch(self, request, call_next):
        path = request.url.path

        # Skip non-API routes (Next.js static, etc.)
        if not path.startswith("/api/v1/"):
            return await call_next(request)

        # Skip OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip explicitly public paths
        if path in _PUBLIC_EXACT:
            return await call_next(request)
        for prefix in _PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Require a valid Bearer JWT
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return StarletteJSON(
                status_code=401,
                content={"detail": "Not authenticated"},
                headers={
                    "WWW-Authenticate": "Bearer",
                    **self._cors_headers(request),
                },
            )

        from app.services.auth_service import decode_access_token
        if decode_access_token(auth[7:].strip()) is None:
            return StarletteJSON(
                status_code=401,
                content={"detail": "Invalid or expired token"},
                headers={
                    "WWW-Authenticate": "Bearer",
                    **self._cors_headers(request),
                },
            )

        return await call_next(request)


# Add AFTER CORSMiddleware so CORS headers are applied to 401 responses
app.add_middleware(_AuthGateMiddleware)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")
app.include_router(admin_console_router, prefix="/api/v1")
app.include_router(stripe_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all: log the real error and return a CORS-safe 500 response.

    Starlette's CORSMiddleware does NOT add CORS headers to responses
    generated by the outermost ServerErrorMiddleware (i.e. unhandled
    exceptions that bubble past ExceptionMiddleware).  By registering
    an explicit handler here, the response goes through the normal
    ASGI send path so CORSMiddleware can add its headers.
    """
    logger.exception(
        "Unhandled exception in %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    origin = request.headers.get("origin")
    allowed = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    headers: dict[str, str] = {}
    if origin and origin in allowed:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    # Details are logged above — never leak exception internals to clients.
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=headers,
    )


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/run-migrations")
@app.get("/api/v1/run-migrations")
def run_migrations_endpoint(x_admin_token: Optional[str] = Header(None)):
    """Manually run `alembic upgrade head`. Requires ADMIN_TOKEN — fails closed."""
    import secrets as _secrets
    if not settings.admin_token or not x_admin_token or not _secrets.compare_digest(
        x_admin_token, settings.admin_token
    ):
        raise HTTPException(status_code=403, detail="Admin token required")
    try:
        _upgrade_database()
        return {"ok": True, "detail": "Database upgraded to head"}
    except Exception as exc:
        logger.exception("Manual migration failed")
        raise HTTPException(status_code=500, detail=f"Migration failed: {type(exc).__name__}")


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

    # 3. Ranking health — critical data pipeline check
    ranking_health = {}
    try:
        from datetime import timezone as _tz
        from sqlalchemy import func as sqla_func
        from app.database import SessionLocal
        from app.models.models import Ranking

        _db = SessionLocal()
        try:
            newest = _db.query(sqla_func.max(Ranking.recorded_at)).scalar()
            if newest is not None:
                if newest.tzinfo is None:
                    newest = newest.replace(tzinfo=_tz.utc)
                from datetime import datetime as _dt
                age_hours = (_dt.now(_tz.utc) - newest).total_seconds() / 3600
                cutoff_24h = _dt.now(_tz.utc) - __import__("datetime").timedelta(hours=24)
                count_24h = (
                    _db.query(sqla_func.count(Ranking.id))
                    .filter(Ranking.recorded_at >= cutoff_24h)
                    .scalar() or 0
                )
                if age_hours < 6:
                    r_status = "healthy"
                elif age_hours < 24:
                    r_status = "stale"
                else:
                    r_status = "critical"
                    if status == "healthy":
                        status = "degraded"
                ranking_health = {
                    "latest_ranking_recorded_at": newest.isoformat(),
                    "ranking_age_hours": round(age_hours, 1),
                    "rankings_last_24h": count_24h,
                    "ranking_status": r_status,
                }
            else:
                ranking_health = {
                    "latest_ranking_recorded_at": None,
                    "ranking_age_hours": None,
                    "rankings_last_24h": 0,
                    "ranking_status": "critical",
                }
                if status == "healthy":
                    status = "degraded"
        finally:
            _db.close()
    except Exception as exc:
        ranking_health = {"error": str(exc)}

    # 4. Scheduled jobs — next run times
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

    # 5. Connection pool status — critical for diagnosing pool exhaustion
    pool_status = {}
    try:
        pool = engine.pool
        pool_status = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "max_overflow": pool._max_overflow,
            "total_connections": pool.checkedin() + pool.checkedout(),
        }
    except Exception as exc:
        pool_status = {"error": str(exc)}

    return {
        "status": status,
        "uptime_seconds": round(time.monotonic() - _APP_START_TIME, 1),
        "checks": checks,
        "ranking_health": ranking_health,
        "pool_status": pool_status,
        "scheduler_jobs": jobs,
        "job_metrics": get_job_metrics(),
        "response_ms": round((time.monotonic() - t0) * 1000, 1),
    }
