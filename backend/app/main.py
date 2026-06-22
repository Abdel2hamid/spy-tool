from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import logging
import time
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base
from app.api import router
from app.api.auth_router import router as auth_router
from app.workers.tasks import run_scrape_task, run_scoring_task
from app.workers.scheduler import scheduler, setup_scheduler, get_job_metrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_APP_START_TIME = time.monotonic()


_MIGRATIONS = [
    # Platform upgrade columns (Session 5)
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_installs_min INTEGER",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_installs_max INTEGER",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS install_confidence FLOAT",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_revenue_monthly_min FLOAT",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS estimated_revenue_monthly_max FLOAT",
    # Freshness priority system (Session 12)
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS freshness_score FLOAT DEFAULT 0.0",
    # Performance indexes (Session 12) — CREATE INDEX IF NOT EXISTS is idempotent
    "CREATE INDEX IF NOT EXISTS idx_app_rating ON apps (current_rating)",
    "CREATE INDEX IF NOT EXISTS idx_app_reviews ON apps (current_reviews)",
    "CREATE INDEX IF NOT EXISTS idx_app_rank ON apps (current_rank)",
    "CREATE INDEX IF NOT EXISTS idx_app_release_date ON apps (release_date)",
    "CREATE INDEX IF NOT EXISTS idx_app_created_at ON apps (created_at)",
    "CREATE INDEX IF NOT EXISTS idx_app_freshness ON apps (freshness_score)",
    "CREATE INDEX IF NOT EXISTS idx_app_developer ON apps (developer)",
    "CREATE INDEX IF NOT EXISTS idx_app_primary_category ON apps (primary_category)",
    # Keyword intelligence pipeline (Session 17)
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS trend_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS trend_growth FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS trend_velocity FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS apps_count INTEGER DEFAULT 0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS dominance_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS competition_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS cpc FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS opportunity_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS feasibility_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS last_enriched TIMESTAMPTZ",
    # keyword_trends table (Session 17) — explicit DDL since create_all won't add new cols
    """CREATE TABLE IF NOT EXISTS keyword_trends (
        id SERIAL PRIMARY KEY,
        keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
        week_start TIMESTAMPTZ NOT NULL,
        interest_score INTEGER DEFAULT 0,
        captured_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(keyword_id, week_start)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_ktrend_keyword ON keyword_trends (keyword_id)",
    # Keyword discovery engine (Session 21)
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS keyword_source VARCHAR(50)",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS discovered_from VARCHAR(255)",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ",
    # Keyword lifecycle status (Session 22)
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'raw'",
    # App keyword intelligence — extracted from title/subtitle/description (Session 22)
    """CREATE TABLE IF NOT EXISTS app_keyword_intelligence (
        id SERIAL PRIMARY KEY,
        app_id INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
        keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
        source VARCHAR(50),
        app_rank INTEGER,
        result_count INTEGER DEFAULT 0,
        search_volume INTEGER DEFAULT 0,
        difficulty FLOAT DEFAULT 0.0,
        traffic_score FLOAT DEFAULT 0.0,
        extracted_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(app_id, keyword_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_aki_app ON app_keyword_intelligence (app_id)",
    "CREATE INDEX IF NOT EXISTS idx_aki_traffic ON app_keyword_intelligence (app_id, traffic_score DESC)",
    # Keyword queue — decouples discovery from enrichment (Session 22)
    """CREATE TABLE IF NOT EXISTS keyword_queue (
        id SERIAL PRIMARY KEY,
        term VARCHAR(255) UNIQUE NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        priority INTEGER NOT NULL DEFAULT 0,
        source VARCHAR(50),
        added_at TIMESTAMPTZ DEFAULT NOW(),
        processed_at TIMESTAMPTZ
    )""",
    "CREATE INDEX IF NOT EXISTS idx_kwq_status_priority ON keyword_queue (status, priority)",
    "CREATE INDEX IF NOT EXISTS idx_kwq_added_at ON keyword_queue (added_at)",
    # App discovered keywords — autocomplete + affix expansion per app (Session 23)
    """CREATE TABLE IF NOT EXISTS app_discovered_keywords (
        id SERIAL PRIMARY KEY,
        app_id INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
        keyword VARCHAR(255) NOT NULL,
        source VARCHAR(50),
        source_keyword VARCHAR(255),
        search_volume INTEGER DEFAULT 0,
        difficulty FLOAT DEFAULT 0.0,
        traffic_score FLOAT DEFAULT 0.0,
        app_rank INTEGER,
        trend_score FLOAT DEFAULT 0.0,
        trend_direction VARCHAR(20) DEFAULT 'stable',
        opportunity_score FLOAT DEFAULT 0.0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(app_id, keyword)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_adk_app ON app_discovered_keywords (app_id)",
    "CREATE INDEX IF NOT EXISTS idx_adk_opp_score ON app_discovered_keywords (app_id, opportunity_score DESC)",
    # Phase-1 keyword discovery: competitor_rank + keyword_gap (Session 24)
    "ALTER TABLE app_discovered_keywords ADD COLUMN IF NOT EXISTS competitor_rank INTEGER",
    "ALTER TABLE app_discovered_keywords ADD COLUMN IF NOT EXISTS keyword_gap BOOLEAN DEFAULT FALSE",
    "CREATE INDEX IF NOT EXISTS idx_adk_gap ON app_discovered_keywords (app_id, keyword_gap)",
    # 3-table keyword architecture (Session 26)
    # keyword_metrics: normalised metrics separated from the keyword dictionary
    """CREATE TABLE IF NOT EXISTS keyword_metrics (
        id SERIAL PRIMARY KEY,
        keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
        search_volume INTEGER DEFAULT 0,
        difficulty FLOAT DEFAULT 0.0,
        trend_score FLOAT DEFAULT 0.0,
        last_updated TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(keyword_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_km_keyword_id ON keyword_metrics (keyword_id)",
    "CREATE INDEX IF NOT EXISTS idx_km_search_volume ON keyword_metrics (search_volume)",
    "CREATE INDEX IF NOT EXISTS idx_km_difficulty ON keyword_metrics (difficulty)",
    # app_keywords: add target-architecture columns (legacy position/relevance kept)
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS rank INTEGER",
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS traffic FLOAT DEFAULT 0.0",
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS opportunity_score FLOAT DEFAULT 0.0",
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS source VARCHAR(50)",
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
    "CREATE INDEX IF NOT EXISTS idx_ak_app_id ON app_keywords (app_id)",
    "CREATE INDEX IF NOT EXISTS idx_ak_keyword_id ON app_keywords (keyword_id)",
    "CREATE INDEX IF NOT EXISTS idx_ak_opportunity ON app_keywords (app_id, opportunity_score DESC)",
    # Keyword quality engine columns (new session)
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS quality_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS quality_tier VARCHAR(1)",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS validation_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS relevance_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS canonical_term VARCHAR(255)",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS times_seen INTEGER DEFAULT 1",
    "CREATE INDEX IF NOT EXISTS idx_kw_quality_score ON keywords (quality_score)",
    "CREATE INDEX IF NOT EXISTS idx_kw_quality_tier ON keywords (quality_tier)",
    "CREATE INDEX IF NOT EXISTS idx_kw_canonical ON keywords (canonical_term)",
    "CREATE INDEX IF NOT EXISTS idx_kw_last_seen ON keywords (last_seen_at)",
    # Precomputed trending scores (refreshed every 10 min by scheduler)
    """
    CREATE TABLE IF NOT EXISTS app_trending_scores (
        app_id INTEGER PRIMARY KEY REFERENCES apps(id) ON DELETE CASCADE,
        trend_score FLOAT NOT NULL DEFAULT 0.0,
        momentum_score FLOAT DEFAULT 0.0,
        momentum_3d FLOAT DEFAULT 0.0,
        momentum_7d FLOAT DEFAULT 0.0,
        consistency_score FLOAT DEFAULT 0.0,
        absolute_rank_bonus FLOAT DEFAULT 0.0,
        review_momentum FLOAT DEFAULT 0.0,
        confidence_factor FLOAT DEFAULT 1.0,
        computed_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_trending_score ON app_trending_scores (trend_score DESC)",
    # Reviews intelligence pipeline — sentiment column on reviews
    "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS sentiment VARCHAR(20)",
    "CREATE INDEX IF NOT EXISTS idx_review_sentiment ON reviews (app_id, sentiment)",
    # Apps Blowing Up — precomputed momentum score table
    """
    CREATE TABLE IF NOT EXISTS app_blowing_up_scores (
        app_id               INTEGER PRIMARY KEY REFERENCES apps(id) ON DELETE CASCADE,
        blowing_up_score     FLOAT NOT NULL DEFAULT 0.0,
        rank_velocity_score  FLOAT DEFAULT 0.0,
        rank_change_score    FLOAT DEFAULT 0.0,
        reviews_velocity_score FLOAT DEFAULT 0.0,
        chart_presence_score FLOAT DEFAULT 0.0,
        cross_market_score   FLOAT DEFAULT 0.0,
        consistency_score    FLOAT DEFAULT 0.0,
        confidence_score     FLOAT DEFAULT 0.0,
        rank_change          INTEGER DEFAULT 0,
        rank_velocity        FLOAT DEFAULT 0.0,
        reviews_velocity     FLOAT DEFAULT 0.0,
        chart_appearances    INTEGER DEFAULT 0,
        markets_count        INTEGER DEFAULT 0,
        badges               JSONB,
        why_flagged          JSONB,
        computed_at          TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_blowing_up_score ON app_blowing_up_scores (blowing_up_score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_blowing_up_confidence ON app_blowing_up_scores (confidence_score)",

    # ── Growth Intelligence Layer ──────────────────────────────────────────────
    # AppMetricSnapshot: time-series download + revenue snapshots (shared backbone)
    """
    CREATE TABLE IF NOT EXISTS app_metric_snapshots (
        id                            SERIAL PRIMARY KEY,
        app_id                        INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
        snapshot_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        estimated_downloads_min       INTEGER DEFAULT 0,
        estimated_downloads_max       INTEGER DEFAULT 0,
        install_confidence            FLOAT DEFAULT 0.0,
        estimated_revenue_monthly_min FLOAT DEFAULT 0.0,
        estimated_revenue_monthly_max FLOAT DEFAULT 0.0,
        revenue_confidence            FLOAT DEFAULT 0.0,
        monetization_model            VARCHAR(50),
        has_ads_signal                BOOLEAN DEFAULT FALSE,
        campaign_confidence           FLOAT DEFAULT 0.0,
        source_signals                JSONB
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ams_app_id      ON app_metric_snapshots (app_id)",
    "CREATE INDEX IF NOT EXISTS idx_ams_snapshot_at ON app_metric_snapshots (snapshot_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ams_app_time    ON app_metric_snapshots (app_id, snapshot_at DESC)",

    # AdCreative: individual ad creatives per app per network
    """
    CREATE TABLE IF NOT EXISTS ad_creatives (
        id                   SERIAL PRIMARY KEY,
        app_id               INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
        network              VARCHAR(50) NOT NULL,
        external_creative_id VARCHAR(255),
        format               VARCHAR(50),
        creative_url         TEXT,
        preview_url          TEXT,
        title                TEXT,
        body                 TEXT,
        cta                  VARCHAR(100),
        landing_url          TEXT,
        first_seen_at        TIMESTAMPTZ DEFAULT NOW(),
        last_seen_at         TIMESTAMPTZ DEFAULT NOW(),
        is_active            BOOLEAN DEFAULT TRUE,
        raw_payload          JSONB,
        UNIQUE(app_id, network, external_creative_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_creative_app     ON ad_creatives (app_id)",
    "CREATE INDEX IF NOT EXISTS idx_creative_active  ON ad_creatives (app_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_creative_network ON ad_creatives (network)",

    # AdCampaign: campaign-level aggregation per app per network
    """
    CREATE TABLE IF NOT EXISTS ad_campaigns (
        id                     SERIAL PRIMARY KEY,
        app_id                 INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
        network                VARCHAR(50) NOT NULL,
        campaign_key           VARCHAR(255) NOT NULL,
        first_seen_at          TIMESTAMPTZ DEFAULT NOW(),
        last_seen_at           TIMESTAMPTZ DEFAULT NOW(),
        active_creatives_count INTEGER DEFAULT 0,
        countries              JSONB,
        status                 VARCHAR(20) DEFAULT 'unknown',
        campaign_confidence    FLOAT DEFAULT 0.0,
        UNIQUE(app_id, network, campaign_key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_campaign_app    ON ad_campaigns (app_id)",
    "CREATE INDEX IF NOT EXISTS idx_campaign_status ON ad_campaigns (status)",

    # GrowthEvent: campaign / growth signals (pure derived intelligence)
    """
    CREATE TABLE IF NOT EXISTS growth_events (
        id                   SERIAL PRIMARY KEY,
        app_id               INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
        detected_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        event_type           VARCHAR(50) NOT NULL,
        confidence           FLOAT DEFAULT 0.0,
        explanation          TEXT,
        signals              JSONB,
        started_at_estimate  TIMESTAMPTZ,
        active_status        BOOLEAN DEFAULT TRUE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_growth_app      ON growth_events (app_id)",
    "CREATE INDEX IF NOT EXISTS idx_growth_type     ON growth_events (event_type)",
    "CREATE INDEX IF NOT EXISTS idx_growth_detected ON growth_events (detected_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_growth_active   ON growth_events (app_id, active_status)",

    # Daily Opportunity — one canonical opportunity per calendar day
    """CREATE TABLE IF NOT EXISTS daily_opportunities (
        id                  SERIAL PRIMARY KEY,
        date                DATE NOT NULL UNIQUE,
        keyword             VARCHAR(255),
        niche               VARCHAR(255),
        competition_score   FLOAT,
        trend_score         FLOAT,
        success_probability FLOAT,
        ai_summary          TEXT,
        related_apps        JSONB,
        full_data           JSONB,
        generated_at        TIMESTAMPTZ DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_daily_opp_date ON daily_opportunities (date DESC)",

    # Weekly Opportunities — top-5 ranked opportunities per ISO week
    """CREATE TABLE IF NOT EXISTS weekly_opportunities (
        id                SERIAL PRIMARY KEY,
        week_start_date   DATE NOT NULL,
        rank              INTEGER NOT NULL,
        keyword           VARCHAR(255),
        niche             VARCHAR(255),
        competition_score FLOAT,
        trend_score       FLOAT,
        success_probability FLOAT,
        opportunity_score FLOAT,
        ai_summary        TEXT,
        related_apps      JSONB,
        full_data         JSONB,
        generated_at      TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(week_start_date, rank)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_weekly_opp_week ON weekly_opportunities (week_start_date DESC)",

    # Phase 1 performance — fast ILIKE search via pg_trgm GIN indexes
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    "CREATE INDEX IF NOT EXISTS idx_apps_name_trgm        ON apps USING GIN (name gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS idx_apps_developer_trgm   ON apps USING GIN (developer gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS idx_apps_subtitle_trgm    ON apps USING GIN (subtitle gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS idx_apps_description_trgm ON apps USING GIN (description gin_trgm_ops)",
    # Phase 1 performance — category_id index for ranking queries
    "CREATE INDEX IF NOT EXISTS idx_rankings_category_id  ON rankings (category_id)",
    # Phase 4 performance — high-impact indexes for scoring/compute hot paths
    "CREATE INDEX IF NOT EXISTS idx_rankings_app_recorded ON rankings (app_id, recorded_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_app_date      ON reviews (app_id, date DESC)",
    "CREATE INDEX IF NOT EXISTS idx_feature_gaps_app_id   ON feature_gaps (app_id)",

    # Auth / Workspace tables
    """CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        full_name VARCHAR(255),
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)",

    """CREATE TABLE IF NOT EXISTS workspaces (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(255) NOT NULL UNIQUE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_workspaces_slug ON workspaces (slug)",

    """CREATE TABLE IF NOT EXISTS memberships (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        role VARCHAR(20) NOT NULL DEFAULT 'member',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, workspace_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_membership_user ON memberships (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_membership_workspace ON memberships (workspace_id)",

    """CREATE TABLE IF NOT EXISTS subscriptions (
        id SERIAL PRIMARY KEY,
        workspace_id INTEGER NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
        plan_code VARCHAR(50) NOT NULL DEFAULT 'trial',
        status VARCHAR(30) NOT NULL DEFAULT 'trialing',
        trial_ends_at TIMESTAMPTZ,
        stripe_customer_id VARCHAR(255),
        stripe_subscription_id VARCHAR(255),
        current_period_end TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_sub_workspace ON subscriptions (workspace_id)",
    "CREATE INDEX IF NOT EXISTS idx_sub_status ON subscriptions (status)",

    # Scalable ingestion pipeline — two-speed architecture (500K target)
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS ingestion_stage VARCHAR(20) DEFAULT 'full'",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS sync_tier VARCHAR(10) DEFAULT 'warm'",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS tier_computed_at TIMESTAMPTZ",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS last_enriched_at TIMESTAMPTZ",
    "ALTER TABLE discovery_queue ADD COLUMN IF NOT EXISTS enrich_mode VARCHAR(10) DEFAULT 'full'",
    "CREATE INDEX IF NOT EXISTS idx_app_ingestion_stage ON apps (ingestion_stage)",
    "CREATE INDEX IF NOT EXISTS idx_app_sync_tier ON apps (sync_tier)",
    "CREATE INDEX IF NOT EXISTS idx_app_tier_stage ON apps (sync_tier, ingestion_stage)",
    "CREATE INDEX IF NOT EXISTS idx_app_last_enriched ON apps (last_enriched_at)",

    # Plan limits — per-workspace monthly usage counters
    """CREATE TABLE IF NOT EXISTS workspace_usage (
        id SERIAL PRIMARY KEY,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        month VARCHAR(7) NOT NULL,
        app_imports INTEGER NOT NULL DEFAULT 0,
        keyword_refreshes INTEGER NOT NULL DEFAULT 0,
        ai_requests INTEGER NOT NULL DEFAULT 0,
        exports INTEGER NOT NULL DEFAULT 0,
        UNIQUE(workspace_id, month)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_workspace_usage_ws ON workspace_usage (workspace_id)",

    # Production audit indexes (memory/query optimization)
    "CREATE INDEX IF NOT EXISTS idx_review_app_sentiment ON reviews (app_id, sentiment)",
    "CREATE INDEX IF NOT EXISTS idx_review_app_rating ON reviews (app_id, rating)",
    "CREATE INDEX IF NOT EXISTS idx_app_version_date ON app_versions (app_id, release_date DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ranking_category_date ON rankings (category_id, recorded_at)",
    "CREATE INDEX IF NOT EXISTS idx_kw_status ON keywords (status)",
    "CREATE INDEX IF NOT EXISTS idx_app_ingestion ON apps (ingestion_stage, sync_tier)",
    "CREATE INDEX IF NOT EXISTS idx_app_developer_id ON apps (developer_id)",
    "CREATE INDEX IF NOT EXISTS idx_opportunity_app_id ON opportunities (app_id)",

    # Scalability audit indexes (100K apps, 1M keywords)
    "CREATE INDEX IF NOT EXISTS idx_kw_source ON keywords (keyword_source)",
    "CREATE INDEX IF NOT EXISTS idx_kss_keyword_country_captured ON keyword_search_snapshots (keyword, country, captured_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_opportunity_app_keyword ON opportunities (app_id, primary_keyword)",
    "CREATE INDEX IF NOT EXISTS idx_app_last_updated ON apps (last_updated)",
    "CREATE INDEX IF NOT EXISTS idx_review_review_id ON reviews (review_id)",
    "CREATE INDEX IF NOT EXISTS idx_rankings_recorded_at ON rankings (recorded_at DESC)",

    # Favorites (user bookmarks)
    """CREATE TABLE IF NOT EXISTS favorites (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        app_id INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, app_id)
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_favorite_user_app ON favorites (user_id, app_id)",
    "CREATE INDEX IF NOT EXISTS idx_favorite_workspace ON favorites (workspace_id)",

    # My Apps — user's own apps (ASO optimization targets)
    """CREATE TABLE IF NOT EXISTS my_apps (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        app_id INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, app_id)
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_myapp_user_app ON my_apps (user_id, app_id)",
    "CREATE INDEX IF NOT EXISTS idx_myapp_workspace ON my_apps (workspace_id)",

    # ── Keyword Scoring V2 (multi-signal fusion + per-app chance) ─────────
    # New columns on keywords table
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS volume_score FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS difficulty_v2 FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS autocomplete_rank INTEGER DEFAULT 0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS top5_avg_ratings FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS incumbent_strength FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS title_saturation FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS brand_dominance FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS market_concentration FLOAT DEFAULT 0.0",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS top_player VARCHAR(255)",
    "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS brand_count INTEGER DEFAULT 0",
    "CREATE INDEX IF NOT EXISTS idx_kw_volume_score ON keywords (volume_score)",
    "CREATE INDEX IF NOT EXISTS idx_kw_difficulty_v2 ON keywords (difficulty_v2)",
    # New columns on app_keywords table (per-app scoring)
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS chance_score FLOAT DEFAULT 0.0",
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS kei FLOAT DEFAULT 0.0",
    "ALTER TABLE app_keywords ADD COLUMN IF NOT EXISTS estimated_installs FLOAT DEFAULT 0.0",
    "CREATE INDEX IF NOT EXISTS idx_ak_chance ON app_keywords (app_id, chance_score)",
    "CREATE INDEX IF NOT EXISTS idx_ak_kei ON app_keywords (app_id, kei)",

    # ── Keyword data cleanup: purge junk from alphabet expansion ──────────
    # Delete keywords ending in isolated single/double letters (e.g. "timer x", "exercise s j")
    # Pattern: " x" or " x y" at end of term — uses PostgreSQL ~ regex operator
    """DELETE FROM keyword_queue WHERE keyword_id IN (SELECT id FROM keywords WHERE term ~ ' [a-z]( [a-z])*$')""",
    """DELETE FROM app_keywords WHERE keyword_id IN (SELECT id FROM keywords WHERE term ~ ' [a-z]( [a-z])*$')""",
    """DELETE FROM keyword_trends WHERE keyword_id IN (SELECT id FROM keywords WHERE term ~ ' [a-z]( [a-z])*$')""",
    """DELETE FROM keywords WHERE term ~ ' [a-z]( [a-z])*$'""",
    # Also purge from app_discovered_keywords
    """DELETE FROM app_discovered_keywords WHERE keyword ~ ' [a-z]( [a-z])*$'""",
    # Reset enrichment status so pipeline re-scores everything with v2
    "UPDATE keywords SET status = 'raw', volume_score = 0, difficulty_v2 = 0 WHERE volume_score = 0 AND status != 'raw'",

    # Admin console — superadmin flag on users
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superadmin BOOLEAN NOT NULL DEFAULT FALSE",

    # Admin activity log
    """CREATE TABLE IF NOT EXISTS admin_activity_log (
        id SERIAL PRIMARY KEY,
        admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        action VARCHAR(100) NOT NULL,
        target_type VARCHAR(50),
        target_id INTEGER,
        details JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_admin_activity_created ON admin_activity_log (created_at DESC)",

    # User activity log
    """CREATE TABLE IF NOT EXISTS user_activity_log (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        action VARCHAR(100) NOT NULL,
        detail VARCHAR(500),
        metadata JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_user_activity_user ON user_activity_log (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_user_activity_created ON user_activity_log (created_at DESC)",

    # Announcements
    """CREATE TABLE IF NOT EXISTS announcements (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        message TEXT NOT NULL,
        type VARCHAR(20) NOT NULL DEFAULT 'info',
        is_active BOOLEAN DEFAULT TRUE,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    # Admin settings key-value store (payment gateways, plan config)
    """CREATE TABLE IF NOT EXISTS admin_settings (
        id SERIAL PRIMARY KEY,
        key VARCHAR(100) UNIQUE NOT NULL,
        value TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_admin_settings_key ON admin_settings (key)",

    # Alerts system — user-defined alert rules + triggered events
    """CREATE TABLE IF NOT EXISTS alerts (
        id SERIAL PRIMARY KEY,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        alert_type VARCHAR(50) NOT NULL,
        name VARCHAR(200) NOT NULL,
        config JSONB NOT NULL DEFAULT '{}',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_alert_workspace ON alerts (workspace_id)",
    "CREATE INDEX IF NOT EXISTS idx_alert_user ON alerts (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_alert_type ON alerts (alert_type)",

    """CREATE TABLE IF NOT EXISTS alert_events (
        id SERIAL PRIMARY KEY,
        alert_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        title VARCHAR(300) NOT NULL,
        message TEXT,
        data JSONB,
        is_read BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_alert_event_workspace ON alert_events (workspace_id)",
    "CREATE INDEX IF NOT EXISTS idx_alert_event_alert ON alert_events (alert_id)",
    "CREATE INDEX IF NOT EXISTS idx_alert_event_read ON alert_events (workspace_id, is_read)",
    # Email verification
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE",
    # Mark all existing users as verified (they signed up before this feature)
    "UPDATE users SET email_verified = TRUE WHERE email_verified = FALSE AND created_at < NOW() - INTERVAL '1 minute'",

    # RankSpy search — app source tracking + full-text search
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'tracked'",
    "ALTER TABLE apps ADD COLUMN IF NOT EXISTS discovered_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS idx_app_source ON apps (source)",
    "CREATE INDEX IF NOT EXISTS idx_app_discovered_at ON apps (discovered_at)",
    # Backfill: existing apps are 'tracked'
    "UPDATE apps SET source = 'tracked' WHERE source IS NULL",
]


def _run_migrations(db_engine):
    """Apply additive migrations (ADD COLUMN IF NOT EXISTS) on every startup."""
    with db_engine.connect() as conn:
        for sql in _MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as exc:
                conn.rollback()
                logger.warning(f"Migration skipped ({exc})")


async def _initial_scrape_background():
    """Run initial scrape + scoring in the background so server starts immediately."""
    try:
        logger.info("Background: starting initial scrape...")
        await run_scrape_task()
        logger.info("Background: initial scrape complete")
    except Exception as e:
        logger.warning(f"Background: initial scrape failed: {e}")
    try:
        await asyncio.to_thread(run_scoring_task)
        logger.info("Background: initial scoring complete")
    except Exception as e:
        logger.warning(f"Background: initial scoring failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RankSpy...")

    # Ensure all DB tables exist
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

    # Safe migrations: add new columns to existing tables if absent
    _run_migrations(engine)

    # Startup scrape disabled — the scheduler handles all scraping on its own schedule.
    # asyncio.create_task(_initial_scrape_background())

    # Start the recurring scheduler.  Jobs are registered with start_date
    # offsets so they don't pile on top of the startup scrape.
    setup_scheduler()
    scheduler.start()
    logger.info(f"Scheduler started — {len(scheduler.get_jobs())} recurring jobs registered")

    yield

    # Graceful shutdown: don't wait for running jobs to finish
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
    logger.info("Shutting down RankSpy...")


app = FastAPI(
    title=settings.app_name,
    description="AI-powered App Store intelligence and opportunity detection",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token", "Stripe-Signature"],
)

from app.api.admin_console_router import router as admin_console_router
from app.api.stripe_router import router as stripe_router


# ── Global auth middleware ────────────────────────────────────────────────
# Requires a valid Bearer JWT on all /api/v1/ routes except a small
# whitelist (auth endpoints, Stripe webhooks, health, categories).
# This is a safety net — individual endpoints still declare their own
# auth dependencies, but this catches any that were missed.
# ────────────────────────────────────────────────────────────────────────

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as StarletteJSON


_PUBLIC_PREFIXES = (
    "/api/v1/auth/",           # login, register, me
    "/api/v1/stripe/webhook",  # Stripe webhook (has its own sig verification)
    "/api/v1/stripe/config",   # public publishable key
    "/api/v1/admin-console/announcements/active",  # public announcements
)

_PUBLIC_EXACT = {
    "/", "/health", "/api/v1/categories", "/api/v1/run-migrations", "/run-migrations",
}


class _AuthGateMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated requests to /api/v1/ data endpoints."""

    def _cors_headers(self, request) -> dict[str, str]:
        """Build CORS headers for error responses (middleware is outermost)."""
        origin = request.headers.get("origin", "")
        allowed = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
        if origin and origin in allowed:
            return {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
            }
        return {}

    async def dispatch(self, request, call_next):
        path = request.url.path

        # Skip non-API routes (Next.js static, etc.)
        if not path.startswith("/api/v1/"):
            return await call_next(request)

        # Skip OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip explicitly public paths
        if path in _PUBLIC_EXACT:
            return await call_next(request)
        for prefix in _PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Require Authorization header
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return StarletteJSON(
                status_code=401,
                content={"detail": "Not authenticated"},
                headers={
                    "WWW-Authenticate": "Bearer",
                    **self._cors_headers(request),
                },
            )

        # Token validity is verified downstream by deps.py / route dependencies.
        # This middleware only ensures the header exists.
        return await call_next(request)


# Add AFTER CORSMiddleware so CORS headers are applied to 401 responses
app.add_middleware(_AuthGateMiddleware)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")
app.include_router(admin_console_router, prefix="/api/v1")
app.include_router(stripe_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all: log the real error and return a CORS-safe 500 response.

    Starlette's CORSMiddleware does NOT add CORS headers to responses
    generated by the outermost ServerErrorMiddleware (i.e. unhandled
    exceptions that bubble past ExceptionMiddleware).  By registering
    an explicit handler here, the response goes through the normal
    ASGI send path so CORSMiddleware can add its headers.
    """
    logger.exception(
        "Unhandled exception in %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    origin = request.headers.get("origin")
    allowed = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    headers: dict[str, str] = {}
    if origin and origin in allowed:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {exc}"},
        headers=headers,
    )


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/run-migrations")
@app.get("/api/v1/run-migrations")
def run_migrations_endpoint():
    """Manually trigger migrations (temporary)."""
    results = []
    with engine.connect() as conn:
        for sql in _MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
                results.append({"sql": sql[:80], "status": "ok"})
            except Exception as exc:
                conn.rollback()
                results.append({"sql": sql[:80], "status": f"FAILED: {exc}"})
    failed = [r for r in results if r["status"] != "ok"]
    return {"ok": len(failed) == 0, "total": len(results), "failed": failed}


@app.get("/health")
def health_check():
    """Real health check: verifies DB connectivity and scheduler state."""
    t0 = time.monotonic()
    status = "healthy"
    checks: dict = {}

    # 1. Database connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        status = "degraded"

    # 2. Scheduler
    try:
        if scheduler.running:
            checks["scheduler"] = "running"
        else:
            checks["scheduler"] = "stopped"
            status = "degraded"
    except Exception as exc:
        checks["scheduler"] = f"error: {exc}"
        status = "degraded"

    # 3. Ranking health — critical data pipeline check
    ranking_health = {}
    try:
        from datetime import timezone as _tz
        from sqlalchemy import func as sqla_func
        from app.database import SessionLocal
        from app.models.models import Ranking

        _db = SessionLocal()
        try:
            newest = _db.query(sqla_func.max(Ranking.recorded_at)).scalar()
            if newest is not None:
                if newest.tzinfo is None:
                    newest = newest.replace(tzinfo=_tz.utc)
                from datetime import datetime as _dt
                age_hours = (_dt.now(_tz.utc) - newest).total_seconds() / 3600
                cutoff_24h = _dt.now(_tz.utc) - __import__("datetime").timedelta(hours=24)
                count_24h = (
                    _db.query(sqla_func.count(Ranking.id))
                    .filter(Ranking.recorded_at >= cutoff_24h)
                    .scalar() or 0
                )
                if age_hours < 6:
                    r_status = "healthy"
                elif age_hours < 24:
                    r_status = "stale"
                else:
                    r_status = "critical"
                    if status == "healthy":
                        status = "degraded"
                ranking_health = {
                    "latest_ranking_recorded_at": newest.isoformat(),
                    "ranking_age_hours": round(age_hours, 1),
                    "rankings_last_24h": count_24h,
                    "ranking_status": r_status,
                }
            else:
                ranking_health = {
                    "latest_ranking_recorded_at": None,
                    "ranking_age_hours": None,
                    "rankings_last_24h": 0,
                    "ranking_status": "critical",
                }
                if status == "healthy":
                    status = "degraded"
        finally:
            _db.close()
    except Exception as exc:
        ranking_health = {"error": str(exc)}

    # 4. Scheduled jobs — next run times
    jobs = []
    try:
        for job in scheduler.get_jobs():
            nrt = job.next_run_time
            jobs.append({
                "id": job.id,
                "next_run": nrt.isoformat() if nrt else None,
            })
    except Exception:
        pass

    # 5. Connection pool status — critical for diagnosing pool exhaustion
    pool_status = {}
    try:
        pool = engine.pool
        pool_status = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "max_overflow": pool._max_overflow,
            "total_connections": pool.checkedin() + pool.checkedout(),
        }
    except Exception as exc:
        pool_status = {"error": str(exc)}

    return {
        "status": status,
        "uptime_seconds": round(time.monotonic() - _APP_START_TIME, 1),
        "checks": checks,
        "ranking_health": ranking_health,
        "pool_status": pool_status,
        "scheduler_jobs": jobs,
        "job_metrics": get_job_metrics(),
        "response_ms": round((time.monotonic() - t0) * 1000, 1),
    }
