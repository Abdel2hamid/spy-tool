from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class CategoryBase(BaseModel):
    name: str
    slug: str


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# App Version
# ---------------------------------------------------------------------------

class AppVersionBase(BaseModel):
    version: str
    release_date: Optional[datetime] = None
    release_notes: Optional[str] = None


class AppVersionCreate(AppVersionBase):
    app_id: Optional[int] = None


class AppVersionResponse(AppVersionBase):
    id: int
    app_id: int
    is_latest: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# App Analytics
# ---------------------------------------------------------------------------

class AppAnalyticsBase(BaseModel):
    review_growth_30d: float = 0
    review_growth_90d: float = 0
    rating_change_30d: float = 0
    rating_change_90d: float = 0
    sentiment_score: float = 0
    sentiment_label: Optional[str] = None
    common_complaints: Optional[List[str]] = None
    common_features: Optional[List[str]] = None
    positive_themes: Optional[List[str]] = None
    bug_keywords: Optional[List[str]] = None
    churn_risk_score: float = 0
    update_cadence_score: float = 0
    quality_score: float = 0
    opportunity_score: float = 0


class AppAnalyticsResponse(AppAnalyticsBase):
    id: int
    app_id: int
    computed_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

class ReviewBase(BaseModel):
    review_id: Optional[str] = None
    user_name: Optional[str] = None
    rating: Optional[int] = None
    title: Optional[str] = None
    content: Optional[str] = None


class ReviewCreate(ReviewBase):
    app_id: int
    date: Optional[datetime] = None
    app_version: Optional[str] = None
    storefront: Optional[str] = None


class ReviewResponse(ReviewBase):
    id: int
    app_id: int
    user_url: Optional[str] = None
    date: Optional[datetime] = None
    app_version: Optional[str] = None
    storefront: Optional[str] = None
    is_updated: bool = False
    developer_reply_text: Optional[str] = None
    developer_reply_date: Optional[datetime] = None
    helpful_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class AppBase(BaseModel):
    app_id: str
    name: str
    developer: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    price: float = 0
    currency: str = "USD"


class AppCreate(AppBase):
    category_id: Optional[int] = None


class AppUpdate(BaseModel):
    name: Optional[str] = None
    developer: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    current_rating: Optional[float] = None
    current_reviews: Optional[int] = None
    current_rank: Optional[int] = None
    category_id: Optional[int] = None


class AppResponse(AppBase):
    id: int
    subtitle: Optional[str] = None
    developer_id: Optional[str] = None
    screenshots: Optional[List[str]] = None
    primary_category: Optional[str] = None
    secondary_category: Optional[str] = None
    is_free: bool = True
    in_app_purchases: Optional[Any] = None
    current_version: Optional[str] = None
    minimum_ios_version: Optional[str] = None
    supported_languages: Optional[List[str]] = None
    release_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    content_rating: Optional[str] = None
    current_rating: Optional[float] = None
    current_reviews: Optional[int] = None
    current_rank: Optional[int] = None
    category_id: Optional[int] = None
    url: Optional[str] = None
    created_at: datetime
    estimated_installs_min: Optional[int] = None
    estimated_installs_max: Optional[int] = None
    install_confidence: Optional[float] = None
    estimated_revenue_monthly_min: Optional[float] = None
    estimated_revenue_monthly_max: Optional[float] = None

    class Config:
        from_attributes = True


class AppDetailResponse(AppResponse):
    versions: List[AppVersionResponse] = []
    analytics: Optional[AppAnalyticsResponse] = None

    class Config:
        from_attributes = True


class AppListResponse(BaseModel):
    """Paginated apps list returned by GET /apps."""
    apps: List[AppResponse]
    total: int
    skip: int
    limit: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Keyword Search / Discover Apps
# ---------------------------------------------------------------------------

class KeywordSearchResultItem(BaseModel):
    """Single app in keyword search results."""
    id: int
    app_id: str
    name: str
    developer: Optional[str] = None
    icon_url: Optional[str] = None
    current_rating: Optional[float] = None
    current_reviews: Optional[int] = None
    primary_category: Optional[str] = None
    price: float = 0
    is_free: bool = True
    url: Optional[str] = None
    is_new: bool = False

    class Config:
        from_attributes = True


