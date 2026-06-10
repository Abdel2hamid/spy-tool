from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(
    settings.database_url.replace("+asyncpg", ""),
    pool_size=5,           # persistent connections (reduced from 15)
    max_overflow=10,       # burst capacity (total max = 15, reduced from 40)
    pool_timeout=30,       # wait up to 30s for a connection
    pool_recycle=1800,     # recycle connections every 30min (Railway closes idle)
    pool_pre_ping=True,    # verify connection is alive before use
    echo=settings.debug,
    connect_args={"options": "-c statement_timeout=30000"},  # 30s max per query
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
