import logging
import secrets

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://abdelhamid@localhost:5432/appstore_spy"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "abdelhamid"
    postgres_password: str = ""
    postgres_db: str = "appstore_spy"

    app_name: str = "RankSpy"
    debug: bool = False

    # ── Test-phase app cap ────────────────────────────────────────────────
    max_test_apps: int = 0

    # ── Google Trends integration ─────────────────────────────────────────
    # Set GOOGLE_TRENDS_ENABLED=false to disable (e.g. if pytrends is blocked)
    google_trends_enabled: bool = True

    # ── DataForSEO integration (optional) ────────────────────────────────
    # Sign up at https://dataforseo.com — free tier available.
    # Set DATAFORSEO_ENABLED=true + credentials to activate real search volumes.
    dataforseo_enabled: bool = False
    dataforseo_username: str = ""
    dataforseo_password: str = ""

    # ── JWT / Auth ────────────────────────────────────────────────────────
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # ── CORS ──────────────────────────────────────────────────────────────
    # Comma-separated allowed origins. Set via CORS_ORIGINS env var.
    # e.g. "https://myapp.up.railway.app,http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    # ── Admin API protection ──────────────────────────────────────────────
    # Set ADMIN_TOKEN env var. Admin endpoints require X-Admin-Token header.
    admin_token: str = ""

    class Config:
        env_file = ".env"


settings = Settings()

# JWT secret: fail-fast in production, ephemeral fallback in dev
if not settings.jwt_secret:
    import os
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("PRODUCTION"):
        raise RuntimeError(
            "FATAL: JWT_SECRET env var is not set. "
            "Refusing to start in production with an ephemeral secret. "
            "Set JWT_SECRET to a stable random string (e.g. openssl rand -base64 48)."
        )
    _generated = secrets.token_urlsafe(48)
    logging.getLogger(__name__).warning(
        "JWT_SECRET not set! Using random ephemeral secret — "
        "tokens will NOT survive restarts. Set JWT_SECRET env var."
    )
    settings.jwt_secret = _generated