class KeywordDiscoverResponse(BaseModel):
    """Response for keyword search / discover apps endpoint."""
    keyword: str
    results: List[KeywordSearchResultItem]
    total: int
    new_apps_count: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# App Import / On-Demand Import
# ---------------------------------------------------------------------------

class AppImportSearchItem(BaseModel):
    """App item in import search results."""
    id: int
    app_id: str
    name: str
    developer: Optional[str] = None
    icon_url: Optional[str] = None
    current_rating: Optional[float] = None
    current_reviews: Optional[int] = None
    primary_category: Optional[str] = None
    price: float = 0
    is_free: bool = True
    url: Optional[str] = None
    is_new: bool = False
    source: str = "database"
    match_score: float = 0.0
    match_type: str = "none"

    class Config:
        from_attributes = True


class AppImportSearchResponse(BaseModel):
    """Response for app import search."""
    query: str
    results: List[AppImportSearchItem]
    total: int
    from_cache: int

    class Config:
        from_attributes = True


class AppLookupResponse(BaseModel):
    """Full app details from lookup."""
    id: int
    app_id: str
    name: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    developer: Optional[str] = None
    developer_id: Optional[str] = None
    icon_url: Optional[str] = None
    screenshots: List[str] = []
    primary_category: Optional[str] = None
    secondary_category: Optional[str] = None
    price: float = 0
    currency: str = "USD"
    is_free: bool = True
    in_app_purchases: Optional[List[Dict]] = None
    current_version: Optional[str] = None
    minimum_ios_version: Optional[str] = None
    supported_languages: Optional[List[str]] = None
    release_date: Optional[str] = None
    last_updated: Optional[str] = None
    content_rating: Optional[str] = None
    current_rating: Optional[float] = None
    current_reviews: Optional[int] = None
    url: Optional[str] = None
    is_new: bool = False

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

class RankingBase(BaseModel):
    app_id: int
    chart_type: str
    rank: int
    previous_rank: Optional[int] = None


class RankingCreate(RankingBase):
    category_id: Optional[int] = None


class RankingResponse(RankingBase):
    id: int
    rank_velocity: float
    recorded_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Keyword
# ---------------------------------------------------------------------------

class KeywordBase(BaseModel):
    term: str


class KeywordCreate(KeywordBase):
    search_volume: int = 0
    difficulty: float = 0


class KeywordResponse(KeywordBase):
    id: int
    search_volume: int
    difficulty: float
    trend: float

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------

class OpportunityBase(BaseModel):
    app_id: Optional[int] = None
    opportunity_type: str
    primary_keyword: Optional[str] = None
    competition_score: float = 0
    trend_score: float = 0
    success_probability: float = 0
    ai_integration_potential: float = 0
    recommendation: Optional[str] = None


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityResponse(OpportunityBase):
    id: int
    generated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Dashboard / aggregated views
# ---------------------------------------------------------------------------

class TrendingAppResponse(BaseModel):
    id: int
    app_id: str
    name: str
    developer: Optional[str] = None
    icon_url: Optional[str] = None
    current_rank: Optional[int] = None
    rank_velocity: float
    review_growth: float
    rating_velocity: float
    trend_score: float


class TrendingAppV2Response(BaseModel):
    """Enhanced trending app response with multi-factor scoring details."""
    id: int
    app_id: str
    name: str
    developer: Optional[str] = None
    icon_url: Optional[str] = None
    current_rank: Optional[int] = None
    current_rating: Optional[float] = None
    current_reviews: Optional[int] = None
    trend_score: float
    momentum_3d: float
    momentum_7d: float
    consistency_score: float
    confidence_factor: float
    absolute_rank_bonus: float
    estimated_installs_min: Optional[int] = None
    estimated_installs_max: Optional[int] = None
    install_confidence: Optional[float] = None
    estimated_revenue_monthly_min: Optional[float] = None
    estimated_revenue_monthly_max: Optional[float] = None
    review_momentum: float


class OpportunityOfDayResponse(BaseModel):
    app_id: int
    app_name: str
    primary_keyword: str
    competition_score: float
    trend_score: float
    success_probability: float
    attractiveness_score: Optional[float] = None
    feasibility_score: Optional[float] = None
    feasibility_details: Optional[dict] = None
    ai_integration_potential: float
    rank_velocity: float
    review_growth: float
    rating_velocity: float
    category_growth: float
    category: str
    recommendation: str


