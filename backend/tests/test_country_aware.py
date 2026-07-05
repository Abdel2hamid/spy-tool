"""
Integration tests for country-aware trending / blowing-up.

These exercise the real per-country computation against PostgreSQL (the queries
use pg-specific features: pg_insert upsert, DISTINCT ON, make_interval), so they
are gated on TEST_DATABASE_URL being set to a *disposable* database. They skip
when it is not set — they never touch a production database.

Run with, e.g.:
    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:55432/appstore_spy \
        python -m pytest tests/test_country_aware.py -v
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
    # Clean only the tables these tests touch.
    s.execute(text(
        "TRUNCATE app_trending_scores, app_blowing_up_scores, rankings, apps "
        "RESTART IDENTITY CASCADE"
    ))
    s.commit()
    yield s
    s.rollback()
    s.close()


# ── helpers ────────────────────────────────────────────────────────────────

def _make_app(db, store_id, name):
    from app.models.models import App
    a = App(app_id=store_id, name=name, developer="Test Dev",
            current_reviews=100, current_rank=None, source="tracked")
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _seed_trend(db, app_pk, country, ranks):
    """Seed a descending-time series of ranks for an app in a country.

    `ranks` is oldest→newest; a decreasing sequence = improving (trending up).
    """
    from app.models.models import Ranking
    now = datetime.utcnow()
    n = len(ranks)
    for i, r in enumerate(ranks):
        recorded = now - timedelta(days=(n - 1 - i))  # spread over the last n days
        db.add(Ranking(
            app_id=app_pk, chart_type="topfree", country=country, genre="all",
            rank=r, previous_rank=(ranks[i - 1] if i > 0 else None),
            recorded_at=recorded,
        ))
    db.commit()


# ── trending: per-country isolation ─────────────────────────────────────────

def test_trending_isolated_per_country(db):
    """Rankings from different storefronts must never mix in trending scores."""
    from app.services.trending_compute_service import compute_trending_scores
    from app.models.models import AppTrendingScore

    a_us = _make_app(db, "1001", "US Riser")
    a_jp = _make_app(db, "1002", "JP Riser")
    # Each app trends only in its own storefront.
    _seed_trend(db, a_us.id, "us", [80, 60, 40, 20, 10])
    _seed_trend(db, a_jp.id, "jp", [90, 70, 50, 30, 15])

    us_scored = compute_trending_scores(db, country="us")
    jp_scored = compute_trending_scores(db, country="jp")
    assert us_scored >= 1 and jp_scored >= 1

    rows = db.query(AppTrendingScore).all()
    by_key = {(r.app_id, r.country) for r in rows}
    # US app scored under 'us' only; JP app under 'jp' only.
    assert (a_us.id, "us") in by_key
    assert (a_jp.id, "jp") in by_key
    assert (a_us.id, "jp") not in by_key  # never mixed
    assert (a_jp.id, "us") not in by_key


def test_trending_empty_dataset(db):
    """A storefront with no rankings yields zero scores and no rows."""
    from app.services.trending_compute_service import compute_trending_scores
    from app.models.models import AppTrendingScore

    scored = compute_trending_scores(db, country="de")
    assert scored == 0
    assert db.query(AppTrendingScore).filter_by(country="de").count() == 0


def test_all_countries_driver_covers_each_storefront(db):
    """The all-countries driver scores each storefront that has rankings."""
    from app.services.trending_compute_service import compute_trending_scores_all_countries
    from app.models.models import AppTrendingScore

    a_us = _make_app(db, "2001", "US App")
    a_gb = _make_app(db, "2002", "GB App")
    _seed_trend(db, a_us.id, "us", [50, 40, 30, 20, 10])
    _seed_trend(db, a_gb.id, "gb", [60, 45, 35, 25, 12])

    total = compute_trending_scores_all_countries(db)
    assert total >= 2
    countries = {c for (c,) in db.query(AppTrendingScore.country).distinct()}
    assert {"us", "gb"}.issubset(countries)


# ── endpoint read helper: default / explicit / invalid country ──────────────

def test_read_precomputed_default_and_explicit(db):
    """_read_precomputed_trending defaults to 'us' and filters by country."""
    from app.services.trending_compute_service import compute_trending_scores
    from app.api.routes import _read_precomputed_trending

    a_us = _make_app(db, "3001", "US Only")
    a_jp = _make_app(db, "3002", "JP Only")
    _seed_trend(db, a_us.id, "us", [70, 55, 40, 25, 12])
    _seed_trend(db, a_jp.id, "jp", [80, 60, 45, 30, 14])
    compute_trending_scores(db, country="us")
    compute_trending_scores(db, country="jp")

    # default country → 'us'
    default_items = _read_precomputed_trending(db, limit=10, category_id=None)
    default_ids = {it["id"] for it in default_items}
    assert a_us.id in default_ids
    assert a_jp.id not in default_ids  # jp app not in the default (us) list

    # explicit jp
    jp_items = _read_precomputed_trending(db, limit=10, category_id=None, country="jp")
    jp_ids = {it["id"] for it in jp_items}
    assert a_jp.id in jp_ids
    assert a_us.id not in jp_ids


def test_read_precomputed_invalid_country_is_empty(db):
    """An unknown / invalid storefront returns an empty list, not an error."""
    from app.services.trending_compute_service import compute_trending_scores
    from app.api.routes import _read_precomputed_trending

    a_us = _make_app(db, "4001", "US App")
    _seed_trend(db, a_us.id, "us", [50, 40, 30, 20, 10])
    compute_trending_scores(db, country="us")

    items = _read_precomputed_trending(db, limit=10, category_id=None, country="xx")
    assert items == []


# ── blowing-up: per-country isolation ───────────────────────────────────────

def test_blowing_up_isolated_per_country(db):
    """Blowing-up scores are computed per storefront and isolated."""
    from app.services.blowing_up_service import BlowingUpService
    from app.models.models import AppBlowingUpScore

    a_us = _make_app(db, "5001", "US Blowup")
    a_jp = _make_app(db, "5002", "JP Blowup")
    _seed_trend(db, a_us.id, "us", [95, 70, 45, 20, 8])
    _seed_trend(db, a_jp.id, "jp", [90, 65, 40, 18, 6])

    svc = BlowingUpService(db)
    svc.compute_for_all_apps(timeframe_days=14, country="us")
    svc.compute_for_all_apps(timeframe_days=14, country="jp")

    keys = {(r.app_id, r.country) for r in db.query(AppBlowingUpScore).all()}
    assert (a_us.id, "us") in keys
    assert (a_jp.id, "jp") in keys
    assert (a_us.id, "jp") not in keys
    assert (a_jp.id, "us") not in keys
