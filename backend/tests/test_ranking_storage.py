"""
Integration tests for ranking_storage change-only writes.

Needs a disposable Postgres database via TEST_DATABASE_URL.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB_URL,
    reason="TEST_DATABASE_URL not set (integration test needs a disposable Postgres)",
)


@pytest.fixture(scope="module")
def engine():
    from sqlalchemy import create_engine, text
    eng = create_engine(TEST_DB_URL.replace("+asyncpg", ""))
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover
        pytest.skip("TEST_DATABASE_URL is set but Postgres is unreachable")
    from app.database import Base
    import app.models.models  # noqa: F401 — registers all tables
    Base.metadata.create_all(eng)
    yield eng


@pytest.fixture
def db(engine):
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    Session = sessionmaker(bind=engine)
    s = Session()
    s.execute(text("TRUNCATE rankings RESTART IDENTITY CASCADE"))
    s.commit()
    yield s
    s.rollback()
    s.close()


class TestRecordRanking:
    def test_inserts_first_ranking(self, db):
        from app.services.ranking_storage import record_ranking
        ranking = record_ranking(db, app_id=1, chart_type="topfree", rank=5)
        db.commit()

        assert ranking is not None
        assert ranking.rank == 5
        assert ranking.previous_rank is None
        assert ranking.rank_velocity == 0

    def test_suppresses_duplicate_rank(self, db):
        from app.services.ranking_storage import record_ranking
        from app.models.models import Ranking
        record_ranking(db, app_id=1, chart_type="topfree", rank=5)
        db.commit()

        second = record_ranking(db, app_id=1, chart_type="topfree", rank=5)
        db.commit()

        assert second is None
        assert db.query(Ranking).count() == 1

    def test_writes_on_rank_change(self, db):
        from app.services.ranking_storage import record_ranking
        from app.models.models import Ranking
        record_ranking(db, app_id=1, chart_type="topfree", rank=5)
        db.commit()

        second = record_ranking(db, app_id=1, chart_type="topfree", rank=3)
        db.commit()

        assert second is not None
        assert second.rank == 3
        assert second.previous_rank == 5
        assert second.rank_velocity == 2
        assert db.query(Ranking).count() == 2

    def test_heartbeat_writes_after_window(self, db):
        from app.services.ranking_storage import record_ranking
        from app.models.models import Ranking
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        r1 = record_ranking(db, app_id=1, chart_type="topfree", rank=5, recorded_at=old_time)
        db.commit()
        r1.recorded_at = old_time
        db.commit()

        second = record_ranking(db, app_id=1, chart_type="topfree", rank=5)
        db.commit()

        assert second is not None
        assert db.query(Ranking).count() == 2

    def test_separate_keys_by_country_and_genre(self, db):
        from app.services.ranking_storage import record_ranking
        from app.models.models import Ranking
        record_ranking(db, app_id=1, chart_type="topfree", rank=5, country="us", genre="all")
        record_ranking(db, app_id=1, chart_type="topfree", rank=5, country="gb", genre="all")
        db.commit()

        assert db.query(Ranking).count() == 2