class KeywordOpportunityResponse(BaseModel):
    keyword: str
    search_volume: int
    difficulty: float
    trend: float
    opportunity_score: float
    base_opportunity_score: Optional[float] = None
    signal_confidence: Optional[float] = None
    current_apps: int


class TrendingAppsResponse(BaseModel):
    """Wrapper response for trending apps with status information."""
    status: str  # "success" | "insufficient_data" | "empty" | "pipeline_not_run"
    message: Optional[str] = None
    required_signals: Optional[List[str]] = None
    items: List[TrendingAppV2Response]


class OpportunityOfDayWrapperResponse(BaseModel):
    """Wrapper response for opportunity of the day with status information."""
    status: str  # "success" | "insufficient_data" | "empty" | "pipeline_not_run"
    message: Optional[str] = None
    required_signals: Optional[List[str]] = None
    item: Optional[OpportunityOfDayResponse] = None


class KeywordOpportunitiesWrapperResponse(BaseModel):
    """Wrapper response for keyword opportunities with status information."""
    status: str  # "success" | "insufficient_data" | "empty" | "pipeline_not_run"
    message: Optional[str] = None
    required_signals: Optional[List[str]] = None
    items: List[KeywordOpportunityResponse]


class FreshRiserItem(BaseModel):
    """Individual fresh riser app with scoring details."""
    app_id: int
    app_name: str
    developer: Optional[str] = None
    release_date: Optional[str] = None
    current_rank: Optional[int] = None
    current_reviews: int
    category: Optional[str] = None
    fresh_riser_score: float
    freshness_score: float
    review_traction_score: float
    rank_quality_score: float
    momentum_score: float
    niche_viability_score: float
    ranking_snapshots_count: int
    age_days: int


class FreshRisersResponse(BaseModel):
    """Wrapper response for fresh risers discovery."""
    status: str  # "success" | "insufficient_data" | "empty"
    message: Optional[str] = None
    required_signals: Optional[List[str]] = None
    items: List[FreshRiserItem]


# ---------------------------------------------------------------------------
# Enhanced Keyword Intelligence (keyword intelligence module)
# ---------------------------------------------------------------------------

class KeywordCompetitorItem(BaseModel):
    app_id: str
    app_name: str
    developer: Optional[str] = None
    icon_url: Optional[str] = None
    position: int
    is_sponsored: bool
    reviews: Optional[int] = None
    rating: Optional[float] = None
    dominance_score: float = 0.0


class KeywordListItem(BaseModel):
    id: int
    term: str
    search_volume: int
    difficulty: float
    trend: float
    opportunity_score: float
    feasibility_score: float
    classification: str  # 'easy' | 'medium' | 'hard' | 'impossible'
    apps_count: int
    ads_presence: float  # 0.0–1.0 fraction of sponsored results
    feature_gap_count: int
    last_updated: Optional[datetime] = None
    # External signal fields (populated by KeywordIntelligencePipeline)
    trend_score: float = 0.0          # Google Trends average interest (0-100)
    trend_growth: float = 0.0         # % growth last 4w vs prior 4w
    trend_velocity: float = 0.0       # momentum: last week vs recent avg
    dominance_score: float = 0.0      # top-app market dominance (0-100)
    competition_score: float = 0.0    # DataForSEO competition index (0-100)
    cpc: float = 0.0                  # cost per click (USD, from DataForSEO)
    last_enriched: Optional[datetime] = None  # last external enrichment


class KeywordListResponse(BaseModel):
    keywords: List[KeywordListItem]
    total: int
    skip: int
    limit: int


class GoogleTrendWeekPoint(BaseModel):
    """Single weekly data point from Google Trends (for sparkline charts)."""
    date: str           # ISO date string (Monday of week)
    interest: int       # 0-100 relative interest


