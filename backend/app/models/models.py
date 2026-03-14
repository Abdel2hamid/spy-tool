import enum

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Index, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class KeywordStatus(str, enum.Enum):
    """Lifecycle state of a keyword in the enrichment pipeline."""
    RAW = "raw"          # inserted, not yet enriched
    ENRICHED = "enriched"  # enrichment pipeline has run at least once
    PRUNED = "pruned"    # marked stale; will be deleted on next cleanup pass


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    icon = Column(String(512))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    apps = relationship("App", back_populates="category")
    rankings = relationship("Ranking", back_populates="category")


class App(Base):
    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(500), nullable=False)
    subtitle = Column(String(500))
    description = Column(Text)
    developer = Column(String(500))
    developer_id = Column(String(100))
    icon_url = Column(String(512))
    screenshots = Column(JSON)
    primary_category = Column(String(255))
    secondary_category = Column(String(255))
    price = Column(Float, default=0)
    currency = Column(String(10), default="USD")
    is_free = Column(Boolean, default=True)
    in_app_purchases = Column(JSON)
    current_version = Column(String(50))
    minimum_ios_version = Column(String(50))
    supported_languages = Column(JSON)
    release_date = Column(DateTime(timezone=True))
    last_updated = Column(DateTime(timezone=True))
    content_rating = Column(String(50))
    current_rating = Column(Float)
    current_reviews = Column(Integer, default=0)
    current_rank = Column(Integer)
    category_id = Column(Integer, ForeignKey("categories.id"))
    url = Column(String(512))
    estimated_installs_min = Column(Integer)
    estimated_installs_max = Column(Integer)
    install_confidence = Column(Float)
    estimated_revenue_monthly_min = Column(Float)
    estimated_revenue_monthly_max = Column(Float)
    # Freshness: 100 = released <30d ago, 0 = >1yr old. Updated on every scrape.
    freshness_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    category = relationship("Category", back_populates="apps")
    rankings = relationship("Ranking", back_populates="app", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="app", cascade="all, delete-orphan")
    keywords = relationship("AppKeyword", back_populates="app", cascade="all, delete-orphan")
    opportunities = relationship("Opportunity", back_populates="app", cascade="all, delete-orphan")
    versions = relationship("AppVersion", back_populates="app", cascade="all, delete-orphan")
    analytics = relationship("AppAnalytics", back_populates="app", cascade="all, delete-orphan")
    market_weakness = relationship("AppMarketWeakness", back_populates="app", cascade="all, delete-orphan")
    feature_gaps = relationship("FeatureGap", back_populates="app", cascade="all, delete-orphan")
    trending_score = relationship("AppTrendingScore", back_populates="app", uselist=False, cascade="all, delete-orphan")
    blowing_up_score = relationship("AppBlowingUpScore", back_populates="app", uselist=False, cascade="all, delete-orphan")
    metric_snapshots = relationship("AppMetricSnapshot", back_populates="app", cascade="all, delete-orphan")
    ad_creatives = relationship("AdCreative", back_populates="app", cascade="all, delete-orphan")
    ad_campaigns = relationship("AdCampaign", back_populates="app", cascade="all, delete-orphan")
    growth_events = relationship("GrowthEvent", back_populates="app", cascade="all, delete-orphan")

    __table_args__ = (
        # Composite index used by filtered list queries
        Index("idx_app_category_rank", "category_id", "current_rank"),
        # Individual column indexes for sort / filter performance
        Index("idx_app_rating", "current_rating"),
        Index("idx_app_reviews", "current_reviews"),
        Index("idx_app_rank", "current_rank"),
        Index("idx_app_release_date", "release_date"),
        Index("idx_app_created_at", "created_at"),
        Index("idx_app_freshness", "freshness_score"),
        Index("idx_app_developer", "developer"),
        Index("idx_app_primary_category", "primary_category"),
    )


