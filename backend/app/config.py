from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://abdelhamid@localhost:5432/appstore_spy"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "abdelhamid"
    postgres_password: str = ""
    postgres_db: str = "appstore_spy"

    app_name: str = "AppStore Spy AI"
    debug: bool = True

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

    class Config:
        env_file = ".env"


settings = Settings()