class KeywordDetailResponse(BaseModel):
    id: Optional[int] = None
    term: str
    search_volume: int
    difficulty: float
    trend: float
    opportunity_score: float
    feasibility_score: float
    classification: str
    apps_count: int
    ads_presence: float
    top_competitors: List[KeywordCompetitorItem]
    related_keywords: List[str]
    feature_gap_count: int
    market_fragmentation: float
    last_scanned: Optional[str] = None
    # External signal fields
    trend_score: float = 0.0
    trend_growth: float = 0.0
    trend_velocity: float = 0.0
    dominance_score: float = 0.0
    competition_score: float = 0.0
    cpc: float = 0.0
    last_enriched: Optional[datetime] = None
    google_trend_points: List[GoogleTrendWeekPoint] = []  # sparkline data


class KeywordTrendPoint(BaseModel):
    date: str
    apps_count: int
    avg_position: float
    sponsored_ratio: float


class KeywordTrendResponse(BaseModel):
    term: str
    trend_points: List[KeywordTrendPoint]


class TrendingKeywordItem(BaseModel):
    """Keyword with strong rising trend signals — used on Trending/Opportunities pages."""
    id: int
    term: str
    trend_score: float
    trend_growth: float
    trend_velocity: float
    opportunity_score: float
    feasibility_score: float
    search_volume: int
    difficulty: float
    dominance_score: float
    apps_count: int
    classification: str


class TrendingKeywordsResponse(BaseModel):
    keywords: List[TrendingKeywordItem]
    total: int


class RankHistoryResponse(BaseModel):
    dates: List[str]
    ranks: List[int]
    chart_type: Optional[str] = None
    category_name: Optional[str] = None
    current_rank: Optional[int] = None


# ---------------------------------------------------------------------------
# Market Weakness
# ---------------------------------------------------------------------------

class CountryStatResponse(BaseModel):
    country: str
    total_reviews: int
    negative_reviews: int
    average_rating: float
    negative_ratio: float
    computed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MarketWeaknessResponse(BaseModel):
    app_id: int
    countries: List[CountryStatResponse]
    total_countries: int
    has_data: bool


# ---------------------------------------------------------------------------
# Feature Gaps
# ---------------------------------------------------------------------------

class FeatureGapItem(BaseModel):
    feature: str
    mentions: int
    detected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FeatureGapListResponse(BaseModel):
    app_id: int
    feature_gaps: List[FeatureGapItem]
    total_features: int
    total_mentions: int
    has_data: bool


class DashboardStatsResponse(BaseModel):
    total_apps_tracked: int
    total_keywords: int
    trending_apps_count: int
    opportunities_count: int
    new_apps_last_30_days: Optional[int] = 0
    new_apps_last_90_days: Optional[int] = 0


# ---------------------------------------------------------------------------
# App Ideas
# ---------------------------------------------------------------------------

class AppIdeaResponse(BaseModel):
    id: int
    idea_title: str
    idea_description: Optional[str]
    opportunity_score: float
    pattern_type: str
    related_app_ids: List[int]
    reasoning: List[str]
    signals: dict
    primary_keyword: Optional[str]
    category: Optional[str]
    generated_at: datetime

    class Config:
        from_attributes = True


class AppIdeaListResponse(BaseModel):
    ideas: List[AppIdeaResponse]
    total: int
    skip: int
    limit: int
    last_generated: Optional[datetime]


# ---------------------------------------------------------------------------
# Keyword Search Snapshots & Intelligence
# ---------------------------------------------------------------------------

class SearchResultItem(BaseModel):
    position: int
    organic_position: Optional[int] = None
    app_id: str
    app_name: str
    developer: str
    icon: str
    is_sponsored: bool


class KeywordSearchResponse(BaseModel):
    keyword: str
    country: str
    captured_at: str
    results: List[SearchResultItem]


class KeywordSnapshotDB(BaseModel):
    id: int
    keyword: str
    country: str
    app_id: str
    app_name: Optional[str]
    developer: Optional[str]
    icon_url: Optional[str]
    position: int
    organic_position: Optional[int]
    is_sponsored: bool
    captured_at: datetime

    class Config:
        from_attributes = True


class KeywordSnapshotListResponse(BaseModel):
    snapshots: List[KeywordSnapshotDB]
    total: int
    skip: int
    limit: int


class OrganicKeywordItem(BaseModel):
    keyword: str
    rank: int
    search_volume: int
    difficulty: float