class Ranking(Base):
    __tablename__ = "rankings"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    chart_type = Column(String(50), nullable=False)
    rank = Column(Integer, nullable=False)
    previous_rank = Column(Integer)
    rank_velocity = Column(Float, default=0)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    app = relationship("App", back_populates="rankings")
    category = relationship("Category", back_populates="rankings")

    __table_args__ = (
        Index("idx_ranking_app_date", "app_id", "recorded_at"),
        Index("idx_ranking_chart_date", "chart_type", "recorded_at"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    review_id = Column(String(100), unique=True)
    user_name = Column(String(255))
    user_url = Column(String(512))
    rating = Column(Integer)
    title = Column(String(500))
    content = Column(Text)
    date = Column(DateTime(timezone=True))
    app_version = Column(String(50))
    storefront = Column(String(10))
    is_updated = Column(Boolean, default=False)
    developer_reply_text = Column(Text)
    developer_reply_date = Column(DateTime(timezone=True))
    helpful_count = Column(Integer, default=0)
    sentiment = Column(String(20))  # positive / neutral / negative
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    app = relationship("App", back_populates="reviews")

    __table_args__ = (
        Index("idx_review_app_date", "app_id", "date"),
    )


class AppVersion(Base):
    __tablename__ = "app_versions"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    version = Column(String(50), nullable=False)
    release_date = Column(DateTime(timezone=True))
    release_notes = Column(Text)
    is_latest = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    app = relationship("App", back_populates="versions")

    __table_args__ = (
        Index("idx_app_version", "app_id", "version"),
    )


class AppAnalytics(Base):
    __tablename__ = "app_analytics"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    review_growth_30d = Column(Float, default=0)
    review_growth_90d = Column(Float, default=0)
    rating_change_30d = Column(Float, default=0)
    rating_change_90d = Column(Float, default=0)
    sentiment_score = Column(Float, default=0)
    sentiment_label = Column(String(50))
    common_complaints = Column(JSON)
    common_features = Column(JSON)
    positive_themes = Column(JSON)
    bug_keywords = Column(JSON)
    churn_risk_score = Column(Float, default=0)
    update_cadence_score = Column(Float, default=0)
    quality_score = Column(Float, default=0)
    opportunity_score = Column(Float, default=0)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    app = relationship("App", back_populates="analytics")

    __table_args__ = (
        Index("idx_analytics_app_computed", "app_id", "computed_at"),
    )


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    term = Column(String(255), unique=True, nullable=False, index=True)
    # Legacy / internal estimates (kept for backwards compatibility)
    search_volume = Column(Integer, default=0)
    difficulty = Column(Float, default=0)
    trend = Column(Float, default=0)
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    # ── External signal columns (populated by KeywordIntelligencePipeline) ──
    # Google Trends signals
    trend_score = Column(Float, default=0.0)        # 0-100 relative interest (Google Trends avg)
    trend_growth = Column(Float, default=0.0)       # % growth last 4 weeks vs prior 4 weeks
    trend_velocity = Column(Float, default=0.0)     # last week vs recent avg (momentum)
    # Apple App Store signals
    apps_count = Column(Integer, default=0)         # apps found for this keyword in iTunes search
    dominance_score = Column(Float, default=0.0)    # top-app market dominance (0-100)
    # DataForSEO signals (optional)
    competition_score = Column(Float, default=0.0)  # 0-100 competition index
    cpc = Column(Float, default=0.0)                # cost per click (USD)
    # Unified scores (computed from all signals)
    opportunity_score = Column(Float, default=0.0)  # 0-100 market opportunity
    feasibility_score = Column(Float, default=0.0)  # 0-100 indie entry feasibility
    # Housekeeping
    last_enriched = Column(DateTime(timezone=True)) # last time external data was fetched
    # Discovery metadata
    keyword_source = Column(String(50))             # 'seed' | 'discovery_engine' | 'user'
    discovered_from = Column(String(255))           # which seed term led to this keyword
    first_seen_at = Column(DateTime(timezone=True)) # when first inserted by discovery engine
    # Lifecycle status (KeywordStatus enum values stored as VARCHAR)
    status = Column(String(20), nullable=False, server_default=KeywordStatus.RAW.value,
                    default=KeywordStatus.RAW.value)
    # ── Quality engine columns (populated by KeywordQualityEngine) ────────────
    quality_score    = Column(Float,   default=0.0)    # 0-100 composite quality score
    quality_tier     = Column(String(1), nullable=True) # 'A'|'B'|'C'|None
    validation_score = Column(Float,   default=0.0)    # Apple component (0-25)
    relevance_score  = Column(Float,   default=0.0)    # app-context overlap (0-5)
    canonical_term   = Column(String(255), nullable=True)  # normalized for dedup
    last_seen_at     = Column(DateTime(timezone=True), nullable=True)  # last time generated
    times_seen       = Column(Integer, default=1)       # how many times discovered

    apps = relationship("AppKeyword", back_populates="keyword")
    metrics = relationship("KeywordMetrics", back_populates="keyword", uselist=False, cascade="all, delete-orphan")
    trends = relationship("KeywordTrend", back_populates="keyword", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_keyword_opp_score", "opportunity_score"),
        Index("idx_keyword_trend_score", "trend_score"),
        Index("idx_keyword_enriched", "last_enriched"),
        Index("idx_kw_quality_score", "quality_score"),
        Index("idx_kw_quality_tier", "quality_tier"),
        Index("idx_kw_canonical", "canonical_term"),
        Index("idx_kw_last_seen", "last_seen_at"),
    )


class KeywordMetrics(Base):
    """
    Normalised keyword metrics table — separates intelligence signals from the
    keyword dictionary so the keywords table stays lean.

    One row per keyword (1-1 with keywords.id).
    Populated/updated by the KeywordIntelligencePipeline enrichment phases.
    """
    __tablename__ = "keyword_metrics"

    id = Column(Integer, primary_key=True, index=True)
    keyword_id = Column(
        Integer,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    search_volume = Column(Integer, default=0)
    difficulty = Column(Float, default=0.0)
    trend_score = Column(Float, default=0.0)
    last_updated = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    keyword = relationship("Keyword", back_populates="metrics")

    __table_args__ = (
        Index("idx_km_keyword_id", "keyword_id"),
        Index("idx_km_search_volume", "search_volume"),
        Index("idx_km_difficulty", "difficulty"),
    )


class AppKeyword(Base):
    __tablename__ = "app_keywords"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=False)
    # Legacy columns (keyword search tracker)
    position = Column(Integer)
    relevance = Column(Float, default=0)
    # New target-architecture columns
    rank = Column(Integer)                       # app's position for this keyword in iTunes
    traffic = Column(Float, default=0.0)         # estimated traffic score
    opportunity_score = Column(Float, default=0.0)
    source = Column(String(50))                  # 'extracted'|'discovered'|'alphabet'|'competitor'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    app = relationship("App", back_populates="keywords")
    keyword = relationship("Keyword", back_populates="apps")

    __table_args__ = (
        Index("idx_app_keyword", "app_id", "keyword_id", unique=True),
        Index("idx_ak_app_id", "app_id"),
        Index("idx_ak_keyword_id", "keyword_id"),
        Index("idx_ak_opportunity", "app_id", "opportunity_score"),
    )


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"))
    opportunity_type = Column(String(50), nullable=False)
    primary_keyword = Column(String(255))
    competition_score = Column(Float, default=0)
    trend_score = Column(Float, default=0)
    success_probability = Column(Float, default=0)
    ai_integration_potential = Column(Float, default=0)
    recommendation = Column(Text)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    app = relationship("App", back_populates="opportunities")

    __table_args__ = (
        Index("idx_opportunity_type", "opportunity_type"),
        Index("idx_opportunity_probability", "success_probability"),
    )


class AppMarketWeakness(Base):
    __tablename__ = "app_market_weakness"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    country = Column(String(10), nullable=False)
    total_reviews = Column(Integer, default=0)
    negative_reviews = Column(Integer, default=0)
    average_rating = Column(Float, default=0)
    negative_ratio = Column(Float, default=0)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    app = relationship("App", back_populates="market_weakness")

    __table_args__ = (
        Index("idx_market_weakness_app", "app_id"),
        Index("idx_market_weakness_app_country", "app_id", "country", unique=True),
        Index("idx_market_weakness_ratio", "negative_ratio"),
    )


class FeatureGap(Base):
    __tablename__ = "feature_gaps"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    feature_name = Column(String(255), nullable=False)
    mentions = Column(Integer, default=1)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())

    app = relationship("App", back_populates="feature_gaps")

    __table_args__ = (
        Index("idx_feature_gap_app", "app_id"),
        Index("idx_feature_gap_app_feature", "app_id", "feature_name", unique=True),
        Index("idx_feature_gap_mentions", "mentions"),
    )


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False, unique=True)
    top_trending_apps = Column(JSON)
    opportunity_of_day = Column(JSON)
    category_insights = Column(JSON)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class KeywordSearchSnapshot(Base):
    """
    One row per (keyword, country, app, captured_at) — stores a point-in-time
    snapshot of App Store search results including sponsored placement detection.
    """
    __tablename__ = "keyword_search_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(255), nullable=False)
    country = Column(String(10), nullable=False, default="us")
    app_id = Column(String(100), nullable=False)  # App Store numeric ID as string
    app_name = Column(String(500))
    developer = Column(String(500))
    icon_url = Column(String(512))
    position = Column(Integer, nullable=False)          # absolute position on page (1-based)
    organic_position = Column(Integer)                  # position among non-sponsored results
    is_sponsored = Column(Boolean, default=False)
    captured_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_kss_keyword", "keyword"),
        Index("idx_kss_app_id", "app_id"),
        Index("idx_kss_captured_at", "captured_at"),
        Index("idx_kss_keyword_app", "keyword", "app_id"),
        Index("idx_kss_keyword_captured", "keyword", "captured_at"),
    )


