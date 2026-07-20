"""
Integration tests for cascade deletes.

Needs a disposable Postgres database via TEST_DATABASE_URL.
Verifies that deleting an app/keyword/user removes dependent rows without
manual cleanup, and that admin user deletion cancels the Stripe subscription
and deletes the workspace.
"""
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

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
    from app.database import Base
    import app.models.models  # noqa: F401 — registers all tables

    eng = create_engine(TEST_DB_URL.replace("+asyncpg", ""))
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover
        pytest.skip("TEST_DATABASE_URL is set but Postgres is unreachable")

    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db(engine):
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    Session = sessionmaker(bind=engine)
    s = Session()
    # Truncate all tables for a clean slate each test.
    tables = [
        "app_metric_snapshots", "ad_creatives", "ad_campaigns", "growth_events",
        "app_blowing_up_scores", "app_trending_scores", "app_discovered_keywords",
        "app_keyword_intelligence", "keyword_trends", "keyword_metrics",
        "app_keywords", "opportunities", "app_market_weakness", "feature_gaps",
        "app_analytics", "app_versions", "reviews", "rankings",
        "alert_events", "alerts", "workspace_usage", "subscriptions",
        "memberships", "favorites", "my_apps", "user_activity_log",
        "workspaces", "users", "apps", "categories", "keywords",
    ]
    for table in tables:
        try:
            s.execute(text(f"TRUNCATE {table} RESTART IDENTITY CASCADE"))
        except Exception:
            pass
    s.commit()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def client(engine):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine)

    def _override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


class TestAppCascadeDeletes:
    def test_app_delete_cascades_to_child_tables(self, db):
        from app.models.models import (
            App, Category, Ranking, Review, AppVersion, AppAnalytics,
            AppKeyword, Keyword, Opportunity, AppMarketWeakness, FeatureGap,
            AppTrendingScore, AppBlowingUpScore, AppMetricSnapshot,
            AdCreative, AdCampaign, GrowthEvent,
        )

        cat = Category(name="Games", slug="games")
        db.add(cat)
        db.flush()

        app = App(
            app_id="123456789",
            name="Test App",
            developer="Dev",
            category_id=cat.id,
        )
        db.add(app)
        db.flush()

        kw = Keyword(term="test keyword")
        db.add(kw)
        db.flush()

        db.add(Ranking(app_id=app.id, category_id=cat.id, chart_type="topfree", country="us", genre="all", rank=10))
        db.add(Review(app_id=app.id, review_id="rev-1", rating=5))
        db.add(AppVersion(app_id=app.id, version="1.0"))
        db.add(AppAnalytics(app_id=app.id))
        db.add(AppKeyword(app_id=app.id, keyword_id=kw.id))
        db.add(Opportunity(app_id=app.id, opportunity_type="keyword_gap"))
        db.add(AppMarketWeakness(app_id=app.id, country="us"))
        db.add(FeatureGap(app_id=app.id, feature_name="dark mode"))
        db.add(AppTrendingScore(app_id=app.id, country="us", trend_score=50))
        db.add(AppBlowingUpScore(app_id=app.id, country="us"))
        db.add(AppMetricSnapshot(app_id=app.id, snapshot_at=datetime.now(timezone.utc)))
        db.add(AdCreative(app_id=app.id, network="meta"))
        db.add(AdCampaign(app_id=app.id, network="meta", campaign_key="c1"))
        db.add(GrowthEvent(app_id=app.id, event_type="organic_breakout"))
        db.commit()

        assert db.query(App).filter(App.id == app.id).count() == 1
        db.delete(app)
        db.commit()

        assert db.query(App).filter(App.id == app.id).count() == 0
        assert db.query(Ranking).filter(Ranking.app_id == app.id).count() == 0
        assert db.query(Review).filter(Review.app_id == app.id).count() == 0
        assert db.query(AppVersion).filter(AppVersion.app_id == app.id).count() == 0
        assert db.query(AppAnalytics).filter(AppAnalytics.app_id == app.id).count() == 0
        assert db.query(AppKeyword).filter(AppKeyword.app_id == app.id).count() == 0
        assert db.query(Opportunity).filter(Opportunity.app_id == app.id).count() == 0
        assert db.query(AppMarketWeakness).filter(AppMarketWeakness.app_id == app.id).count() == 0
        assert db.query(FeatureGap).filter(FeatureGap.app_id == app.id).count() == 0
        assert db.query(AppTrendingScore).filter(AppTrendingScore.app_id == app.id).count() == 0
        assert db.query(AppBlowingUpScore).filter(AppBlowingUpScore.app_id == app.id).count() == 0
        assert db.query(AppMetricSnapshot).filter(AppMetricSnapshot.app_id == app.id).count() == 0
        assert db.query(AdCreative).filter(AdCreative.app_id == app.id).count() == 0
        assert db.query(AdCampaign).filter(AdCampaign.app_id == app.id).count() == 0
        assert db.query(GrowthEvent).filter(GrowthEvent.app_id == app.id).count() == 0