class AdsKeywordItem(BaseModel):
    keyword: str
    position: int


class TrafficMix(BaseModel):
    organic: int   # percent 0-100
    ads: int       # percent 0-100


class KeywordIntelligenceResponse(BaseModel):
    app_id: str
    app_name: str
    primary_keyword: Optional[str]
    confidence: int          # 0-100
    organic_keywords: List[OrganicKeywordItem]
    ads_keywords: List[AdsKeywordItem]
    traffic_mix: TrafficMix
    total_snapshots: int
    last_scanned: Optional[datetime]


class KeywordTrackerRunResponse(BaseModel):
    status: str
    keywords_scanned: int
    total_results: int
    sponsored_results: int
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Install & Revenue Estimates
# ---------------------------------------------------------------------------

class InstallEstimateResponse(BaseModel):
    app_id: int
    estimated_installs_min: int
    estimated_installs_max: int
    install_confidence: float
    methodology: str


class RevenueEstimateResponse(BaseModel):
    app_id: int
    estimated_revenue_monthly_min: float
    estimated_revenue_monthly_max: float
    model: str
    arpu: float
    category: str


class FactorBreakdown(BaseModel):
    rank_baseline: Optional[int] = None
    review_velocity_estimate: Optional[int] = None
    visibility_estimate: Optional[int] = None
    momentum_adjustment_pct: Optional[float] = None
    weights_used: Optional[Dict] = None
    confidence_factors: Optional[Dict] = None


class DownloadEstimateResponse(BaseModel):
    app_id: int
    estimated_downloads_daily: int
    estimated_downloads_monthly: int
    downloads_range_low: int
    downloads_range_high: int
    estimated_revenue_monthly: Optional[float] = None
    revenue_range_low: Optional[float] = None
    revenue_range_high: Optional[float] = None
    estimation_confidence: float
    confidence_label: str
    monetization_model_hint: Optional[str] = None
    factor_breakdown: FactorBreakdown
    estimation_notes: str


# ---------------------------------------------------------------------------
# Keyword Extraction Intelligence (metadata-based)
# ---------------------------------------------------------------------------

class ExtractedKeywordItem(BaseModel):
    keyword: str
    source: str                   # 'title' | 'subtitle' | 'description'
    search_volume: int            # heuristic 0-100
    difficulty: float             # heuristic 0-100
    traffic_score: float          # search_volume × CTR(rank) / 100
    app_rank: Optional[int]       # position of this app in iTunes search; None if absent
    result_count: int             # total iTunes results for keyword
    extracted_at: Optional[datetime] = None


class KeywordExtractionResponse(BaseModel):
    app_id: str
    app_name: str
    keywords: List[ExtractedKeywordItem]
    extracting: bool              # True if a background job just started
    total: int
    last_extracted: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Keyword Discovery (autocomplete + affix expansion per app)
# ---------------------------------------------------------------------------

class DiscoveredKeywordItem(BaseModel):
    keyword: str
    source: str                    # 'autocomplete' | 'prefix' | 'suffix' | 'alphabet' | 'competitor'
    source_keyword: str
    search_volume: int
    difficulty: float
    traffic_score: float
    app_rank: Optional[int]
    competitor_rank: Optional[int] = None
    keyword_gap: bool = False
    trend_score: float
    trend_direction: str           # 'rising' | 'stable' | 'declining'
    opportunity_score: float
    created_at: Optional[datetime] = None


class DiscoveredKeywordsResponse(BaseModel):
    app_id: str
    app_name: str
    keywords: List[DiscoveredKeywordItem]
    total: int
    discovering: bool              # True when a background job just started
    last_discovered: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Keyword Opportunities (Phase-1)
# ---------------------------------------------------------------------------

class KeywordOpportunityItem(BaseModel):
    keyword: str
    search_volume: int
    difficulty: float
    trend_score: float
    trend_direction: str
    app_rank: Optional[int]
    competitor_rank: Optional[int]
    keyword_gap: bool
    opportunity_score: float
    source: str


class KeywordOpportunitiesResponse(BaseModel):
    app_id: str
    app_name: str
    opportunities: List[KeywordOpportunityItem]
    total: int
    discovering: bool


# ---------------------------------------------------------------------------
# Keyword History
# ---------------------------------------------------------------------------