class DiscoveryQueue(Base):
    """
    Persistent queue of app IDs awaiting full scrape.
    Populated by chart/keyword/developer discovery; drained by queue_processor job.
    """
    __tablename__ = "discovery_queue"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    # pending → scraping → done | failed
    priority = Column(Integer, nullable=False, default=0, index=True)
    # higher priority → processed first; keyword hits get priority=2, chart=1
    source = Column(String(255))          # e.g. "chart:topfreeapplications:us:6007"
    failed_attempts = Column(Integer, default=0)
    added_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    processed_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_dq_status_priority", "status", "priority"),
        Index("idx_dq_added_at", "added_at"),
    )


class DiscoveryProgress(Base):
    """
    Tracks which discovery sources (charts, keywords, developers) have
    already been scanned, so the crawler resumes where it left off.
    """
    __tablename__ = "discovery_progress"

    id = Column(Integer, primary_key=True, index=True)
    source_key = Column(String(255), unique=True, nullable=False, index=True)
    # e.g. "chart:topfreeapplications:us:6007" or "keyword:fitness"
    last_run = Column(DateTime(timezone=True))
    apps_found = Column(Integer, default=0)   # cumulative IDs found from this source

    __table_args__ = (
        Index("idx_dp_source_key", "source_key"),
        Index("idx_dp_last_run", "last_run"),
    )


