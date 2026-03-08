from pydantic import BaseModel
from typing import Optional, List, Any
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


class OpportunityOfDayResponse(BaseModel):
    app_id: int
    app_name: str
    primary_keyword: str
    competition_score: float
    trend_score: float
    success_probability: float
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
    current_apps: int


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
