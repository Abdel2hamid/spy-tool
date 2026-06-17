import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url.replace("+asyncpg", ""),
    pool_size=10,          # persistent connections (was 5 — too low for 32 jobs + API)
    max_overflow=20,       # burst capacity (total max = 30)
    pool_timeout=30,       # wait up to 30s for a connection
    pool_recycle=1800,     # recycle connections every 30min (Railway closes idle)
    pool_pre_ping=True,    # verify connection is alive before use
    echo=settings.debug,
    connect_args={"options": "-c statement_timeout=60000"},  # 60s max per query (was 30s)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(engine, "checkin")
def _on_checkin(dbapi_conn, connection_record):
    """Reset statement_timeout when a connection returns to the pool."""
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute("RESET statement_timeout")
        cursor.close()
    except Exception:
        pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