class AppIdea(Base):
    __tablename__ = "app_ideas"

    id = Column(Integer, primary_key=True, index=True)
    idea_title = Column(String(500), nullable=False, unique=True)
    idea_description = Column(Text)
    opportunity_score = Column(Float, default=0.0)
    pattern_type = Column(String(50), nullable=False)  # 'feature_gap' | 'weak_market' | 'keyword_gap'
    related_app_ids = Column(JSON, default=list)
    reasoning = Column(JSON, default=list)
    signals = Column(JSON, default=dict)
    primary_keyword = Column(String(255))
    category = Column(String(255))
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_idea_score", "opportunity_score"),
        Index("idx_idea_pattern", "pattern_type"),
        Index("idx_idea_category", "category"),
    )


class AppKeywordIntelligence(Base):
    """
    Per-(app, keyword) intelligence extracted from the app's own metadata
    (title, subtitle, description) and enriched via iTunes Search API.
    Separate from AppKeyword which tracks keyword search-rank snapshots.
    """
    __tablename__ = "app_keyword_intelligence"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    keyword_id = Column(Integer, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(50))          # 'title' | 'subtitle' | 'description'
    app_rank = Column(Integer)           # position of this app in iTunes results (None if absent)
    result_count = Column(Integer, default=0)   # total iTunes results for keyword
    search_volume = Column(Integer, default=0)  # heuristic 0-100
    difficulty = Column(Float, default=0.0)     # heuristic 0-100
    traffic_score = Column(Float, default=0.0)  # search_volume × CTR(rank)
    extracted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_aki_app", "app_id"),
        Index("idx_aki_app_kw", "app_id", "keyword_id", unique=True),
        Index("idx_aki_traffic", "app_id", "traffic_score"),
    )


