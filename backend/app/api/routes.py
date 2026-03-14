from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import exists, func, and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
import asyncio
import logging

from app.database import get_db
from app.models import models
from app.models.schemas import (
    AppResponse,
    AppListResponse,
    AppDetailResponse,
    AppCreate,
    AppUpdate,
    RankingResponse,
    KeywordResponse,
    KeywordCreate,
    OpportunityResponse,
    OpportunityCreate,
    TrendingAppResponse,
    TrendingAppV2Response,
    OpportunityOfDayResponse,
    KeywordOpportunityResponse,
    KeywordCompetitorItem,
    KeywordListItem,
    KeywordListResponse,
    KeywordDetailResponse,
    KeywordTrendPoint,
    KeywordTrendResponse,
    GoogleTrendWeekPoint,
    TrendingKeywordItem,
    TrendingKeywordsResponse,
    RankHistoryResponse,
    DashboardStatsResponse,
    ReviewResponse,
    AppVersionResponse,
    AppAnalyticsResponse,
    MarketWeaknessResponse,
    FeatureGapListResponse,
    AppIdeaListResponse,
    KeywordIntelligenceResponse,
    KeywordTrackerRunResponse,
    KeywordSnapshotListResponse,
    KeywordSearchResponse,
    InstallEstimateResponse,
    RevenueEstimateResponse,
    KeywordHistoryResponse,
    NicheRadarResponse,
    ReviewIntelligenceResponse,
    AppAutopsyResponse,
    KeywordExtractionResponse,
    ExtractedKeywordItem,
    DiscoveredKeywordsResponse,
    DiscoveredKeywordItem,
    KeywordOpportunitiesResponse,
    KeywordDiscoverResponse,
    AppImportSearchResponse,
    AppLookupResponse,
    TrendingAppsResponse,
    OpportunityOfDayWrapperResponse,
    KeywordOpportunitiesWrapperResponse,
    FreshRisersResponse,
    AppBlowingUpItem,
    BlowingUpResponse,
    MetricSnapshotResponse,
    MetricSnapshotHistoryResponse,
    AdCreativeResponse,
    AdCampaignResponse,
    AppAdIntelligenceResponse,
    AdIntelligenceListItem,
    AdIntelligenceListResponse,
    GrowthEventResponse,
    AppGrowthEventsResponse,
    CampaignTrackingListItem,
    CampaignTrackingListResponse,
)
from app.scoring.engine import ScoringEngine, _BIG_BRAND_DEVELOPERS
from app.scoring.feature_gaps import FeatureGapAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Dashboard stats — in-process TTL cache (60 s) to avoid repeated COUNT(*)
# on large tables at every page load.
# ---------------------------------------------------------------------------
_DASHBOARD_CACHE: dict = {}
_DASHBOARD_CACHE_TTL = 60  # seconds


@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(db: Session = Depends(get_db)):
    import time
    now = time.monotonic()
    cached = _DASHBOARD_CACHE.get("stats")
    if cached and now - cached["ts"] < _DASHBOARD_CACHE_TTL:
        return cached["data"]

    total_apps = db.query(func.count(models.App.id)).scalar() or 0
    total_keywords = db.query(func.count(models.Keyword.id)).scalar() or 0

    cutoff = datetime.utcnow() - timedelta(days=7)
    trending_count = (
        db.query(func.count(func.distinct(models.Ranking.app_id)))
        .filter(
            models.Ranking.recorded_at >= cutoff,
            models.Ranking.rank_velocity > 0,
        )
        .scalar() or 0
    )

    opportunities_count = db.query(func.count(models.Opportunity.id)).scalar() or 0

    # Freshness metrics — apps released in last 30/90 days
    now_dt = datetime.utcnow()
    new_30d = (
        db.query(func.count(models.App.id))
        .filter(models.App.release_date >= now_dt - timedelta(days=30))
        .scalar() or 0
    )
    new_90d = (
        db.query(func.count(models.App.id))
        .filter(models.App.release_date >= now_dt - timedelta(days=90))
        .scalar() or 0
    )

    data = {
        "total_apps_tracked": total_apps,
        "total_keywords": total_keywords,
        "trending_apps_count": trending_count,
        "opportunities_count": opportunities_count,
        "new_apps_last_30_days": new_30d,
        "new_apps_last_90_days": new_90d,
    }
    _DASHBOARD_CACHE["stats"] = {"ts": now, "data": data}
    return data


_VALID_SORT_FIELDS = {
    "name": models.App.name,
    "rating": models.App.current_rating,
    "reviews": models.App.current_reviews,
    "rank": models.App.current_rank,
    "release_date": models.App.release_date,
    "last_updated": models.App.last_updated,
    "created_at": models.App.created_at,
}

_AI_TERMS = ["%ai%", "%artificial intelligence%", "%machine learning%",
             "%chatgpt%", "%gpt%", "%llm%", "%generative%"]