class TestKeywordCascadeDeletes:
    def test_keyword_delete_cascades_to_child_tables(self, db):
        from app.models.models import (
            App, Category, Keyword, KeywordMetrics, AppKeyword,
            AppKeywordIntelligence, KeywordTrend,
        )

        cat = Category(name="Tools", slug="tools")
        db.add(cat)
        db.flush()

        app = App(app_id="987654321", name="Tool App", developer="Dev", category_id=cat.id)
        db.add(app)
        db.flush()

        kw = Keyword(term="productivity")
        db.add(kw)
        db.flush()

        db.add(KeywordMetrics(keyword_id=kw.id))
        db.add(AppKeyword(app_id=app.id, keyword_id=kw.id))
        db.add(AppKeywordIntelligence(app_id=app.id, keyword_id=kw.id))
        db.add(KeywordTrend(keyword_id=kw.id, week_start=datetime.now(timezone.utc)))
        db.commit()

        db.delete(kw)
        db.commit()

        assert db.query(Keyword).filter(Keyword.id == kw.id).count() == 0
        assert db.query(KeywordMetrics).filter(KeywordMetrics.keyword_id == kw.id).count() == 0
        assert db.query(AppKeyword).filter(AppKeyword.keyword_id == kw.id).count() == 0
        assert db.query(AppKeywordIntelligence).filter(AppKeywordIntelligence.keyword_id == kw.id).count() == 0
        assert db.query(KeywordTrend).filter(KeywordTrend.keyword_id == kw.id).count() == 0


class TestAdminUserDeletion:
    def test_admin_delete_user_cancels_subscription_and_deletes_workspace(self, db, client):
        from app.models.models import User, Workspace, Membership, Subscription
        from app.services.auth_service import hash_password, create_access_token
        from app.services.billing import get_billing_provider

        # Create superadmin
        admin = User(
            email="admin@example.com",
            password_hash=hash_password("password123"),
            is_superadmin=True,
            is_active=True,
            email_verified=True,
        )
        db.add(admin)
        db.flush()

        # Create target user with workspace + paid Stripe subscription
        user = User(
            email="user@example.com",
            password_hash=hash_password("password123"),
            is_active=True,
            email_verified=True,
        )
        db.add(user)
        db.flush()

        ws = Workspace(name="User Workspace", slug="user-workspace")
        db.add(ws)
        db.flush()

        db.add(Membership(user_id=user.id, workspace_id=ws.id, role="owner"))
        sub = Subscription(
            workspace_id=ws.id,
            plan_code="pro",
            status="active",
            provider="stripe",
            provider_subscription_id="sub_12345",
        )
        db.add(sub)
        db.commit()

        user_id = user.id
        workspace_id = ws.id
        admin_token = create_access_token(admin.id, workspace_id=0)

        provider = get_billing_provider()
        with patch.object(provider, "cancel_subscription") as mock_cancel:
            with patch.object(provider, "is_configured", return_value=True):
                with patch("app.api.admin_console_router.get_billing_provider", return_value=provider):
                    response = client.delete(
                        f"/api/v1/admin-console/users/{user_id}",
                        headers={"Authorization": f"Bearer {admin_token}"},
                    )

        assert response.status_code == 200
        assert response.json()["ok"] is True
        mock_cancel.assert_called_once_with("sub_12345")

        # Refresh the test session so it sees changes committed by the API.
        db.expire_all()
        assert db.query(User).filter(User.id == user_id).count() == 0
        assert db.query(Workspace).filter(Workspace.id == workspace_id).count() == 0
        assert db.query(Subscription).filter(Subscription.workspace_id == workspace_id).count() == 0
        assert db.query(Membership).filter(Membership.workspace_id == workspace_id).count() == 0