class KeywordQueue(Base):
    """
    Decouples keyword discovery from enrichment.
    KeywordDiscoveryEngine writes here; KeywordIntelligencePipeline drains it.
    """
    __tablename__ = "keyword_queue"

    id = Column(Integer, primary_key=True, index=True)
    term = Column(String(255), unique=True, nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    # pending → enriching → done | failed
    priority = Column(Integer, nullable=False, default=0)
    # higher = processed first; discovery_engine=1, seed=2, user=3
    source = Column(String(50))           # 'discovery_engine' | 'seed' | 'user'
    added_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    processed_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_kwq_status_priority", "status", "priority"),
        Index("idx_kwq_added_at", "added_at"),
    )


class AppDiscoveredKeyword(Base):
    """
    Keywords discovered for an app via autocomplete expansion + enrichment.
    Populated by KeywordDiscoveryService; separate from app_keyword_intelligence
    (which is extracted from the app's own text).
    """
    __tablename__ = "app_discovered_keywords"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    keyword = Column(String(255), nullable=False)
    source = Column(String(50))           # 'autocomplete'|'prefix'|'suffix'|'alphabet'|'competitor'
    source_keyword = Column(String(255))  # which seed keyword generated this
    search_volume = Column(Integer, default=0)
    difficulty = Column(Float, default=0.0)
    traffic_score = Column(Float, default=0.0)
    app_rank = Column(Integer)            # app's position in iTunes results; None if absent
    competitor_rank = Column(Integer)     # best competitor position in top-10; None if unknown
    keyword_gap = Column(Boolean, default=False)  # True when competitor ≤10 & we rank >30/None
    trend_score = Column(Float, default=0.0)
    trend_direction = Column(String(20), default="stable")  # 'rising'|'stable'|'declining'
    opportunity_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_adk_app", "app_id"),
        Index("idx_adk_app_kw", "app_id", "keyword", unique=True),
        Index("idx_adk_opp_score", "app_id", "opportunity_score"),
        Index("idx_adk_gap", "app_id", "keyword_gap"),
    )


class KeywordTrend(Base):
    """
    Time-series Google Trends interest data per keyword (weekly granularity).
    Used for sparkline charts and trend_growth computation.
    """
    __tablename__ = "keyword_trends"

    id = Column(Integer, primary_key=True, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=False)
    week_start = Column(DateTime(timezone=True), nullable=False)  # Monday of the week
    interest_score = Column(Integer, default=0)   # 0-100, Google Trends relative interest
    captured_at = Column(DateTime(timezone=True), server_default=func.now())

    keyword = relationship("Keyword", back_populates="trends")

    __table_args__ = (
        Index("idx_ktrend_keyword_week", "keyword_id", "week_start", unique=True),
        Index("idx_ktrend_keyword", "keyword_id"),
        Index("idx_ktrend_week_start", "week_start"),
    )