class KeywordHistoryPoint(BaseModel):
    date: str
    best_rank: int
    is_sponsored: bool


class KeywordHistoryResponse(BaseModel):
    app_id: str
    keyword: str
    country: str
    history: List[KeywordHistoryPoint]
    current_rank: Optional[int]
    total_days: int


# ---------------------------------------------------------------------------
# Niche Radar
# ---------------------------------------------------------------------------

class NicheRadarItem(BaseModel):
    niche_name: str
    niche_score: int
    signal_type: str
    description: str
    keywords: List[str]
    app_count: int
    trend: float
    search_volume: int
    difficulty: float
    detected_at: str


class NicheRadarResponse(BaseModel):
    niches: List[NicheRadarItem]
    total: int
    scanned_at: str


# ---------------------------------------------------------------------------
# Review Intelligence
# ---------------------------------------------------------------------------

class ReviewIntelligenceResponse(BaseModel):
    app_id: Optional[int] = None
    app_name: Optional[str] = None
    feature_requests: List[str]
    competitor_mentions: List[str]
    pricing_complaints: List[str]
    pain_points: List[str]
    sentiment_summary: str
    opportunity_score: int
    reviews_analyzed: int


# ---------------------------------------------------------------------------
# App Autopsy
# ---------------------------------------------------------------------------

class RankTrajectoryResponse(BaseModel):
    current_rank: Optional[int]
    rank_30d_ago: Optional[int]
    rank_delta: int
    trend: str


class UpdateCadenceResponse(BaseModel):
    avg_days_between_releases: Optional[int]
    versions_last_90d: int


class CompetitorGapItem(BaseModel):
    feature: str
    total_mentions: int
    apps_missing: int


class AppAutopsyResponse(BaseModel):
    app_id: int
    app_name: str
    developer: Optional[str]
    category: Optional[str]
    current_rating: Optional[float]
    current_reviews: Optional[int]
    current_rank: Optional[int]
    price: Optional[float]
    is_free: Optional[bool]
    has_iap: bool
    release_date: Optional[str]
    estimated_installs_min: Optional[int]
    estimated_installs_max: Optional[int]
    install_confidence: Optional[float]
    estimated_revenue_monthly_min: Optional[float]
    estimated_revenue_monthly_max: Optional[float]
    rating_momentum: float
    review_growth_30d: float
    rank_trajectory: RankTrajectoryResponse
    update_cadence: UpdateCadenceResponse
    competitor_feature_gaps: List[CompetitorGapItem]
    strengths: List[str]
    narrative: Optional[str]


# ---------------------------------------------------------------------------
# Apps Blowing Up
# ---------------------------------------------------------------------------

class AppBlowingUpItem(BaseModel):
    """One entry in the 'blowing up' list — includes app fields + score breakdown."""
    # App identity
    id: int                          # internal DB id
    app_id: str                      # App Store numeric string ID
    name: str
    developer: Optional[str] = None
    icon_url: Optional[str] = None
    primary_category: Optional[str] = None
    current_rank: Optional[int] = None
    current_rating: Optional[float] = None
    current_reviews: Optional[int] = None
    # Score + components
    blowing_up_score: float
    rank_velocity_score: float
    rank_change_score: float
    reviews_velocity_score: float
    chart_presence_score: float
    cross_market_score: float
    consistency_score: float
    confidence_score: float
    # Raw signals
    rank_change: int
    rank_velocity: float
    reviews_velocity: float
    chart_appearances: int
    markets_count: int
    # Human-readable labels
    badges: List[str]
    why_flagged: List[str]
    computed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BlowingUpResponse(BaseModel):
    """Status-wrapped response for GET /apps/blowing-up."""
    status: str                          # "success" | "insufficient_data" | "empty"
    message: Optional[str] = None
    required_signals: Optional[List[str]] = None
    items: List[AppBlowingUpItem]
    total: int
    # Summary stats (populated on success)
    exploding_count: Optional[int] = None
    top_score: Optional[float] = None
    avg_rank_velocity: Optional[float] = None


# ===========================================================================
# Growth Intelligence Schemas
# ===========================================================================

