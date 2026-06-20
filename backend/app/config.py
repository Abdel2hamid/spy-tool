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
    jwt_expire_minutes: int = 480  # 8 hours

    # ── CORS ──────────────────────────────────────────────────────────────
    # Comma-separated allowed origins. Set via CORS_ORIGINS env var.
    # e.g. "https://myapp.up.railway.app,http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    # ── Stripe billing ─────────────────────────────────────────────────
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter: str = ""    # Stripe Price ID for Starter ($19.99/mo)
    stripe_price_pro: str = ""        # Stripe Price ID for Pro ($49.99/mo)
    frontend_url: str = "http://localhost:3000"

    # ── Email verification (Resend) ────────────────────────────────────
    resend_api_key: str = ""
    resend_from_email: str = "RankSpy <noreply@rankspy.app>"
    email_verification_token_expire_minutes: int = 60  # 1 hour

    # ── Admin API protection ──────────────────────────────────────────────
    # Set ADMIN_TOKEN env var. Admin endpoints require X-Admin-Token header.
    admin_token: str = ""

    class Config:
        env_file = ".env"


settings = Settings()

_logger = logging.getLogger(__name__)
_is_production = bool(
    __import__("os").getenv("RAILWAY_ENVIRONMENT")
    or __import__("os").getenv("PRODUCTION")
)

# JWT secret: fail-fast in production, ephemeral fallback in dev
if not settings.jwt_secret:
    if _is_production:
        raise RuntimeError(
            "FATAL: JWT_SECRET env var is not set. "
            "Refusing to start in production with an ephemeral secret. "
            "Set JWT_SECRET to a stable random string (e.g. openssl rand -base64 48)."
        )
    _generated = secrets.token_urlsafe(48)
    _logger.warning(
        "JWT_SECRET not set! Using random ephemeral secret — "
        "tokens will NOT survive restarts. Set JWT_SECRET env var."
    )
    settings.jwt_secret = _generated

# Admin token: auto-generate in production so admin endpoints stay locked
if not settings.admin_token:
    if _is_production:
        _admin_token = secrets.token_urlsafe(48)
        settings.admin_token = _admin_token
        _logger.warning(
            "ADMIN_TOKEN not set! Generated random token — admin endpoints "
            "are protected but unreachable until you set ADMIN_TOKEN env var."
        )
    else:
        _logger.warning(
            "ADMIN_TOKEN not set! Admin endpoints are UNPROTECTED (dev mode). "
            "Set ADMIN_TOKEN env var for production."
        )

# Stripe webhook secret: warn in production
if not settings.stripe_webhook_secret and _is_production:
    _logger.warning(
        "STRIPE_WEBHOOK_SECRET not set! Stripe webhooks will reject all events. "
        "Set STRIPE_WEBHOOK_SECRET env var."
    )

if not settings.resend_api_key and _is_production:
    _logger.warning(
        "RESEND_API_KEY not set! Email verification will be skipped. "
        "Set RESEND_API_KEY env var."
    )