class AppBlowingUpScore(Base):
    """
    Precomputed 'blowing up' momentum scores for apps showing unusually fast
    acceleration across rankings and reviews.  Refreshed every 15 minutes by
    the blowing_up_compute scheduler job — keeps the /apps/blowing-up endpoint
    a cheap read-only table scan.
    """
    __tablename__ = "app_blowing_up_scores"

    app_id              = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), primary_key=True)
    blowing_up_score    = Column(Float, nullable=False, default=0.0)  # 0-100 composite
    # Component scores (each 0-100)
    rank_velocity_score    = Column(Float, default=0.0)
    rank_change_score      = Column(Float, default=0.0)
    reviews_velocity_score = Column(Float, default=0.0)
    chart_presence_score   = Column(Float, default=0.0)
    cross_market_score     = Column(Float, default=0.0)
    consistency_score      = Column(Float, default=0.0)
    confidence_score       = Column(Float, default=0.0)  # 0-100
    # Raw signals
    rank_change      = Column(Integer, default=0)   # positive = improved toward #1
    rank_velocity    = Column(Float, default=0.0)   # avg rank_velocity in window
    reviews_velocity = Column(Float, default=0.0)   # new reviews per day
    chart_appearances = Column(Integer, default=0)  # ranking snapshots in window
    markets_count    = Column(Integer, default=0)   # distinct chart_types + categories
    # Human-readable output
    badges      = Column(JSON)   # ["Rapid Climb", "Fast Reviews", ...]
    why_flagged = Column(JSON)   # ["Rank improved from #80 to #12", ...]
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    app = relationship("App", back_populates="blowing_up_score")

    __table_args__ = (
        Index("idx_blowing_up_score", "blowing_up_score"),
        Index("idx_blowing_up_confidence", "confidence_score"),
    )


class AppMetricSnapshot(Base):
    """
    Time-series snapshot of computed app metrics (downloads + revenue estimates).
    Written by MetricSnapshotService on every scoring cycle.

    This is the shared backbone used by:
    - app detail metrics tab
    - campaign tracking (downloads delta)
    - dashboard widgets
    - trend/opportunity pages
    """
    __tablename__ = "app_metric_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    snapshot_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Downloads estimate
    estimated_downloads_min = Column(Integer, default=0)
    estimated_downloads_max = Column(Integer, default=0)
    install_confidence      = Column(Float, default=0.0)

    # Revenue estimate
    estimated_revenue_monthly_min = Column(Float, default=0.0)
    estimated_revenue_monthly_max = Column(Float, default=0.0)
    revenue_confidence            = Column(Float, default=0.0)
    monetization_model            = Column(String(50))   # paid_$x / free+iap / free_ads_only

    # Campaign / ad signals (populated when ad intelligence runs)
    has_ads_signal       = Column(Boolean, default=False)
    campaign_confidence  = Column(Float, default=0.0)   # 0-1

    # All signals used to build this snapshot (for audit / debug)
    source_signals = Column(JSON)

    app = relationship("App", back_populates="metric_snapshots")

    __table_args__ = (
        Index("idx_ams_app_id",     "app_id"),
        Index("idx_ams_snapshot_at","snapshot_at"),
        Index("idx_ams_app_time",   "app_id", "snapshot_at"),
    )