class MetricSnapshotResponse(BaseModel):
    """Single metric snapshot (download + revenue estimate at a point in time)."""
    id: int
    app_id: int
    snapshot_at: datetime
    estimated_downloads_min: Optional[int] = None
    estimated_downloads_max: Optional[int] = None
    install_confidence: Optional[float] = None
    estimated_revenue_monthly_min: Optional[float] = None
    estimated_revenue_monthly_max: Optional[float] = None
    revenue_confidence: Optional[float] = None
    monetization_model: Optional[str] = None
    has_ads_signal: bool = False
    campaign_confidence: float = 0.0
    source_signals: Optional[dict] = None

    class Config:
        from_attributes = True


class MetricSnapshotHistoryResponse(BaseModel):
    """Time-series of metric snapshots for a single app."""
    app_id: int
    snapshots: List[MetricSnapshotResponse]
    latest: Optional[MetricSnapshotResponse] = None
    downloads_delta_7d: Optional[dict] = None


class AdCreativeResponse(BaseModel):
    """Single ad creative detected for an app."""
    id: int
    app_id: int
    network: str
    external_creative_id: Optional[str] = None
    format: Optional[str] = None
    creative_url: Optional[str] = None
    preview_url: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    cta: Optional[str] = None
    landing_url: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class AdCampaignResponse(BaseModel):
    """Campaign-level ad summary for an app."""
    id: int
    app_id: int
    network: str
    campaign_key: str
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    active_creatives_count: int = 0
    countries: Optional[List[str]] = None
    status: str = "unknown"
    campaign_confidence: float = 0.0

    class Config:
        from_attributes = True


class AppAdIntelligenceResponse(BaseModel):
    """Full ad intelligence for a single app."""
    app_id: int
    campaigns: List[AdCampaignResponse]
    creatives: List[AdCreativeResponse]
    total_campaigns: int
    active_campaigns: int
    total_creatives: int
    active_creatives: int
    has_active_campaign: bool
    networks: List[str]


class AdIntelligenceListItem(BaseModel):
    """Summary row for the global /ads listing."""
    app_id: int
    app_db_id: int
    name: str
    icon_url: Optional[str] = None
    primary_category: Optional[str] = None
    current_rank: Optional[int] = None
    networks: List[str]
    active_campaigns: int
    active_creatives: int
    max_confidence: float
    first_ad_seen: Optional[datetime] = None
    last_ad_seen: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdIntelligenceListResponse(BaseModel):
    """Paginated list of apps with active ad intelligence data."""
    status: str
    items: List[AdIntelligenceListItem]
    total: int
    active_count: int


class GrowthEventResponse(BaseModel):
    """Single growth/campaign signal event."""
    id: int
    app_id: int
    detected_at: datetime
    event_type: str
    confidence: float
    explanation: Optional[str] = None
    signals: Optional[dict] = None
    started_at_estimate: Optional[datetime] = None
    active_status: bool = True

    class Config:
        from_attributes = True


class AppGrowthEventsResponse(BaseModel):
    """Growth events for a single app."""
    app_id: int
    events: List[GrowthEventResponse]
    latest_event: Optional[GrowthEventResponse] = None
    total: int


class CampaignTrackingListItem(BaseModel):
    """Summary row for the global /campaigns listing."""
    app_id: int
    app_db_id: int
    name: str
    icon_url: Optional[str] = None
    primary_category: Optional[str] = None
    current_rank: Optional[int] = None
    event_type: str
    confidence: float
    explanation: Optional[str] = None
    detected_at: datetime
    started_at_estimate: Optional[datetime] = None
    blowing_up_score: Optional[float] = None

    class Config:
        from_attributes = True


class CampaignTrackingListResponse(BaseModel):
    """Paginated campaign tracking events with summary stats."""
    status: str
    items: List[CampaignTrackingListItem]
    total: int
    by_type: Optional[dict] = None  # {"paid_push": 12, "organic_breakout": 5, ...}


class DashboardKeywordHighlight(BaseModel):
    """Lightweight keyword row for the dashboard Keyword Intelligence section."""
    term: str
    search_volume: int
    trend_score: float
    opportunity_score: float


class DashboardKeywordHighlightsResponse(BaseModel):
    keywords: List[DashboardKeywordHighlight]
    total: int
