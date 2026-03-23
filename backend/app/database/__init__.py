from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from app.config import settings

engine = create_engine(
    settings.database_url.replace("+asyncpg", ""),
    poolclass=NullPool,
    echo=settings.debug,
    connect_args={"options": "-c statement_timeout=15000"},  # 15s max per query
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
