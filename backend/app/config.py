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
    # Limits how many apps are scraped / refreshed across every pipeline path.
    # Set MAX_TEST_APPS=0 in .env (or bump the default here) to remove the cap
    # when moving to production.
    max_test_apps: int = 0

    class Config:
        env_file = ".env"


settings = Settings()