class AdCreative(Base):
    """
    Individual ad creatives fetched from ad networks (Apple Search Ads signals,
    Meta Ads Library, etc.).  Deduplicated by (app_id, network, external_creative_id).
    """
    __tablename__ = "ad_creatives"

    id                  = Column(Integer, primary_key=True, index=True)
    app_id              = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    network             = Column(String(50), nullable=False)   # apple_search_ads / meta / google_uac
    external_creative_id= Column(String(255))
    format              = Column(String(50))   # banner / video / interstitial / native
    creative_url        = Column(Text)
    preview_url         = Column(Text)
    title               = Column(Text)
    body                = Column(Text)
    cta                 = Column(String(100))
    landing_url         = Column(Text)
    first_seen_at       = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at        = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active           = Column(Boolean, default=True)
    raw_payload         = Column(JSON)

    app = relationship("App", back_populates="ad_creatives")

    __table_args__ = (
        Index("idx_creative_app",    "app_id"),
        Index("idx_creative_active", "app_id", "is_active"),
        Index("idx_creative_network","network"),
        Index("idx_creative_dedup",  "app_id", "network", "external_creative_id", unique=True),
    )


class AdCampaign(Base):
    """
    Aggregated campaign-level view of ad activity for an app.
    One row per (app_id, network, campaign_key); updated on every ad intelligence run.
    """
    __tablename__ = "ad_campaigns"

    id                     = Column(Integer, primary_key=True, index=True)
    app_id                 = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    network                = Column(String(50), nullable=False)
    campaign_key           = Column(String(255), nullable=False)   # stable identifier per network
    first_seen_at          = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at           = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    active_creatives_count = Column(Integer, default=0)
    countries              = Column(JSON)   # list of country codes where ads were detected
    status                 = Column(String(20), default="unknown")  # active / inactive / paused
    campaign_confidence    = Column(Float, default=0.0)   # 0-1

    app = relationship("App", back_populates="ad_campaigns")

    __table_args__ = (
        Index("idx_campaign_app",    "app_id"),
        Index("idx_campaign_status", "status"),
        Index("idx_campaign_dedup",  "app_id", "network", "campaign_key", unique=True),
    )


class GrowthEvent(Base):
    """
    Growth signal / campaign event detected by CampaignTrackingService.
    Pure derived intelligence — no scraping, only consumes existing data.

    event_type values:
      paid_push         — strong ad + rank + reviews evidence
      organic_breakout  — rank/reviews surge with no ad evidence
      mixed             — both ad activity AND organic signals present
      momentum_surge    — unusual rank velocity without clear cause
      campaign_cooling  — ad activity declining after a paid_push period
      unknown_unusual   — something is happening but cause unclear
    """
    __tablename__ = "growth_events"

    id               = Column(Integer, primary_key=True, index=True)
    app_id           = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    detected_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    event_type       = Column(String(50), nullable=False)
    confidence       = Column(Float, default=0.0)   # 0-1
    explanation      = Column(Text)
    signals          = Column(JSON)   # raw signal dict used in classification
    started_at_estimate = Column(DateTime(timezone=True))
    active_status    = Column(Boolean, default=True)

    app = relationship("App", back_populates="growth_events")

    __table_args__ = (
        Index("idx_growth_app",       "app_id"),
        Index("idx_growth_type",      "event_type"),
        Index("idx_growth_detected",  "detected_at"),
        Index("idx_growth_active",    "app_id", "active_status"),
    )


class AppTrendingScore(Base):
    """
    Precomputed trending scores for all apps with recent ranking history.
    Refreshed every 10 minutes by the trending_compute scheduler job so that
    the /trending endpoint is a cheap read-only table scan instead of an
    expensive on-the-fly computation.
    """
    __tablename__ = "app_trending_scores"

    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), primary_key=True)
    trend_score = Column(Float, nullable=False, default=0.0)
    momentum_score = Column(Float, default=0.0)   # weighted momentum (3d/7d/14d)
    momentum_3d = Column(Float, default=0.0)       # raw 3-day momentum
    momentum_7d = Column(Float, default=0.0)       # raw 7-day momentum
    consistency_score = Column(Float, default=0.0)
    absolute_rank_bonus = Column(Float, default=0.0)
    review_momentum = Column(Float, default=0.0)
    confidence_factor = Column(Float, default=1.0)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    app = relationship("App", back_populates="trending_score")

    __table_args__ = (
        Index("idx_trending_score", "trend_score"),
    )