@router.get("/apps", response_model=AppListResponse)
def get_apps(
    # ── pagination: page/limit (1-based) OR legacy skip/limit ────────────
    page: int = Query(1, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    # ── text search ──────────────────────────────────────────────────────
    search: Optional[str] = None,
    # ── category / developer ─────────────────────────────────────────────
    category: Optional[str] = None,
    category_id: Optional[int] = None,
    developer: Optional[str] = None,
    # ── rating ───────────────────────────────────────────────────────────
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    max_rating: Optional[float] = Query(None, ge=0, le=5),
    # ── review count ─────────────────────────────────────────────────────
    min_reviews: Optional[int] = Query(None, ge=0),
    max_reviews: Optional[int] = Query(None, ge=0),
    # ── rank ─────────────────────────────────────────────────────────────
    min_rank: Optional[int] = Query(None, ge=1),
    max_rank: Optional[int] = Query(None, ge=1),
    # ── pricing ──────────────────────────────────────────────────────────
    is_free: Optional[bool] = None,
    has_in_app_purchases: Optional[bool] = None,
    # ── dates (ISO-8601 strings) ──────────────────────────────────────────
    updated_after: Optional[str] = None,
    updated_before: Optional[str] = None,
    released_after: Optional[str] = None,
    released_before: Optional[str] = None,
    # ── freshness filter ─────────────────────────────────────────────────
    fresh_only: Optional[bool] = None,   # True = released in last 30 days
    min_freshness_score: Optional[float] = Query(None, ge=0, le=100),
    # ── opportunity scoring ───────────────────────────────────────────────
    min_success_probability: Optional[float] = Query(None, ge=0, le=100),
    # ── ai filter ────────────────────────────────────────────────────────
    ai_only: Optional[bool] = None,
    # ── market weakness ───────────────────────────────────────────────────
    weak_market: Optional[str] = None,
    min_negative_ratio: Optional[float] = Query(None, ge=0, le=1),
    # ── feature gaps ──────────────────────────────────────────────────────
    min_feature_gaps: Optional[int] = Query(None, ge=1),
    # ── sorting ──────────────────────────────────────────────────────────
    sort_by: Optional[str] = None,
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
):
    """
    Return a paginated, filtered list of tracked apps.
    All filters are optional and composable.
    Supports page/limit (1-based) or legacy skip/limit.
    """
    # page param takes precedence over raw skip when page > 1
    effective_skip = (page - 1) * limit if page > 1 else skip

    query = db.query(models.App)

    # ── full-text search across name / subtitle / developer / description ─
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                models.App.name.ilike(term),
                models.App.subtitle.ilike(term),
                models.App.developer.ilike(term),
                models.App.description.ilike(term),
            )
        )

    # ── category (name string or integer id) ─────────────────────────────
    if category:
        cat_term = f"%{category}%"
        query = query.filter(
            or_(
                models.App.primary_category.ilike(cat_term),
                models.App.secondary_category.ilike(cat_term),
            )
        )
    if category_id:
        query = query.filter(models.App.category_id == category_id)

    # ── developer ────────────────────────────────────────────────────────
    if developer:
        query = query.filter(models.App.developer.ilike(f"%{developer}%"))

    # ── rating ───────────────────────────────────────────────────────────
    if min_rating is not None:
        query = query.filter(models.App.current_rating >= min_rating)
    if max_rating is not None:
        query = query.filter(models.App.current_rating <= max_rating)

    # ── review count ─────────────────────────────────────────────────────
    if min_reviews is not None:
        query = query.filter(models.App.current_reviews >= min_reviews)
    if max_reviews is not None:
        query = query.filter(models.App.current_reviews <= max_reviews)

    # ── rank ─────────────────────────────────────────────────────────────
    if min_rank is not None:
        query = query.filter(models.App.current_rank >= min_rank)
    if max_rank is not None:
        query = query.filter(models.App.current_rank <= max_rank)

    # ── pricing ──────────────────────────────────────────────────────────
    if is_free is not None:
        query = query.filter(models.App.is_free == is_free)
    if has_in_app_purchases is not None:
        query = query.filter(models.App.in_app_purchases == has_in_app_purchases)

    # ── dates ────────────────────────────────────────────────────────────
    def _parse_date(s: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    if updated_after:
        dt = _parse_date(updated_after)
        if dt:
            query = query.filter(models.App.last_updated >= dt)
    if updated_before:
        dt = _parse_date(updated_before)
        if dt:
            query = query.filter(models.App.last_updated <= dt)
    if released_after:
        dt = _parse_date(released_after)
        if dt:
            query = query.filter(models.App.release_date >= dt)
    if released_before:
        dt = _parse_date(released_before)
        if dt:
            query = query.filter(models.App.release_date <= dt)

    # ── opportunity: min success probability ─────────────────────────────
    if min_success_probability is not None:
        opp_ids = (
            db.query(models.Opportunity.app_id)
            .filter(models.Opportunity.success_probability >= min_success_probability)
            .subquery()
        )
        query = query.filter(models.App.id.in_(opp_ids))

    # ── ai-related apps ──────────────────────────────────────────────────
    if ai_only:
        query = query.filter(
            or_(
                *[models.App.name.ilike(t) for t in _AI_TERMS],
                *[models.App.description.ilike(t) for t in _AI_TERMS],
            )
        )

    # ── market weakness filter ────────────────────────────────────────────
    if weak_market or min_negative_ratio is not None:
        mw_query = db.query(models.AppMarketWeakness.app_id)
        if weak_market:
            mw_query = mw_query.filter(
                models.AppMarketWeakness.country == weak_market.upper()
            )
        if min_negative_ratio is not None:
            mw_query = mw_query.filter(
                models.AppMarketWeakness.negative_ratio >= min_negative_ratio
            )
        weak_app_ids = mw_query.subquery()
        query = query.filter(models.App.id.in_(weak_app_ids))

    # ── feature gaps filter ───────────────────────────────────────────────
    if min_feature_gaps is not None:
        fg_ids = (
            db.query(models.FeatureGap.app_id)
            .group_by(models.FeatureGap.app_id)
            .having(func.count(models.FeatureGap.id) >= min_feature_gaps)
            .subquery()
        )
        query = query.filter(models.App.id.in_(fg_ids))

    # ── freshness filters ─────────────────────────────────────────────────
    if fresh_only:
        cutoff_30d = datetime.utcnow() - timedelta(days=30)
        query = query.filter(models.App.release_date >= cutoff_30d)
    if min_freshness_score is not None:
        query = query.filter(models.App.freshness_score >= min_freshness_score)

    # ── sorting ──────────────────────────────────────────────────────────
    _VALID_SORT_FIELDS_LOCAL = {
        **_VALID_SORT_FIELDS,
        "freshness_score": models.App.freshness_score,
    }
    sort_col = _VALID_SORT_FIELDS_LOCAL.get(sort_by or "", models.App.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc().nullslast())
    else:
        query = query.order_by(sort_col.desc().nullslast())

    total = query.count()
    apps = query.offset(effective_skip).limit(limit).all()

    return {"apps": apps, "total": total, "skip": effective_skip, "limit": limit}


@router.get("/apps/latest-60-days", response_model=AppListResponse)
def get_latest_apps(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None),
    sort_by: str = Query("release_date"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=60)

    query = db.query(models.App).filter(
        or_(
            models.App.release_date >= cutoff,
            models.App.created_at >= cutoff,
        )
    )

    if category:
        query = query.filter(
            or_(
                models.App.primary_category.ilike(f"%{category}%"),
                models.App.secondary_category.ilike(f"%{category}%"),
            )
        )

    sort_col = _VALID_SORT_FIELDS.get(sort_by, models.App.release_date)
    query = query.order_by(
        sort_col.desc() if sort_order == "desc" else sort_col.asc()
    )

    total = query.count()
    apps = query.offset(offset).limit(limit).all()

    return AppListResponse(apps=apps, total=total, skip=offset, limit=limit)


@router.get("/apps/blowing-up", response_model=BlowingUpResponse)
def get_blowing_up_apps(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    sort_by: str = Query("blowing_up_score", description="blowing_up_score|rank_velocity|rank_change|reviews_velocity|confidence"),
    sort_order: str = Query("desc", description="asc|desc"),
    min_confidence: float = Query(0.3, ge=0.0, le=1.0, description="Minimum confidence (0–1)"),
    min_reviews_velocity: float = Query(0.0, ge=0.0, description="Minimum reviews/day"),
    category: Optional[str] = Query(None, description="Filter by primary_category (partial match)"),
    chart_type: Optional[str] = Query(None, description="topfree|toppaid|topgrossing"),
    timeframe: str = Query("7d", description="24h|3d|7d — window used for score computation"),
    db: Session = Depends(get_db),
):
    """
    Return apps showing unusually fast momentum across rankings and reviews.
    Results are read from the precomputed app_blowing_up_scores table
    (refreshed every 15 min) for sub-millisecond response times.
    """
    from app.services.blowing_up_service import BlowingUpService

    svc = BlowingUpService(db)

    # Check if the table has any data at all
    from app.models.models import AppBlowingUpScore
    total_computed = db.query(func.count(AppBlowingUpScore.app_id)).scalar() or 0

    if total_computed == 0:
        return BlowingUpResponse(
            status="insufficient_data",
            message="No blowing-up scores computed yet. The scoring job runs every 15 minutes.",
            required_signals=["ranking_history", "rank_velocity"],
            items=[],
            total=0,
        )

    rows, total = svc.get_blowing_up_apps(
        limit=limit,
        skip=skip,
        sort_by=sort_by,
        sort_order=sort_order,
        min_confidence=min_confidence,
        min_reviews_velocity=min_reviews_velocity,
        category=category,
        chart_type=chart_type,
    )

    if total == 0:
        return BlowingUpResponse(
            status="empty",
            message="No apps match the current filters. Try relaxing confidence or velocity thresholds.",
            items=[],
            total=0,
        )

    items: list[AppBlowingUpItem] = []
    for score, app in rows:
        items.append(AppBlowingUpItem(
            id=app.id,
            app_id=app.app_id,
            name=app.name,
            developer=app.developer,
            icon_url=app.icon_url,
            primary_category=app.primary_category,
            current_rank=app.current_rank,
            current_rating=app.current_rating,
            current_reviews=app.current_reviews,
            blowing_up_score=score.blowing_up_score,
            rank_velocity_score=score.rank_velocity_score,
            rank_change_score=score.rank_change_score,
            reviews_velocity_score=score.reviews_velocity_score,
            chart_presence_score=score.chart_presence_score,
            cross_market_score=score.cross_market_score,
            consistency_score=score.consistency_score,
            confidence_score=score.confidence_score,
            rank_change=score.rank_change,
            rank_velocity=score.rank_velocity,
            reviews_velocity=score.reviews_velocity,
            chart_appearances=score.chart_appearances,
            markets_count=score.markets_count,
            badges=score.badges or [],
            why_flagged=score.why_flagged or [],
            computed_at=score.computed_at,
        ))

    scores = [item.blowing_up_score for item in items]
    velocities = [item.rank_velocity for item in items if item.rank_velocity > 0]

    return BlowingUpResponse(
        status="success",
        items=items,
        total=total,
        exploding_count=total,
        top_score=round(max(scores), 1) if scores else None,
        avg_rank_velocity=round(sum(velocities) / len(velocities), 1) if velocities else None,
    )


@router.get("/apps/{app_id}", response_model=AppResponse)
def get_app(app_id: int, db: Session = Depends(get_db)):
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return app


@router.post("/apps", response_model=AppResponse)
def create_app(app: AppCreate, db: Session = Depends(get_db)):
    db_app = models.App(**app.dict())
    db.add(db_app)
    db.commit()
    db.refresh(db_app)
    return db_app


@router.get("/search/apps", response_model=KeywordDiscoverResponse)
def search_apps_by_keyword(
    keyword: str = Query(..., min_length=2, description="Keyword to search apps"),
    limit: int = Query(50, ge=1, le=100, description="Max results to return"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Search for apps by keyword from App Store.
    
    - Calls iTunes Search API (entity=software)
    - Inserts new apps if not in database
    - Returns results with app info
    - Triggers background enrichment for new apps
    """
    from app.services.keyword_search_service import KeywordSearchService
    
    service = KeywordSearchService(db)
    result = service.search(keyword, limit=limit)
    
    if result.get("new_app_ids"):
        background_tasks.add_task(service.trigger_background_enrichment, result["new_app_ids"])
    
    return result


@router.get("/apps/import", response_model=AppImportSearchResponse)
def import_search_apps(
    q: str = Query(..., min_length=2, description="App name to search"),
    limit: int = Query(10, ge=1, le=20, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    Search for apps: first checks local database, then queries iTunes API if needed.
    Returns top results with source info (database or itunes).
    """
    from app.services.app_import_service import AppImportService
    
    service = AppImportService(db)
    return service.search_apps(q, limit=limit)


@router.get("/apps/lookup/{track_id}", response_model=AppLookupResponse)
def lookup_app(
    track_id: str,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Lookup full app details by trackId from iTunes API.
    - Fetches full metadata from iTunes Lookup API
    - Inserts/updates app in database
    - Returns complete app details
    - Triggers background enrichment for new imports
    """
    from app.services.app_import_service import AppImportService
    
    service = AppImportService(db)
    result = service.lookup_app(track_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    if result.get("is_new") and result.get("id"):
        background_tasks.add_task(service.trigger_enrichment, result["id"])
    
    return result


@router.patch("/apps/{app_id}", response_model=AppResponse)
def update_app(app_id: int, app_update: AppUpdate, db: Session = Depends(get_db)):
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    update_data = app_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(app, key, value)
    
    db.commit()
    db.refresh(app)
    return app


@router.get("/apps/{app_id}/rank-history", response_model=RankHistoryResponse)
def get_rank_history(
    app_id: int,
    days: int = Query(30, ge=1, le=90),
    chart_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = db.query(models.Ranking).filter(
        and_(
            models.Ranking.app_id == app_id,
            models.Ranking.recorded_at >= cutoff,
        )
    ).order_by(models.Ranking.recorded_at)

    if chart_type:
        query = query.filter(models.Ranking.chart_type == chart_type)
    else:
        # Default: prefer topfree; fall back to any chart
        topfree = query.filter(models.Ranking.chart_type == "topfree").all()
        if topfree:
            rankings = topfree
        else:
            rankings = query.all()

        # Resolve category name from the most recent entry
        category_name = None
        used_chart_type = None
        if rankings:
            latest = rankings[-1]
            used_chart_type = latest.chart_type
            if latest.category_id:
                cat = db.query(models.Category).filter(
                    models.Category.id == latest.category_id
                ).first()
                if cat:
                    category_name = cat.name

        return {
            "dates": [r.recorded_at.strftime("%Y-%m-%d") for r in rankings],
            "ranks": [r.rank for r in rankings],
            "chart_type": used_chart_type,
            "category_name": category_name,
            "current_rank": rankings[-1].rank if rankings else None,
        }

    rankings = query.all()

    category_name = None
    if rankings and rankings[-1].category_id:
        cat = db.query(models.Category).filter(
            models.Category.id == rankings[-1].category_id
        ).first()
        if cat:
            category_name = cat.name

    return {
        "dates": [r.recorded_at.strftime("%Y-%m-%d") for r in rankings],
        "ranks": [r.rank for r in rankings],
        "chart_type": chart_type,
        "category_name": category_name,
        "current_rank": rankings[-1].rank if rankings else None,
    }


logger = logging.getLogger(__name__)


def _check_ranking_history(db: Session, app_ids: List[int]) -> bool:
    """Check if apps have ranking history data."""
    if not app_ids:
        return False
    has_history = db.query(models.Ranking).filter(
        models.Ranking.app_id.in_(app_ids)
    ).first() is not None
    return has_history


def _read_precomputed_trending(
    db: Session,
    limit: int,
    category_id: Optional[int],
) -> list:
    """
    Read trending items from the precomputed app_trending_scores table.
    Returns a list of dicts matching TrendingAppV2Response fields, or [] if
    the table is empty / no scores exist yet.
    """
    query = (
        db.query(models.AppTrendingScore, models.App)
        .join(models.App, models.App.id == models.AppTrendingScore.app_id)
        .filter(models.AppTrendingScore.trend_score > 0)
    )
    if category_id is not None:
        # Filter to apps that have at least one ranking in the requested category
        query = query.filter(
            exists().where(
                (models.Ranking.app_id == models.AppTrendingScore.app_id)
                & (models.Ranking.category_id == category_id)
            )
        )
    rows = (
        query
        .order_by(models.AppTrendingScore.trend_score.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": app.id,
            "app_id": app.app_id,
            "name": app.name,
            "developer": app.developer,
            "icon_url": app.icon_url,
            "current_rank": app.current_rank,
            "current_rating": app.current_rating,
            "current_reviews": app.current_reviews,
            "trend_score": score.trend_score,
            "momentum_3d": score.momentum_3d,
            "momentum_7d": score.momentum_7d,
            "consistency_score": score.consistency_score,
            "confidence_factor": score.confidence_factor,
            "absolute_rank_bonus": score.absolute_rank_bonus,
            "review_momentum": score.review_momentum,
        }
        for score, app in rows
    ]


@router.get("/trending", response_model=TrendingAppsResponse)
def get_trending_apps(
    limit: int = Query(10, ge=1, le=50),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    db: Session = Depends(get_db)
):
    """
    Get trending apps from precomputed scores (refreshed every 10 minutes).

    Scores are computed by the trending_compute scheduler job using a
    multi-factor algorithm:
    - Multi-window momentum (3d, 7d, 14d)
    - Confidence penalty for sparse data
    - Consistency bonus for sustained movers
    - Absolute rank bonus for strong positions
    - Bounded review growth
    - Category normalization

    Returns:
        TrendingAppsResponse with status field indicating success/insufficient_data/empty
    """
    trending = _read_precomputed_trending(db, limit, category_id)

    if trending:
        return {
            "status": "success",
            "message": None,
            "required_signals": None,
            "items": trending,
        }

    app_count = db.query(func.count(models.App.id)).scalar() or 0

    if app_count == 0:
        logger.info("trending endpoint: no apps in database")
        return {
            "status": "empty",
            "message": "No apps in database. Add apps to track trending.",
            "required_signals": ["apps"],
            "items": [],
        }

    has_ranking_history = _check_ranking_history(db, [])
    if not has_ranking_history:
        logger.info("trending endpoint: apps exist but no ranking history")
        return {
            "status": "insufficient_data",
            "message": "Apps exist but no ranking history to compute trends yet.",
            "required_signals": ["ranking_history", "recent_snapshots"],
            "items": [],
        }

    return {
        "status": "success",
        "message": "Trending scores are being computed — check back shortly.",
        "required_signals": None,
        "items": [],
    }


@router.get("/trending/v2", response_model=TrendingAppsResponse)
def get_trending_apps_v2(
    limit: int = Query(10, ge=1, le=50),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    db: Session = Depends(get_db)
):
    """
    Enhanced trending apps from precomputed scores (refreshed every 10 minutes).

    Features:
    - Multi-window momentum (3d, 7d, 14d)
    - Confidence penalty for sparse data
    - Consistency bonus for sustained movers
    - Absolute rank bonus for strong positions
    - Bounded review growth (tiny apps don't dominate)
    - Category normalization

    Returns:
        TrendingAppsResponse with status field indicating success/insufficient_data/empty
    """
    trending = _read_precomputed_trending(db, limit, category_id)

    if trending:
        return {
            "status": "success",
            "message": None,
            "required_signals": None,
            "items": trending,
        }

    app_count = db.query(func.count(models.App.id)).scalar() or 0

    if app_count == 0:
        logger.info("trending/v2 endpoint: no apps in database")
        return {
            "status": "empty",
            "message": "No apps in database. Add apps to track trending.",
            "required_signals": ["apps"],
            "items": [],
        }

    has_ranking_history = _check_ranking_history(db, [])
    if not has_ranking_history:
        logger.info("trending/v2 endpoint: apps exist but no ranking history")
        return {
            "status": "insufficient_data",
            "message": "Apps exist but no ranking history to compute trends yet.",
            "required_signals": ["ranking_history", "recent_snapshots"],
            "items": [],
        }

    return {
        "status": "success",
        "message": "Trending scores are being computed — check back shortly.",
        "required_signals": None,
        "items": [],
    }


@router.get("/fresh-risers", response_model=FreshRisersResponse)
def get_fresh_risers(
    mode: str = Query("fresh_risers", description="Mode: fresh_risers, newest, hidden_gems"),
    limit: int = Query(20, ge=1, le=50),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    db: Session = Depends(get_db)
):
    """
    Get fresh riser apps - newly released apps showing early traction.
    
    Modes:
    - fresh_risers (default): Apps with best overall fresh_riser_score
    - newest: Most recently released apps
    - hidden_gems: Apps with high momentum but lower visibility
    
    Eligibility:
    - Release date within last 7 days (or fallback to created_at within 14 days)
    - At least 5 reviews
    - At least 3 ranking snapshots in last 7 days
    - Valid category
    
    Scoring:
    - freshness_score (25%): How new the app is
    - review_traction_score (25%): Review velocity
    - rank_quality_score (20%): Best rank achieved
    - momentum_score (20%): Ranking improvement
    - niche_viability_score (10%): Category competition level
    """
    engine = ScoringEngine(db)
    fresh_risers = engine.get_fresh_risers(
        mode=mode,
        limit=limit,
        category_id=category_id
    )
    
    if not fresh_risers:
        app_count = db.query(func.count(models.App.id)).scalar() or 0
        
        if app_count == 0:
            logger.info("fresh-risers endpoint: no apps in database")
            return {
                "status": "empty",
                "message": "No apps in database. Add apps to discover fresh risers.",
                "required_signals": ["apps"],
                "items": []
            }
        
        logger.info("fresh-risers endpoint: no apps meet eligibility criteria")
        return {
            "status": "insufficient_data",
            "message": "No apps meet fresh riser eligibility criteria (7-day old, 5+ reviews, 3+ ranking snapshots).",
            "required_signals": ["release_date", "reviews", "ranking_history"],
            "items": []
        }
    
    return {
        "status": "success",
        "message": None,
        "required_signals": None,
        "items": fresh_risers
    }


@router.get("/opportunity-of-day", response_model=OpportunityOfDayWrapperResponse)
def get_opportunity_of_day(db: Session = Depends(get_db)):
    """
    Get the opportunity of the day based on scoring engine analysis.
    
    Returns:
        OpportunityOfDayWrapperResponse with status field indicating success/insufficient_data/empty
    """
    today = datetime.utcnow().date()
    
    report = db.query(models.DailyReport).filter(
        models.DailyReport.date >= today
    ).first()
    
    if report and report.opportunity_of_day:
        return {
            "status": "success",
            "message": None,
            "required_signals": None,
            "item": report.opportunity_of_day
        }
    
    engine = ScoringEngine(db)
    opportunity = engine.generate_opportunity_of_day()
    
    if opportunity:
        return {
            "status": "success",
            "message": None,
            "required_signals": None,
            "item": opportunity
        }
    
    app_count = db.query(func.count(models.App.id)).scalar() or 0
    
    if app_count == 0:
        logger.info("opportunity-of-day endpoint: no apps in database")
        return {
            "status": "empty",
            "message": "No apps in database. Add apps to generate opportunities.",
            "required_signals": ["apps"],
            "item": None
        }
    
    has_ranking = db.query(models.App).filter(
        models.App.current_rank.isnot(None)
    ).first() is not None
    
    if not has_ranking:
        logger.info("opportunity-of-day endpoint: apps exist but no ranking data")
        return {
            "status": "insufficient_data",
            "message": "Apps exist but no ranking data to compute opportunity scores.",
            "required_signals": ["ranking_history", "current_rank"],
            "item": None
        }
    
    logger.info("opportunity-of-day endpoint: apps and ranking exist but no qualifying opportunity")
    return {
        "status": "insufficient_data",
        "message": "Not enough signals to generate opportunity. Keep tracking apps.",
        "required_signals": ["keyword_intelligence", "discovered_keywords", "rank_velocity"],
        "item": None
    }


@router.get("/keyword-opportunities", response_model=KeywordOpportunitiesWrapperResponse)
def get_keyword_opportunities(
    min_difficulty: float = Query(0, ge=0, le=100),
    max_difficulty: float = Query(60, ge=0, le=100),
    db: Session = Depends(get_db)
):
    """
    Get keyword opportunities based on difficulty and other signals.
    
    Returns:
        KeywordOpportunitiesWrapperResponse with status field indicating success/insufficient_data/empty
    """
    engine = ScoringEngine(db)
    opportunities = engine.get_keyword_opportunities(min_difficulty, max_difficulty)
    
    if opportunities:
        return {
            "status": "success",
            "message": None,
            "required_signals": None,
            "items": opportunities
        }
    
    keyword_count = db.query(func.count(models.Keyword.id)).scalar() or 0
    
    if keyword_count == 0:
        logger.info("keyword-opportunities endpoint: no keywords in database")
        return {
            "status": "empty",
            "message": "No keywords in database. Run keyword discovery to generate opportunities.",
            "required_signals": ["keywords"],
            "items": []
        }
    
    has_enrichment = db.query(models.Keyword).filter(
        models.Keyword.search_volume.isnot(None)
    ).first() is not None
    
    if not has_enrichment:
        logger.info("keyword-opportunities endpoint: keywords exist but not enriched")
        return {
            "status": "insufficient_data",
            "message": "Keywords exist but not enriched with search volume/difficulty data.",
            "required_signals": ["search_volume", "difficulty", "trend"],
            "items": []
        }
    
    logger.info("keyword-opportunities endpoint: no qualifying opportunities with current filters")
    return {
        "status": "insufficient_data",
        "message": f"No keyword opportunities found within difficulty range {min_difficulty}-{max_difficulty}.",
        "required_signals": None,
        "items": []
    }


@router.get("/keywords", response_model=List[KeywordResponse])
def get_keywords(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    return db.query(models.Keyword).offset(skip).limit(limit).all()


@router.post("/keywords", response_model=KeywordResponse)
def create_keyword(keyword: KeywordCreate, db: Session = Depends(get_db)):
    from app.services.global_keyword_sink import GlobalKeywordSink
    
    sink = GlobalKeywordSink(db)
    inserted, skipped = sink.push(
        keywords=[keyword.term],
        source="api",
        discovered_from=None,
    )
    
    existing = db.query(models.Keyword).filter(models.Keyword.term == keyword.term).first()
    if not existing:
        raise HTTPException(status_code=400, detail="Keyword could not be inserted (limit reached)")
    return existing


# ---------------------------------------------------------------------------
# Keyword Intelligence helpers
# ---------------------------------------------------------------------------

def _kw_opportunity_score(search_volume: int, difficulty: float, trend: float, apps_count: int) -> float:
    """Composite keyword opportunity score 0–100."""
    vol_pts = min(search_volume / 1000.0 * 3.0, 30.0)
    diff_pts = (1.0 - difficulty / 100.0) * 30.0
    trend_pts = min(max(trend, -10.0) + 10.0, 20.0)
    if apps_count == 0:
        comp_pts = 15.0
    elif apps_count < 5:
        comp_pts = 20.0
    elif apps_count < 20:
        comp_pts = 15.0
    elif apps_count < 60:
        comp_pts = 8.0
    elif apps_count < 150:
        comp_pts = 3.0
    else:
        comp_pts = 0.0
    return round(min(vol_pts + diff_pts + trend_pts + comp_pts, 100.0), 1)


def _kw_feasibility_score(
    difficulty: float,
    apps_count: int,
    ads_presence: float,
    feature_gap_count: int,
    trend: float,
    brand_dominated: bool,
) -> float:
    """Feasibility score 0–100 (can you actually win this keyword)."""
    diff_pts = (1.0 - difficulty / 100.0) * 25.0
    if apps_count < 5:
        scar_pts = 25.0
    elif apps_count < 15:
        scar_pts = 20.0
    elif apps_count < 40:
        scar_pts = 12.0
    elif apps_count < 100:
        scar_pts = 5.0
    else:
        scar_pts = 0.0
    ads_pts = (1.0 - min(ads_presence, 1.0)) * 20.0
    gap_pts = min(feature_gap_count / 10.0 * 15.0, 15.0)
    if trend > 5:
        trend_pts = 15.0
    elif trend > 0:
        trend_pts = 10.0
    elif trend > -5:
        trend_pts = 5.0
    else:
        trend_pts = 0.0
    score = diff_pts + scar_pts + ads_pts + gap_pts + trend_pts
    if brand_dominated:
        score = max(score - 30.0, 0.0)
    return round(min(score, 100.0), 1)


def _kw_classify(difficulty: float, apps_count: int, top_reviews: int, brand_dominated: bool) -> str:
    if brand_dominated or difficulty > 80 or top_reviews > 500_000:
        return "impossible"
    if difficulty > 60 or top_reviews > 100_000 or apps_count > 150:
        return "hard"
    if difficulty > 30 or top_reviews > 10_000 or apps_count > 40:
        return "medium"
    return "easy"


def _is_big_brand_developer(developer: str) -> bool:
    dev_lower = (developer or "").strip().lower()
    if dev_lower in _BIG_BRAND_DEVELOPERS:
        return True
    return any(len(b) > 5 and b in dev_lower for b in _BIG_BRAND_DEVELOPERS)


# ---------------------------------------------------------------------------
# Enhanced Keyword Intelligence Routes
# ---------------------------------------------------------------------------

@router.get("/keywords/enhanced", response_model=KeywordListResponse)
def get_keywords_enhanced(
    search: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    sort_by: str = Query("opportunity_score"),
    sort_order: str = Query("desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    min_volume: int = Query(0, ge=0),
    max_difficulty: float = Query(100.0, ge=0, le=100),
    db: Session = Depends(get_db),
):
    """Enhanced keyword list with opportunity/feasibility scoring and classification."""
    # Apps-count per keyword via subquery
    apps_count_sq = (
        db.query(
            models.AppKeyword.keyword_id,
            func.count(models.AppKeyword.id).label("cnt"),
        )
        .group_by(models.AppKeyword.keyword_id)
        .subquery("apps_cnt")
    )

    q = (
        db.query(
            models.Keyword,
            func.coalesce(apps_count_sq.c.cnt, 0).label("apps_count"),
        )
        .outerjoin(apps_count_sq, apps_count_sq.c.keyword_id == models.Keyword.id)
    )
    if min_volume > 0:
        q = q.filter(models.Keyword.search_volume >= min_volume)
    if max_difficulty < 100:
        q = q.filter(models.Keyword.difficulty <= max_difficulty)
    if search:
        q = q.filter(models.Keyword.term.ilike(f"%{search}%"))

    # ── TRUE total: COUNT(*) with current SQL filters, before Python-only filters ──
    total_count = q.count()

    # ── DB-level ORDER BY so results are deterministic and pagination is correct ──
    _DB_SORT_MAP = {
        "term":             models.Keyword.term,
        "search_volume":    models.Keyword.search_volume,
        "difficulty":       models.Keyword.difficulty,
        "opportunity_score": models.Keyword.opportunity_score,
        "feasibility_score": models.Keyword.feasibility_score,
        "trend":            models.Keyword.trend,
        "trend_score":      models.Keyword.trend_score,
        "trend_growth":     models.Keyword.trend_growth,
        "trend_velocity":   models.Keyword.trend_velocity,
        "dominance_score":  models.Keyword.dominance_score,
        "apps_count":       func.coalesce(apps_count_sq.c.cnt, 0),
    }
    sort_col = _DB_SORT_MAP.get(sort_by, models.Keyword.opportunity_score)
    q = q.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

    # When a classification filter is active (Python-only), over-fetch a large
    # window so we can filter + paginate in memory.  Without it, paginate at DB level.
    if classification:
        rows = q.limit(5000).all()
    else:
        rows = q.offset(skip).limit(limit).all()

    items = []
    for kw, apps_count_raw in rows:
        vol = kw.search_volume or 0
        diff = float(kw.difficulty or 0)
        trend = float(kw.trend or 0)
        # Prefer pipeline-computed scores when available; fall back to legacy formulas
        apps_count = int(kw.apps_count or 0) or int(apps_count_raw or 0)
        opp = float(kw.opportunity_score or 0) or _kw_opportunity_score(vol, diff, trend, apps_count)
        feas = float(kw.feasibility_score or 0) or _kw_feasibility_score(diff, apps_count, 0.0, 0, trend, False)
        cls = _kw_classify(
            diff,
            apps_count,
            0,
            bool(kw.dominance_score and kw.dominance_score >= 80),
        )
        items.append(
            KeywordListItem(
                id=kw.id,
                term=kw.term,
                search_volume=vol,
                difficulty=diff,
                trend=trend,
                opportunity_score=opp,
                feasibility_score=feas,
                classification=cls,
                apps_count=apps_count,
                ads_presence=0.0,
                feature_gap_count=0,
                last_updated=kw.last_updated,
                # External signal fields
                trend_score=float(kw.trend_score or 0),
                trend_growth=float(kw.trend_growth or 0),
                trend_velocity=float(kw.trend_velocity or 0),
                dominance_score=float(kw.dominance_score or 0),
                competition_score=float(kw.competition_score or 0),
                cpc=float(kw.cpc or 0),
                last_enriched=kw.last_enriched,
            )
        )

    if classification:
        items = [i for i in items if i.classification == classification]
        page = items[skip: skip + limit]
    else:
        page = items  # already paginated at DB level

    return KeywordListResponse(
        keywords=page,
        total=total_count,  # TRUE DB count with SQL filters — never capped at 500
        skip=skip,
        limit=limit,
    )


@router.get("/keywords/trending", response_model=TrendingKeywordsResponse)
def get_trending_keywords(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Returns keywords with the strongest rising trend signals (Google Trends velocity + score).
    Used by Trending, Opportunities, and Niche Radar pages.
    """
    # Keywords with real trend data first; fall back to legacy trend field
    rows = (
        db.query(models.Keyword)
        .filter(models.Keyword.opportunity_score > 0)
        .order_by(
            models.Keyword.trend_velocity.desc().nullslast(),
            models.Keyword.trend_growth.desc().nullslast(),
            models.Keyword.opportunity_score.desc().nullslast(),
        )
        .limit(limit * 2)  # over-fetch to allow classification filtering
        .all()
    )

    items = []
    for kw in rows:
        apps_count = int(kw.apps_count or 0)
        diff = float(kw.difficulty or 0)
        dominance = float(kw.dominance_score or 0)
        cls = _kw_classify(diff, apps_count, 0, dominance >= 80)
        items.append(
            TrendingKeywordItem(
                id=kw.id,
                term=kw.term,
                trend_score=float(kw.trend_score or 0),
                trend_growth=float(kw.trend_growth or 0),
                trend_velocity=float(kw.trend_velocity or 0),
                opportunity_score=float(kw.opportunity_score or 0),
                feasibility_score=float(kw.feasibility_score or 0),
                search_volume=int(kw.search_volume or 0),
                difficulty=diff,
                dominance_score=dominance,
                apps_count=apps_count,
                classification=cls,
            )
        )
        if len(items) >= limit:
            break

    return TrendingKeywordsResponse(keywords=items, total=len(items))


@router.post("/keywords/pipeline/run")
async def trigger_keyword_pipeline():
    """
    Manually trigger the full keyword intelligence pipeline.
    Schedules the pipeline as a background asyncio task; returns immediately.
    """
    async def _run():
        from app.services.keyword_intelligence_pipeline import KeywordIntelligencePipeline
        from app.database import SessionLocal
        _db = SessionLocal()
        try:
            logger.info("keyword_pipeline: manual run started")
            pipeline = KeywordIntelligencePipeline(_db)
            summary = await pipeline.run_full_pipeline(max_keywords=300)
            logger.info(f"keyword_pipeline: manual run complete — {summary}")
        except Exception as e:
            logger.error(f"keyword_pipeline: manual run failed — {e}", exc_info=True)
        finally:
            _db.close()

    asyncio.create_task(_run())
    return {"status": "started", "message": "Keyword intelligence pipeline running in background"}


@router.get("/keywords/pipeline/debug")
def get_keyword_pipeline_debug(db: Session = Depends(get_db)):
    """Return enrichment coverage stats for the keyword intelligence pipeline."""
    from app.models.models import KeywordTrend, Keyword as KW, AppKeyword as AKW
    from sqlalchemy import func as sqlfunc
    from app.config import settings as cfg

    total = db.query(KW).count()
    with_app_links = (
        db.query(KW)
        .join(AKW, AKW.keyword_id == KW.id)
        .distinct()
        .count()
    )
    # Google Trends enrichment
    google_trends_success_count = db.query(KW).filter(KW.trend_score > 0).count()
    with_trend_growth = db.query(KW).filter(KW.trend_growth != 0).count()
    # Apple signals enrichment (apps_count > 0 means iTunes returned results)
    apple_signals_success_count = db.query(KW).filter(KW.apps_count > 0).count()
    with_dominance = db.query(KW).filter(KW.dominance_score > 0).count()
    # Scoring
    with_opportunity = db.query(KW).filter(KW.opportunity_score > 0).count()
    with_feasibility = db.query(KW).filter(KW.feasibility_score > 0).count()
    # Pipeline activity
    with_last_enriched = db.query(KW).filter(KW.last_enriched.isnot(None)).count()
    last_run_at = db.query(sqlfunc.max(KW.last_enriched)).scalar()
    # Trend time-series data
    keyword_trends_rows = db.query(KeywordTrend).count()

    return {
        "total_keywords": total,
        "with_app_links": with_app_links,
        # Google Trends
        "google_trends_enabled": cfg.google_trends_enabled,
        "google_trends_success_count": google_trends_success_count,
        "with_trend_growth": with_trend_growth,
        "keyword_trends_rows": keyword_trends_rows,
        # Apple signals
        "apple_signals_success_count": apple_signals_success_count,
        "with_dominance_score": with_dominance,
        # Scoring
        "with_opportunity_score": with_opportunity,
        "with_feasibility_score": with_feasibility,
        # Pipeline health
        "with_last_enriched": with_last_enriched,
        "last_pipeline_run_at": last_run_at.isoformat() if last_run_at else None,
        "dataforseo_enabled": cfg.dataforseo_enabled,
    }


@router.post("/keywords/discovery/run")
async def run_keyword_discovery():
    """
    Trigger the keyword discovery engine in the background.
    Runs all three phases (static expansion, Apple suggestions, metadata phrases)
    and inserts new keywords into the keywords table.
    """
    async def _run():
        from app.services.keyword_discovery_engine import KeywordDiscoveryEngine
        from app.database import SessionLocal
        _db = SessionLocal()
        try:
            engine = KeywordDiscoveryEngine(_db)
            stats = await engine.run_keyword_discovery()
            logger.info(
                f"[API] keyword discovery complete — "
                f"inserted={stats['inserted']}, skipped={stats['skipped']}, "
                f"candidates={stats['candidates']}"
            )
        except Exception as exc:
            logger.error(f"[API] keyword discovery error: {exc}", exc_info=True)
        finally:
            _db.close()

    asyncio.create_task(_run())
    return {"status": "started", "message": "Keyword discovery engine running in background"}


@router.get("/keywords/discovery/status")
def get_keyword_discovery_status(db: Session = Depends(get_db)):
    """Return discovery engine stats: total keywords, discovery_engine sourced, recently added."""
    from sqlalchemy import func as sqlfunc

    total = db.query(models.Keyword).count()
    from_engine = db.query(models.Keyword).filter(models.Keyword.keyword_source == "discovery_engine").count()
    from_user = db.query(models.Keyword).filter(models.Keyword.keyword_source == "user").count()
    last_added = db.query(sqlfunc.max(models.Keyword.first_seen_at)).scalar()

    return {
        "total_keywords": total,
        "from_discovery_engine": from_engine,
        "from_user": from_user,
        "last_discovery_run": last_added.isoformat() if last_added else None,
    }


@router.get("/keywords/{term}/detail", response_model=KeywordDetailResponse)
def get_keyword_detail(
    term: str,
    country: str = Query("us"),
    db: Session = Depends(get_db),
):
    """Full keyword detail: competitors, ads presence, market fragmentation, related keywords."""
    kw = db.query(models.Keyword).filter(models.Keyword.term == term).first()
    vol = kw.search_volume if kw else 0
    diff = float(kw.difficulty if kw else 0)
    trend_val = float(kw.trend if kw else 0)
    kw_id = kw.id if kw else None

    apps_count = 0
    if kw_id:
        apps_count = (
            db.query(func.count(models.AppKeyword.id))
            .filter(models.AppKeyword.keyword_id == kw_id)
            .scalar()
        ) or 0

    # Latest snapshot batch for this keyword
    last_snap_time = (
        db.query(func.max(models.KeywordSearchSnapshot.captured_at))
        .filter(
            models.KeywordSearchSnapshot.keyword == term,
            models.KeywordSearchSnapshot.country == country,
        )
        .scalar()
    )

    top_competitors: list = []
    ads_presence = 0.0
    market_fragmentation = 0.5
    last_scanned = None
    brand_dominated = False

    if last_snap_time:
        last_scanned = last_snap_time.isoformat()
        cutoff = last_snap_time - timedelta(hours=2)
        latest_snaps = (
            db.query(models.KeywordSearchSnapshot)
            .filter(
                models.KeywordSearchSnapshot.keyword == term,
                models.KeywordSearchSnapshot.country == country,
                models.KeywordSearchSnapshot.captured_at >= cutoff,
            )
            .order_by(models.KeywordSearchSnapshot.position)
            .limit(20)
            .all()
        )

        total_snaps = len(latest_snaps)
        sponsored_count = sum(1 for s in latest_snaps if s.is_sponsored)
        ads_presence = round(sponsored_count / total_snaps, 2) if total_snaps > 0 else 0.0

        app_id_strs = [s.app_id for s in latest_snaps]
        apps_by_id = {
            a.app_id: a
            for a in db.query(models.App).filter(models.App.app_id.in_(app_id_strs)).all()
        }

        appearances: dict = {}
        for s in latest_snaps:
            appearances[s.app_id] = appearances.get(s.app_id, 0) + 1
        if appearances:
            max_share = max(appearances.values()) / sum(appearances.values())
            market_fragmentation = round(1.0 - max_share, 2)

        for snap in latest_snaps[:12]:
            app = apps_by_id.get(snap.app_id)
            reviews = app.current_reviews if app else None
            rating = app.current_rating if app else None
            if app and _is_big_brand_developer(app.developer or ""):
                brand_dominated = True
            pos_weight = max(0, 10 - snap.position) / 10.0
            rev_weight = min((reviews or 0) / 50_000.0, 1.0)
            dom_score = round((pos_weight * 0.5 + rev_weight * 0.5) * 100.0, 1)
            top_competitors.append(
                KeywordCompetitorItem(
                    app_id=snap.app_id,
                    app_name=snap.app_name or "Unknown",
                    developer=snap.developer or (app.developer if app else None),
                    icon_url=snap.icon_url or (app.icon_url if app else None),
                    position=snap.position,
                    is_sponsored=snap.is_sponsored,
                    reviews=reviews,
                    rating=rating,
                    dominance_score=dom_score,
                )
            )

    # Feature gaps: aggregate across apps that rank for this keyword
    feature_gap_count = 0
    if kw_id:
        app_ids_for_kw = [
            ak.app_id
            for ak in db.query(models.AppKeyword.app_id)
            .filter(models.AppKeyword.keyword_id == kw_id)
            .limit(50)
            .all()
        ]
        if app_ids_for_kw:
            feature_gap_count = (
                db.query(func.count(models.FeatureGap.id))
                .filter(models.FeatureGap.app_id.in_(app_ids_for_kw))
                .scalar()
            ) or 0

    # Related keywords: keywords that share apps with this one
    related_keywords: list = []
    if kw_id:
        shared_app_ids = [
            ak.app_id
            for ak in db.query(models.AppKeyword.app_id)
            .filter(models.AppKeyword.keyword_id == kw_id)
            .limit(20)
            .all()
        ]
        if shared_app_ids:
            rel_kw_ids = [
                ak.keyword_id
                for ak in db.query(models.AppKeyword.keyword_id)
                .filter(
                    models.AppKeyword.app_id.in_(shared_app_ids),
                    models.AppKeyword.keyword_id != kw_id,
                )
                .distinct()
                .limit(12)
                .all()
            ]
            if rel_kw_ids:
                related_keywords = [
                    k.term
                    for k in db.query(models.Keyword)
                    .filter(models.Keyword.id.in_(rel_kw_ids))
                    .limit(8)
                    .all()
                ]

    top_reviews = max((c.reviews or 0 for c in top_competitors), default=0)

    # Prefer pipeline-stored scores; fall back to legacy formulas
    kw_apps_count = int(kw.apps_count or 0) if kw else 0
    eff_apps_count = kw_apps_count or apps_count
    kw_trend_score = float(kw.trend_score or 0) if kw else 0.0
    kw_trend_growth = float(kw.trend_growth or 0) if kw else 0.0
    kw_trend_velocity = float(kw.trend_velocity or 0) if kw else 0.0
    kw_dominance = float(kw.dominance_score or 0) if kw else 0.0
    kw_competition = float(kw.competition_score or 0) if kw else 0.0
    kw_cpc = float(kw.cpc or 0) if kw else 0.0
    kw_last_enriched = kw.last_enriched if kw else None

    # Dominance from pipeline overrides brand detection for scoring
    if kw_dominance >= 80:
        brand_dominated = True

    opp = float(kw.opportunity_score or 0) if kw else 0.0
    if not opp:
        opp = _kw_opportunity_score(vol, diff, trend_val, eff_apps_count)
    feas = float(kw.feasibility_score or 0) if kw else 0.0
    if not feas:
        feas = _kw_feasibility_score(diff, eff_apps_count, ads_presence, feature_gap_count, trend_val, brand_dominated)
    cls = _kw_classify(diff, eff_apps_count, top_reviews, brand_dominated)

    # Google Trends sparkline points from keyword_trends table
    google_trend_points: list = []
    if kw_id:
        trend_rows = (
            db.query(models.KeywordTrend)
            .filter(models.KeywordTrend.keyword_id == kw_id)
            .order_by(models.KeywordTrend.week_start.asc())
            .limit(16)
            .all()
        )
        for tr in trend_rows:
            google_trend_points.append(
                GoogleTrendWeekPoint(
                    date=tr.week_start.strftime("%Y-%m-%d"),
                    interest=tr.interest_score or 0,
                )
            )

    return KeywordDetailResponse(
        id=kw_id,
        term=term,
        search_volume=vol,
        difficulty=diff,
        trend=trend_val,
        opportunity_score=opp,
        feasibility_score=feas,
        classification=cls,
        apps_count=eff_apps_count,
        ads_presence=ads_presence,
        top_competitors=top_competitors,
        related_keywords=related_keywords,
        feature_gap_count=feature_gap_count,
        market_fragmentation=market_fragmentation,
        last_scanned=last_scanned,
        trend_score=kw_trend_score,
        trend_growth=kw_trend_growth,
        trend_velocity=kw_trend_velocity,
        dominance_score=kw_dominance,
        competition_score=kw_competition,
        cpc=kw_cpc,
        last_enriched=kw_last_enriched,
        google_trend_points=google_trend_points,
    )


@router.get("/keywords/{term}/trend", response_model=KeywordTrendResponse)
def get_keyword_trend_data(
    term: str,
    country: str = Query("us"),
    days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db),
):
    """Keyword trend: daily apps_count, avg_position, sponsored_ratio over time."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(models.KeywordSearchSnapshot)
        .filter(
            models.KeywordSearchSnapshot.keyword == term,
            models.KeywordSearchSnapshot.country == country,
            models.KeywordSearchSnapshot.captured_at >= cutoff,
        )
        .order_by(models.KeywordSearchSnapshot.captured_at)
        .all()
    )

    from collections import defaultdict
    day_data: dict = defaultdict(list)
    for row in rows:
        day = row.captured_at.strftime("%Y-%m-%d") if row.captured_at else "unknown"
        day_data[day].append(row)

    trend_points = []
    for day in sorted(day_data.keys()):
        day_rows = day_data[day]
        app_ids = {r.app_id for r in day_rows}
        sponsored = sum(1 for r in day_rows if r.is_sponsored)
        avg_pos = sum(r.position for r in day_rows) / len(day_rows)
        trend_points.append(
            KeywordTrendPoint(
                date=day,
                apps_count=len(app_ids),
                avg_position=round(avg_pos, 1),
                sponsored_ratio=round(sponsored / len(day_rows), 2) if day_rows else 0.0,
            )
        )

    return KeywordTrendResponse(term=term, trend_points=trend_points)


@router.get("/opportunities", response_model=List[OpportunityResponse])
def get_opportunities(
    skip: int = 0,
    limit: int = 50,
    min_probability: Optional[float] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Opportunity)
    
    if min_probability:
        query = query.filter(models.Opportunity.success_probability >= min_probability)
    
    return query.order_by(models.Opportunity.success_probability.desc()).offset(skip).limit(limit).all()


@router.get("/categories", response_model=List[dict])
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(models.Category).all()
    return [{"id": c.id, "name": c.name, "slug": c.slug} for c in categories]


@router.get("/rankings", response_model=List[RankingResponse])
def get_rankings(
    app_id: Optional[int] = None,
    chart_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = db.query(models.Ranking)
    
    if app_id:
        query = query.filter(models.Ranking.app_id == app_id)
    if chart_type:
        query = query.filter(models.Ranking.chart_type == chart_type)
    
    rankings = query.order_by(models.Ranking.recorded_at.desc()).limit(limit).all()
    
    if not rankings and app_id:
        app = db.query(models.App).filter(models.App.id == app_id).first()
        if app:
            return []
    
    return rankings


@router.get("/apps/{app_id}/detail", response_model=AppDetailResponse)
def get_app_detail(app_id: int, db: Session = Depends(get_db)):
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    versions = db.query(models.AppVersion).filter(
        models.AppVersion.app_id == app_id
    ).order_by(models.AppVersion.release_date.desc()).limit(20).all()
    
    analytics = db.query(models.AppAnalytics).filter(
        models.AppAnalytics.app_id == app_id
    ).order_by(models.AppAnalytics.computed_at.desc()).first()
    
    return {
        **app.__dict__,
        "versions": versions,
        "analytics": analytics
    }


@router.get("/apps/{app_id}/versions", response_model=List[AppVersionResponse])
def get_app_versions(app_id: int, db: Session = Depends(get_db)):
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    return db.query(models.AppVersion).filter(
        models.AppVersion.app_id == app_id
    ).order_by(models.AppVersion.release_date.desc()).all()


@router.get("/apps/{app_id}/reviews", response_model=List[ReviewResponse])
def get_app_reviews(
    app_id: int,
    rating: Optional[int] = None,
    skip: int = 0,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    query = db.query(models.Review).filter(models.Review.app_id == app_id)
    
    if rating:
        query = query.filter(models.Review.rating == rating)
    
    return query.order_by(models.Review.date.desc()).offset(skip).limit(limit).all()


@router.get("/apps/{app_id}/analytics", response_model=AppAnalyticsResponse)
def get_app_analytics(app_id: int, db: Session = Depends(get_db)):
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    analytics = db.query(models.AppAnalytics).filter(
        models.AppAnalytics.app_id == app_id
    ).order_by(models.AppAnalytics.computed_at.desc()).first()
    
    if not analytics:
        return {
            "id": 0,
            "app_id": app_id,
            "review_growth_30d": 0,
            "review_growth_90d": 0,
            "rating_change_30d": 0,
            "rating_change_90d": 0,
            "sentiment_score": 0,
            "sentiment_label": "unknown",
            "common_complaints": [],
            "common_features": [],
            "positive_themes": [],
            "bug_keywords": [],
            "churn_risk_score": 0,
            "update_cadence_score": 0,
            "quality_score": 0,
            "opportunity_score": 0,
            "computed_at": datetime.utcnow()
        }
    
    return analytics


@router.get("/apps/{app_id}/market-weakness", response_model=MarketWeaknessResponse)
def get_market_weakness(app_id: int, db: Session = Depends(get_db)):
    """
    Return per-country negative review analysis for an app.
    Countries with < 20 reviews are excluded from results.
    On first call, computes and stores the stats on demand.
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    stats = (
        db.query(models.AppMarketWeakness)
        .filter(models.AppMarketWeakness.app_id == app_id)
        .order_by(models.AppMarketWeakness.negative_ratio.desc())
        .all()
    )

    if not stats:
        engine = ScoringEngine(db)
        computed = engine.compute_market_weakness(app_id)
        return {
            "app_id": app_id,
            "countries": computed,
            "total_countries": len(computed),
            "has_data": len(computed) > 0,
        }

    return {
        "app_id": app_id,
        "countries": [
            {
                "country": s.country,
                "total_reviews": s.total_reviews,
                "negative_reviews": s.negative_reviews,
                "average_rating": s.average_rating,
                "negative_ratio": s.negative_ratio,
                "computed_at": s.computed_at,
            }
            for s in stats
        ],
        "total_countries": len(stats),
        "has_data": len(stats) > 0,
    }


@router.get("/apps/{app_id}/feature-gaps", response_model=FeatureGapListResponse)
def get_feature_gaps(app_id: int, db: Session = Depends(get_db)):
    """
    Return feature gap analysis for an app.
    Computes on demand if no data exists yet.
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    analyzer = FeatureGapAnalyzer(db)
    gaps = analyzer.get_gaps(app_id)

    if not gaps:
        gaps = analyzer.compute_for_app(app_id)

    return {
        "app_id": app_id,
        "feature_gaps": gaps,
        "total_features": len(gaps),
        "total_mentions": sum(g["mentions"] for g in gaps),
        "has_data": len(gaps) > 0,
    }


# ---------------------------------------------------------------------------
# AI App Ideas
# ---------------------------------------------------------------------------

@router.get("/ideas", response_model=AppIdeaListResponse)
def get_ideas(
    sort_by: str = Query("opportunity_score"),
    sort_order: str = Query("desc"),
    pattern_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    from app.scoring.idea_generator import IdeaGenerator
    gen = IdeaGenerator(db)
    ideas, total = gen.get_ideas(
        sort_by=sort_by,
        sort_order=sort_order,
        pattern_type=pattern_type,
        category=category,
        keyword=keyword,
        skip=skip,
        limit=limit,
    )
    last_generated = ideas[0].generated_at if ideas else None
    return {
        "ideas": ideas,
        "total": total,
        "skip": skip,
        "limit": limit,
        "last_generated": last_generated,
    }


@router.post("/ideas/generate", response_model=AppIdeaListResponse)
def trigger_generate_ideas(db: Session = Depends(get_db)):
    from app.scoring.idea_generator import IdeaGenerator
    gen = IdeaGenerator(db)
    gen.generate_all()
    ideas, total = gen.get_ideas(sort_by="opportunity_score", sort_order="desc", skip=0, limit=20)
    last_generated = ideas[0].generated_at if ideas else None
    return {
        "ideas": ideas,
        "total": total,
        "skip": 0,
        "limit": 20,
        "last_generated": last_generated,
    }


@router.post("/apps/{app_id}/feature-gaps/analyze", response_model=FeatureGapListResponse)
def analyze_feature_gaps(app_id: int, db: Session = Depends(get_db)):
    """
    Re-run feature gap analysis for an app (force refresh).
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    analyzer = FeatureGapAnalyzer(db)
    gaps = analyzer.compute_for_app(app_id)

    return {
        "app_id": app_id,
        "feature_gaps": gaps,
        "total_features": len(gaps),
        "total_mentions": sum(g["mentions"] for g in gaps),
        "has_data": len(gaps) > 0,
    }


# ---------------------------------------------------------------------------
# Admin bootstrap — populates an empty database from scratch
# ---------------------------------------------------------------------------

_bootstrap_running = False


@router.post("/admin/bootstrap")
async def bootstrap_database(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    **One-shot bootstrap for a fresh / empty Railway database.**

    Runs the full pipeline in the background and returns immediately:
      1. Discovery  — keyword search (10 keywords × 50 results) + top charts
      2. Full scrape — metadata, versions, reviews for every discovered app
      3. Scoring     — opportunities, market weakness, feature gaps, ideas,
                       install/revenue estimates

    Call this once after first deploy. Check GET /dashboard/stats to see
    progress. The job runs for ~5–15 minutes depending on Railway capacity.

    Returns 409 if a bootstrap is already running.
    """
    global _bootstrap_running
    if _bootstrap_running:
        raise HTTPException(
            status_code=409,
            detail="Bootstrap already running — wait for it to complete then check /dashboard/stats",
        )

    total_apps_before = db.query(models.App).count()

    async def _run():
        global _bootstrap_running
        _bootstrap_running = True
        try:
            from app.workers.tasks import run_scrape_task, run_scoring_task
            logger.info("[BOOTSTRAP] Starting full pipeline on empty database")
            await run_scrape_task()
            logger.info("[BOOTSTRAP] Scrape complete — running scoring")
            await asyncio.to_thread(run_scoring_task)
            logger.info("[BOOTSTRAP] Bootstrap complete")
        except Exception as exc:
            logger.error(f"[BOOTSTRAP] Failed: {exc}", exc_info=True)
        finally:
            _bootstrap_running = False

    background_tasks.add_task(_run)

    return {
        "status": "started",
        "apps_in_db_before": total_apps_before,
        "message": (
            "Bootstrap pipeline started in background. "
            "Phase 1 (discovery) takes ~2–3 min, Phase 2 (full scrape) ~5–10 min. "
            "Poll GET /api/v1/dashboard/stats to track progress."
        ),
        "poll_url": "/api/v1/dashboard/stats",
    }


@router.get("/admin/bootstrap/status")
def bootstrap_status(db: Session = Depends(get_db)):
    """Check whether a bootstrap is running and how many apps are in the DB."""
    return {
        "bootstrap_running": _bootstrap_running,
        "total_apps": db.query(models.App).count(),
        "total_keywords": db.query(models.Keyword).count(),
        "total_reviews": db.query(models.Review).count(),
    }


@router.get("/admin/discovery/metrics")
def get_discovery_metrics(db: Session = Depends(get_db)):
    """
    Live discovery engine metrics:
    - Total apps in DB and new apps added today/yesterday
    - Discovery queue counts (pending / scraping / done / failed)
    - Number of sources (chart+keyword+developer combinations) scanned today vs total
    - Estimated coverage percentage

    Use this to monitor how fast the catalog is growing.
    """
    from app.workers.discovery_engine import DiscoveryEngine
    engine = DiscoveryEngine(db)
    return engine.get_metrics()


@router.post("/admin/discovery/run-charts")
async def trigger_chart_discovery(
    batch_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Manually trigger a chart discovery batch (up to `batch_size` chart pages).
    Useful after first deploy or when you want to accelerate coverage.
    """
    from app.workers.discovery_engine import DiscoveryEngine
    engine = DiscoveryEngine(db)
    new_ids = await engine.run_chart_discovery_batch(batch_size=batch_size)
    return {"status": "ok", "new_ids_queued": new_ids}


@router.post("/admin/discovery/run-keywords")
async def trigger_keyword_discovery(db: Session = Depends(get_db)):
    """
    Manually trigger keyword discovery for all 100+ keywords not yet run today.
    """
    from app.workers.discovery_engine import DiscoveryEngine
    engine = DiscoveryEngine(db)
    new_ids = await engine.run_keyword_discovery()
    return {"status": "ok", "new_ids_queued": new_ids}


@router.post("/admin/discovery/process-queue")
async def trigger_queue_processing(
    batch_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Manually process up to `batch_size` items from the discovery queue
    (full scrape: metadata + versions + reviews).
    """
    from app.workers.discovery_engine import DiscoveryEngine
    engine = DiscoveryEngine(db)
    scraped = await engine.process_queue(batch_size=batch_size)
    return {"status": "ok", "apps_scraped": scraped}


@router.post("/scrape/all")
async def scrape_all_apps(db: Session = Depends(get_db)):
    from app.workers.tasks import ScraperWorker
    
    logger.info("Manual scrape all triggered via API")
    
    worker = ScraperWorker()
    await worker.initialize()
    
    try:
        success_count = await worker.scrape_all_tracked_apps()
        return {
            "status": "completed",
            "apps_scraped": success_count,
            "message": f"Successfully scraped full details for {success_count} apps"
        }
    except Exception as e:
        logger.error(f"Scrape all failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await worker.cleanup()


@router.post("/apps/{app_id}/refresh")
async def scrape_single_app(app_id: int, db: Session = Depends(get_db)):
    from app.workers.tasks import ScraperWorker

    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    logger.info(f"Manual refresh triggered for app {app_id} ({app.app_id})")

    worker = ScraperWorker()
    await worker.initialize()

    try:
        success = await worker.scrape_app_full_details(app.app_id)

        if success:
            db.refresh(app)
            return {
                "status": "completed",
                "app_id": app.id,
                "app_name": app.name,
                "message": "App details, versions, and reviews refreshed successfully"
            }
        else:
            return {
                "status": "partial",
                "app_id": app.id,
                "message": "App found but no details could be scraped"
            }
    except Exception as e:
        logger.error(f"Scrape app {app_id} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await worker.cleanup()


# ---------------------------------------------------------------------------
# Scheduler status & control
# ---------------------------------------------------------------------------

@router.get("/scheduler/status")
def get_scheduler_status():
    """Return the current state of the scheduler and all registered jobs."""
    from app.workers.scheduler import scheduler

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "running": scheduler.running,
        "jobs": jobs,
    }


@router.post("/scheduler/jobs/{job_id}/trigger")
async def trigger_job_now(job_id: str):
    """
    Immediately trigger a scheduled job by its ID.

    Valid job IDs:
      - hourly_reviews_ratings
      - hourly_scoring
      - full_metadata
      - discovery
    """
    from app.workers.scheduler import scheduler

    job = scheduler.get_job(job_id)
    if not job:
        valid = [j.id for j in scheduler.get_jobs()]
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found. Valid IDs: {valid}",
        )

    job.modify(next_run_time=datetime.utcnow())
    logger.info(f"Manual trigger requested for scheduler job '{job_id}'")
    return {
        "status": "triggered",
        "job_id": job_id,
        "message": f"Job '{job_id}' will run momentarily",
    }


# ---------------------------------------------------------------------------
# Keyword Intelligence
# ---------------------------------------------------------------------------

@router.get("/apps/{app_id}/keyword-intelligence", response_model=KeywordIntelligenceResponse)
def get_keyword_intelligence(app_id: int, db: Session = Depends(get_db)):
    """
    Return keyword intelligence for an app: primary keyword, organic vs
    sponsored rankings, traffic mix estimate.
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    from app.services.keyword_intelligence import KeywordIntelligenceService
    svc = KeywordIntelligenceService(db)
    result = svc.get_app_intelligence(app.app_id)

    if not result:
        # Return empty but valid response
        return {
            "app_id": app.app_id,
            "app_name": app.name,
            "primary_keyword": None,
            "confidence": 0,
            "organic_keywords": [],
            "ads_keywords": [],
            "traffic_mix": {"organic": 0, "ads": 0},
            "total_snapshots": 0,
            "last_scanned": None,
        }
    return result


# ---------------------------------------------------------------------------
# Keyword Extraction Intelligence — metadata-based keyword extraction
# ---------------------------------------------------------------------------

@router.get("/apps/{app_id}/keywords/intelligence", response_model=KeywordExtractionResponse)
def get_keywords_intelligence(
    app_id: int,
    refresh: bool = Query(False, description="Force re-extraction even if data is fresh"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """
    Return keyword intelligence extracted from the app's title, subtitle,
    and description, enriched with iTunes Search API signals.

    Returns cached data immediately.  A background extraction job is triggered
    automatically when data is missing, stale (>24 h), or refresh=true.
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    from app.services.keyword_extraction_service import KeywordExtractionService
    svc = KeywordExtractionService(db)

    stored = svc.get_stored(app_id)
    needs_extraction = refresh or svc.is_stale(app_id)

    if needs_extraction and background_tasks is not None:
        background_tasks.add_task(_run_keyword_extraction_bg, app_id)

    last_extracted = stored[0]["extracted_at"] if stored else None

    return {
        "app_id": app.app_id,
        "app_name": app.name,
        "keywords": stored,
        "extracting": needs_extraction,
        "total": len(stored),
        "last_extracted": last_extracted,
    }


@router.post("/apps/{app_id}/keywords/intelligence/extract")
async def trigger_keyword_extraction(app_id: int, db: Session = Depends(get_db)):
    """
    Immediately trigger keyword extraction in the background.
    Returns right away; poll GET /apps/{id}/keywords/intelligence for results.
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    asyncio.create_task(_run_keyword_extraction_async(app_id))
    return {"status": "started", "app_id": app.app_id, "app_name": app.name}


def _run_keyword_extraction_bg(app_id: int) -> None:
    """BackgroundTasks-compatible wrapper (sync, called in thread pool)."""
    from app.database import SessionLocal
    from app.services.keyword_extraction_service import KeywordExtractionService
    db = SessionLocal()
    try:
        svc = KeywordExtractionService(db)
        svc.extract_keywords_for_app(app_id)
    except Exception as exc:
        logger.error(f"[KeywordExtraction] background job failed app={app_id}: {exc}")
    finally:
        db.close()


async def _run_keyword_extraction_async(app_id: int) -> None:
    """asyncio.create_task-compatible wrapper — runs in thread pool."""
    import asyncio as _asyncio
    await _asyncio.to_thread(_run_keyword_extraction_bg, app_id)


# ---------------------------------------------------------------------------
# Keyword Discovery — autocomplete + affix expansion per app
# ---------------------------------------------------------------------------

@router.get("/apps/{app_id}/keywords/discovered", response_model=DiscoveredKeywordsResponse)
def get_discovered_keywords(
    app_id: int,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Return keywords discovered for this app via autocomplete expansion,
    sorted by opportunity_score DESC.
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    from app.services.keyword_discovery_service import KeywordDiscoveryService
    svc = KeywordDiscoveryService(db)
    rows = svc.get_discovered(app_id, limit=limit)

    last_discovered = rows[0]["created_at"] if rows else None

    return {
        "app_id": app.app_id,
        "app_name": app.name,
        "keywords": rows,
        "total": len(rows),
        "discovering": False,
        "last_discovered": last_discovered,
    }


@router.post("/apps/{app_id}/keywords/discover", response_model=DiscoveredKeywordsResponse)
async def trigger_keyword_discovery(app_id: int, db: Session = Depends(get_db)):
    """
    Trigger keyword discovery for this app in the background.
    Returns immediately; poll GET /apps/{id}/keywords/discovered for results.

    Requires: app must have extracted keywords in app_keyword_intelligence.
    Run POST /apps/{id}/keywords/intelligence/extract first if this is a new app.
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    # Guard: discovery is seed-driven — it needs extracted keywords first.
    has_seeds = (
        db.query(models.AppKeywordIntelligence)
        .filter(models.AppKeywordIntelligence.app_id == app_id)
        .limit(1)
        .first()
    )
    if not has_seeds:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No extracted keywords found for app {app_id}. "
                f"Run POST /api/v1/apps/{app_id}/keywords/intelligence/extract first "
                f"to extract keywords from the app's metadata before running discovery."
            ),
        )

    from app.services.keyword_discovery_service import KeywordDiscoveryService

    # Return current state immediately and kick off discovery in background
    svc = KeywordDiscoveryService(db)
    existing = svc.get_discovered(app_id, limit=200)
    last_discovered = existing[0]["created_at"] if existing else None

    asyncio.create_task(_run_keyword_discovery_async(app_id))

    return {
        "app_id": app.app_id,
        "app_name": app.name,
        "keywords": existing,
        "total": len(existing),
        "discovering": True,
        "last_discovered": last_discovered,
    }


def _run_keyword_discovery_bg(app_id: int) -> None:
    """BackgroundTasks-compatible sync wrapper (runs in thread pool)."""
    from app.database import SessionLocal
    from app.services.keyword_discovery_service import KeywordDiscoveryService
    db = SessionLocal()
    try:
        svc = KeywordDiscoveryService(db)
        count = svc.discover_for_app(app_id)
        logger.info(f"[Discovery] background job: {count} new keywords for app {app_id}")
    except Exception as exc:
        logger.error(f"[Discovery] background job failed app={app_id}: {exc}")
    finally:
        db.close()


async def _run_keyword_discovery_async(app_id: int) -> None:
    """asyncio.create_task-compatible wrapper — runs in thread pool."""
    await asyncio.to_thread(_run_keyword_discovery_bg, app_id)


# ---------------------------------------------------------------------------
# Keyword Rank Tracker — manual trigger & search
# ---------------------------------------------------------------------------

@router.post("/keyword-tracker/run", response_model=KeywordTrackerRunResponse)
async def run_keyword_tracker(
    country: str = Query("us"),
    keyword_limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Trigger a keyword rank tracking scan immediately.
    Scrapes App Store search results for all tracked keywords.
    """
    import time as _time
    from app.jobs.keyword_rank_tracker import run_keyword_rank_tracker

    logger.info(f"Manual keyword tracker run: country={country}, limit={keyword_limit}")
    try:
        summary = await run_keyword_rank_tracker(
            country=country,
            keyword_limit=keyword_limit,
        )
        return {
            "status": "completed",
            "keywords_scanned": summary["keywords_scanned"],
            "total_results": summary["total_results"],
            "sponsored_results": summary["sponsored_results"],
            "elapsed_seconds": summary["elapsed_seconds"],
        }
    except Exception as e:
        logger.error(f"Keyword tracker run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keyword-tracker/search", response_model=KeywordTrackerRunResponse)
async def search_single_keyword(
    keyword: str = Query(..., description="Keyword to search"),
    country: str = Query("us"),
    db: Session = Depends(get_db),
):
    """
    Scrape App Store search results for a single keyword immediately.
    Results are saved to keyword_search_snapshots.
    """
    from app.jobs.keyword_rank_tracker import run_keyword_rank_tracker

    logger.info(f"Single keyword search: {keyword!r} country={country}")
    try:
        summary = await run_keyword_rank_tracker(
            country=country,
            custom_keywords=[keyword],
        )
        return {
            "status": "completed",
            "keywords_scanned": summary["keywords_scanned"],
            "total_results": summary["total_results"],
            "sponsored_results": summary["sponsored_results"],
            "elapsed_seconds": summary["elapsed_seconds"],
        }
    except Exception as e:
        logger.error(f"Single keyword search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/keyword-search-snapshots", response_model=KeywordSnapshotListResponse)
def get_keyword_snapshots(
    keyword: Optional[str] = Query(None),
    app_id: Optional[str] = Query(None),
    is_sponsored: Optional[bool] = Query(None),
    country: str = Query("us"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Return keyword search snapshots with optional filters.
    """
    query = db.query(models.KeywordSearchSnapshot).filter(
        models.KeywordSearchSnapshot.country == country
    )

    if keyword:
        query = query.filter(models.KeywordSearchSnapshot.keyword.ilike(f"%{keyword}%"))
    if app_id:
        query = query.filter(models.KeywordSearchSnapshot.app_id == app_id)
    if is_sponsored is not None:
        query = query.filter(models.KeywordSearchSnapshot.is_sponsored == is_sponsored)

    query = query.order_by(models.KeywordSearchSnapshot.captured_at.desc())
    total = query.count()
    snapshots = query.offset(skip).limit(limit).all()

    return {
        "snapshots": snapshots,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/keyword-tracker/traffic-sources")
def get_traffic_sources(
    db: Session = Depends(get_db),
):
    """
    Return traffic source mix (organic vs ads) for all apps with snapshot data.
    """
    from app.services.keyword_intelligence import KeywordIntelligenceService
    svc = KeywordIntelligenceService(db)
    return {"traffic_sources": svc.compute_traffic_sources_all()}


# ---------------------------------------------------------------------------
# Install & Revenue Estimates
# ---------------------------------------------------------------------------

@router.get("/apps/{app_id}/install-estimate", response_model=InstallEstimateResponse)
def get_install_estimate(app_id: int, db: Session = Depends(get_db)):
    """Return install estimate for an app. Computes on demand if not cached."""
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    from app.services.install_estimator import InstallEstimator
    est = InstallEstimator(db)
    result = est.estimate(app_id)

    # Persist if not already stored
    if not app.estimated_installs_min:
        est.compute_and_save(app)
        db.commit()

    return {**result, "app_id": app_id}


@router.get("/apps/{app_id}/revenue-estimate", response_model=RevenueEstimateResponse)
def get_revenue_estimate(app_id: int, db: Session = Depends(get_db)):
    """Return revenue estimate for an app. Computes on demand."""
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    from app.services.revenue_estimator import RevenueEstimator
    est = RevenueEstimator(db)
    result = est.estimate(app_id)
    return {**result, "app_id": app_id}


# ---------------------------------------------------------------------------
# Keyword History
# ---------------------------------------------------------------------------

@router.get("/apps/{app_id}/keyword-history", response_model=KeywordHistoryResponse)
def get_keyword_history(
    app_id: int,
    keyword: str = Query(..., description="Keyword to get history for"),
    country: str = Query("us"),
    days: int = Query(90, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Return rank-over-time history for a specific app+keyword pair."""
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    from app.services.keyword_history import KeywordHistoryService
    svc = KeywordHistoryService(db)
    return svc.get_history(app.app_id, keyword, country=country, days=days)


@router.get("/apps/{app_id}/keyword-history/keywords")
def get_app_keyword_list(
    app_id: int,
    country: str = Query("us"),
    db: Session = Depends(get_db),
):
    """Return all keywords this app has appeared in (for populating a keyword picker)."""
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    from app.services.keyword_history import KeywordHistoryService
    svc = KeywordHistoryService(db)
    keywords = svc.get_all_keywords_for_app(app.app_id, country=country)
    return {"keywords": keywords}


# ---------------------------------------------------------------------------
# Niche Radar
# ---------------------------------------------------------------------------

@router.get("/niche-radar", response_model=NicheRadarResponse)
def get_niche_radar(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Return top emerging App Store micro-niches detected from signals."""
    from app.services.niche_radar import NicheRadarEngine
    from datetime import datetime, timezone
    try:
        radar = NicheRadarEngine(db)
        niches = radar.scan(limit=limit)
    except Exception as exc:
        logger.warning("NicheRadar scan failed, returning empty: %s", exc)
        niches = []
    return {
        "niches": niches,
        "total": len(niches),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Review Intelligence (LLM)
# ---------------------------------------------------------------------------

@router.get("/apps/{app_id}/review-intelligence", response_model=ReviewIntelligenceResponse)
def get_review_intelligence(
    app_id: int,
    force: bool = Query(False, description="Force re-analysis even if cached"),
    db: Session = Depends(get_db),
):
    """
    Return LLM-powered review analysis for an app.
    Uses cached result if available; pass force=true to re-run.
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    from app.services.review_intelligence import ReviewIntelligenceService
    svc = ReviewIntelligenceService(db)
    result = svc.analyze_app(app_id, force=force)
    return result


# ---------------------------------------------------------------------------
# App Autopsy
# ---------------------------------------------------------------------------

@router.get("/apps/{app_id}/autopsy", response_model=AppAutopsyResponse)
def get_app_autopsy(
    app_id: int,
    use_llm: bool = Query(True, description="Generate LLM narrative (requires ANTHROPIC_API_KEY)"),
    db: Session = Depends(get_db),
):
    """
    Return a comprehensive 'Why Is This App Winning?' autopsy report.
    Includes install estimates, rank trajectory, update cadence,
    competitor gaps, and an optional AI-generated narrative.
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    from app.services.app_autopsy import AppAutopsyService
    svc = AppAutopsyService(db)
    result = svc.get_autopsy(app_id, use_llm=use_llm)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


# ---------------------------------------------------------------------------
# Phase-1 Keyword Discovery — alphabet + competitor mining + gap + scoring
# ---------------------------------------------------------------------------

@router.post("/apps/{app_id}/keywords/discover-phase1", response_model=KeywordOpportunitiesResponse)
async def trigger_phase1_discovery(app_id: int, db: Session = Depends(get_db)):
    """
    Trigger Phase-1 keyword discovery pipeline in the background:
      1. Alphabet mining (seed × a-z × autocomplete)
      2. Competitor keyword extraction (iTunes search + n-gram phrases)
      3. Keyword gap analysis (marks keyword_gap = True where competitor ≤ 10)
      4. Opportunity scoring (recomputes opportunity_score for all keywords)

    Returns immediately with current top-50 opportunities; poll
    GET /apps/{id}/keywords/opportunities for live results.

    Requires: app must have extracted keywords in app_keyword_intelligence.
    Run POST /apps/{id}/keywords/intelligence/extract first if this is a new app.
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    # Guard: Phase-1 pipeline is seed-driven — it needs extracted keywords first.
    has_seeds = (
        db.query(models.AppKeywordIntelligence)
        .filter(models.AppKeywordIntelligence.app_id == app_id)
        .limit(1)
        .first()
    )
    if not has_seeds:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No extracted keywords found for app {app_id}. "
                f"Run POST /api/v1/apps/{app_id}/keywords/intelligence/extract first "
                f"to extract keywords from the app's metadata before running Phase-1 discovery."
            ),
        )

    # Kick off the full pipeline in the background
    asyncio.create_task(_run_phase1_async(app_id))

    # Return current top opportunities immediately
    from app.services.opportunity_service import OpportunityScoreService
    opp_svc = OpportunityScoreService(db)
    current = opp_svc.get_top_opportunities(app_id, limit=50)

    return {
        "app_id": app.app_id,
        "app_name": app.name,
        "opportunities": current,
        "total": len(current),
        "discovering": True,
    }


@router.get("/apps/{app_id}/keywords/opportunities", response_model=KeywordOpportunitiesResponse)
def get_keyword_opportunities(
    app_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Return top keywords for this app sorted by opportunity_score DESC.
    Includes gap keywords (keyword_gap=True) and competitor rank info.
    """
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    from app.services.opportunity_service import OpportunityScoreService
    svc = OpportunityScoreService(db)
    opportunities = svc.get_top_opportunities(app_id, limit=limit)

    return {
        "app_id": app.app_id,
        "app_name": app.name,
        "opportunities": opportunities,
        "total": len(opportunities),
        "discovering": False,
    }


def _run_phase1_bg(app_id: int) -> None:
    """Sync wrapper: runs the full Phase-1 pipeline for one app."""
    from app.database import SessionLocal
    from app.services.alphabet_mining_service import AlphabetMiningService
    from app.services.competitor_keyword_service import CompetitorKeywordService
    from app.services.keyword_gap_service import KeywordGapService
    from app.services.opportunity_service import OpportunityScoreService

    db = SessionLocal()
    try:
        logger.info(f"[Phase1] Running Phase-1 discovery for app {app_id}")

        # 1. Alphabet mining
        alpha_svc = AlphabetMiningService(db)
        alpha_count = alpha_svc.mine_for_app(app_id)
        logger.info(f"[Phase1] Alphabet mining: {alpha_count} new keywords for app {app_id}")

        # 2. Competitor keyword mining
        comp_svc = CompetitorKeywordService(db)
        comp_count = comp_svc.mine_for_app(app_id)
        logger.info(f"[Phase1] Competitor mining: {comp_count} new keywords for app {app_id}")

        # 3. Gap analysis
        gap_svc = KeywordGapService(db)
        gap_count = gap_svc.analyze_for_app(app_id)
        logger.info(f"[Phase1] Found {gap_count} gap keywords for app {app_id}")

        # 4. Opportunity scoring
        opp_svc = OpportunityScoreService(db)
        opp_svc.score_for_app(app_id)

    except Exception as exc:
        logger.error(f"[Phase1] Pipeline failed for app {app_id}: {exc}", exc_info=True)
    finally:
        db.close()


async def _run_phase1_async(app_id: int) -> None:
    """asyncio.create_task-compatible wrapper — runs Phase-1 in thread pool."""
    await asyncio.to_thread(_run_phase1_bg, app_id)


# ===========================================================================
# Growth Intelligence: Metric Snapshots
# ===========================================================================

@router.get("/apps/{app_id}/metrics", response_model=MetricSnapshotHistoryResponse)
def get_app_metrics(
    app_id: int,
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """
    Latest metric snapshot + time-series history for an app.
    Snapshot contains unified download + revenue estimates.
    """
    from app.services.metric_snapshot_service import MetricSnapshotService

    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    svc = MetricSnapshotService(db)
    latest = svc.latest_snapshot(app_id)
    history = svc.snapshot_history(app_id, days=days)
    delta = svc.downloads_delta(app_id, days=7)

    return MetricSnapshotHistoryResponse(
        app_id=app_id,
        snapshots=history,
        latest=latest,
        downloads_delta_7d=delta,
    )


@router.post("/apps/{app_id}/metrics/compute")
def compute_app_metrics(app_id: int, db: Session = Depends(get_db)):
    """On-demand metric snapshot computation for a single app."""
    from app.services.metric_snapshot_service import MetricSnapshotService

    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    svc = MetricSnapshotService(db)
    snap = svc.compute_for_app(app)
    db.commit()
    return {"status": "computed", "snapshot_at": snap.snapshot_at.isoformat()}


# ===========================================================================
# Growth Intelligence: Ad Intelligence
# ===========================================================================

@router.get("/apps/{app_id}/ads", response_model=AppAdIntelligenceResponse)
def get_app_ad_intelligence(
    app_id: int,
    db: Session = Depends(get_db),
):
    """Full ad intelligence for a single app: campaigns + creatives."""
    from app.services.ad_intelligence_service import AdIntelligenceService

    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    svc = AdIntelligenceService(db)
    campaigns = svc.get_campaigns(app_id)
    creatives = svc.get_creatives(app_id)
    active_camps = [c for c in campaigns if c.status == "active"]
    active_crs = [c for c in creatives if c.is_active]
    networks = list({c.network for c in campaigns})

    return AppAdIntelligenceResponse(
        app_id=app_id,
        campaigns=campaigns,
        creatives=creatives,
        total_campaigns=len(campaigns),
        active_campaigns=len(active_camps),
        total_creatives=len(creatives),
        active_creatives=len(active_crs),
        has_active_campaign=len(active_camps) > 0,
        networks=networks,
    )


@router.post("/apps/{app_id}/ads/scan")
async def scan_app_ads(app_id: int, db: Session = Depends(get_db)):
    """Trigger on-demand ad intelligence scan for a single app."""
    import os
    from app.services.ad_intelligence_service import AdIntelligenceService

    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    meta_token = os.environ.get("FACEBOOK_ACCESS_TOKEN")
    svc = AdIntelligenceService(db, meta_access_token=meta_token)
    result = await asyncio.to_thread(lambda: svc.run_for_app(app_id))
    return {"status": "scanned", **result}


@router.get("/ads", response_model=AdIntelligenceListResponse)
def get_ad_intelligence_list(
    network: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Global listing of apps with detected ad activity.
    Filterable by network and active status.
    """
    q = (
        db.query(models.AdCampaign, models.App)
        .join(models.App, models.App.id == models.AdCampaign.app_id)
    )
    if active_only:
        q = q.filter(models.AdCampaign.status == "active")
    if network:
        q = q.filter(models.AdCampaign.network == network)

    total = q.distinct(models.AdCampaign.app_id).count()

    # Group by app: one summary row per app
    from sqlalchemy import func as sqlfunc
    rows = (
        db.query(
            models.App,
            sqlfunc.count(models.AdCampaign.id).label("campaign_count"),
            sqlfunc.max(models.AdCampaign.campaign_confidence).label("max_confidence"),
            sqlfunc.min(models.AdCampaign.first_seen_at).label("first_ad_seen"),
            sqlfunc.max(models.AdCampaign.last_seen_at).label("last_ad_seen"),
        )
        .join(models.AdCampaign, models.AdCampaign.app_id == models.App.id)
        .filter(models.AdCampaign.status == "active" if active_only else True)
        .group_by(models.App.id)
        .order_by(sqlfunc.max(models.AdCampaign.campaign_confidence).desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = []
    for app, camp_count, max_conf, first_seen, last_seen in rows:
        networks_for_app = [
            r[0] for r in db.query(models.AdCampaign.network)
            .filter(models.AdCampaign.app_id == app.id)
            .distinct()
            .all()
        ]
        active_cr_count = db.query(models.AdCreative).filter(
            models.AdCreative.app_id == app.id,
            models.AdCreative.is_active == True,
        ).count()

        items.append(AdIntelligenceListItem(
            app_id=app.app_id,
            app_db_id=app.id,
            name=app.name,
            icon_url=app.icon_url,
            primary_category=app.primary_category,
            current_rank=app.current_rank,
            networks=networks_for_app,
            active_campaigns=camp_count,
            active_creatives=active_cr_count,
            max_confidence=round(max_conf or 0, 2),
            first_ad_seen=first_seen,
            last_ad_seen=last_seen,
        ))

    active_count = db.query(models.AdCampaign).filter(
        models.AdCampaign.status == "active"
    ).distinct(models.AdCampaign.app_id).count()

    return AdIntelligenceListResponse(
        status="success" if items else "empty",
        items=items,
        total=total,
        active_count=active_count,
    )


# ===========================================================================
# Growth Intelligence: Campaign Tracking
# ===========================================================================

@router.get("/apps/{app_id}/growth-events", response_model=AppGrowthEventsResponse)
def get_app_growth_events(
    app_id: int,
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Growth signals / campaign events detected for a single app."""
    from app.services.campaign_tracking_service import CampaignTrackingService

    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    svc = CampaignTrackingService(db)
    events = svc.get_events(app_db_id=app_id, active_only=active_only, limit=100)
    latest = events[0] if events else None

    return AppGrowthEventsResponse(
        app_id=app_id,
        events=events,
        latest_event=latest,
        total=len(events),
    )


@router.post("/apps/{app_id}/growth-events/detect")
async def detect_app_growth(app_id: int, db: Session = Depends(get_db)):
    """On-demand campaign/growth signal detection for a single app."""
    from app.services.campaign_tracking_service import CampaignTrackingService

    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    svc = CampaignTrackingService(db)
    events = await asyncio.to_thread(lambda: svc.run_for_app(app_id))
    db.commit()
    return {"status": "detected", "events_created": len(events)}


@router.get("/campaigns", response_model=CampaignTrackingListResponse)
def get_campaigns(
    event_type: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
    min_confidence: float = Query(default=0.3, ge=0, le=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Global campaign / growth signal listing.
    Returns active growth events with app details and blowing-up score.
    """
    q = (
        db.query(models.GrowthEvent, models.App)
        .join(models.App, models.App.id == models.GrowthEvent.app_id)
    )
    if active_only:
        q = q.filter(models.GrowthEvent.active_status == True)
    if event_type:
        q = q.filter(models.GrowthEvent.event_type == event_type)
    q = q.filter(models.GrowthEvent.confidence >= min_confidence)

    total = q.count()
    rows = q.order_by(
        models.GrowthEvent.confidence.desc(),
        models.GrowthEvent.detected_at.desc(),
    ).offset(skip).limit(limit).all()

    # Count by type for summary
    from sqlalchemy import func as sqlfunc
    type_counts_rows = (
        db.query(models.GrowthEvent.event_type, sqlfunc.count(models.GrowthEvent.id))
        .filter(models.GrowthEvent.active_status == True)
        .group_by(models.GrowthEvent.event_type)
        .all()
    )
    by_type = {t: c for t, c in type_counts_rows}

    items = []
    for event, app in rows:
        bu = db.query(models.AppBlowingUpScore).filter(
            models.AppBlowingUpScore.app_id == app.id
        ).first()
        items.append(CampaignTrackingListItem(
            app_id=app.app_id,
            app_db_id=app.id,
            name=app.name,
            icon_url=app.icon_url,
            primary_category=app.primary_category,
            current_rank=app.current_rank,
            event_type=event.event_type,
            confidence=event.confidence,
            explanation=event.explanation,
            detected_at=event.detected_at,
            started_at_estimate=event.started_at_estimate,
            blowing_up_score=bu.blowing_up_score if bu else None,
        ))

    return CampaignTrackingListResponse(
        status="success" if items else "empty",
        items=items,
        total=total,
        by_type=by_type,
    )
