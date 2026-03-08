from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
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
    OpportunityOfDayResponse,
    KeywordOpportunityResponse,
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
)
from app.scoring.engine import ScoringEngine
from app.scoring.feature_gaps import FeatureGapAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_apps = db.query(func.count(models.App.id)).scalar() or 0
    total_keywords = db.query(func.count(models.Keyword.id)).scalar() or 0
    
    cutoff = datetime.utcnow() - timedelta(days=7)
    trending_count = db.query(func.count(func.distinct(models.Ranking.app_id))).filter(
        models.Ranking.recorded_at >= cutoff,
        models.Ranking.rank_velocity > 0
    ).scalar() or 0
    
    opportunities_count = db.query(func.count(models.Opportunity.id)).scalar() or 0
    
    return {
        "total_apps_tracked": total_apps,
        "total_keywords": total_keywords,
        "trending_apps_count": trending_count,
        "opportunities_count": opportunities_count
    }


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
    """
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

    # ── sorting ──────────────────────────────────────────────────────────
    sort_col = _VALID_SORT_FIELDS.get(sort_by or "", models.App.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc().nullslast())
    else:
        query = query.order_by(sort_col.desc().nullslast())

    total = query.count()
    apps = query.offset(skip).limit(limit).all()

    return {"apps": apps, "total": total, "skip": skip, "limit": limit}


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


@router.get("/trending", response_model=List[TrendingAppResponse])
def get_trending_apps(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    engine = ScoringEngine(db)
    trending = engine.get_top_trending_apps(limit)
    
    if not trending:
        apps = db.query(models.App).limit(limit).all()
        if apps:
            return [{
                "id": app.id,
                "app_id": app.app_id,
                "name": app.name,
                "developer": app.developer,
                "icon_url": app.icon_url,
                "current_rank": app.current_rank,
                "rank_velocity": 0.0,
                "review_growth": 0.0,
                "rating_velocity": 0.0,
                "trend_score": 0.0
            } for app in apps]
        return []
    
    return trending


@router.get("/opportunity-of-day", response_model=OpportunityOfDayResponse)
def get_opportunity_of_day(db: Session = Depends(get_db)):
    today = datetime.utcnow().date()
    
    report = db.query(models.DailyReport).filter(
        models.DailyReport.date >= today
    ).first()
    
    if report and report.opportunity_of_day:
        return report.opportunity_of_day
    
    engine = ScoringEngine(db)
    opportunity = engine.generate_opportunity_of_day()
    
    if not opportunity:
        app = db.query(models.App).first()
        if not app:
            return {
                "app_id": 0,
                "app_name": "No apps available",
                "primary_keyword": "N/A",
                "competition_score": 0.0,
                "trend_score": 0.0,
                "success_probability": 0.0,
                "ai_integration_potential": 0.0,
                "rank_velocity": 0.0,
                "review_growth": 0.0,
                "rating_velocity": 0.0,
                "category_growth": 0.0,
                "category": "general",
                "recommendation": "No opportunity data available. Add apps to generate opportunities."
            }
        return {
            "app_id": app.id,
            "app_name": app.name,
            "primary_keyword": app.name.split()[0].lower() if app.name else "app",
            "competition_score": 50.0,
            "trend_score": 0.0,
            "success_probability": 0.0,
            "ai_integration_potential": 30.0,
            "rank_velocity": 0.0,
            "review_growth": 0.0,
            "rating_velocity": 0.0,
            "category_growth": 0.0,
            "category": "general",
            "recommendation": "Not enough data to generate opportunity. Keep tracking apps."
        }
    
    return opportunity


@router.get("/keyword-opportunities", response_model=List[KeywordOpportunityResponse])
def get_keyword_opportunities(
    min_difficulty: float = Query(0, ge=0, le=100),
    max_difficulty: float = Query(60, ge=0, le=100),
    db: Session = Depends(get_db)
):
    engine = ScoringEngine(db)
    opportunities = engine.get_keyword_opportunities(min_difficulty, max_difficulty)
    
    if not opportunities:
        keywords = db.query(models.Keyword).limit(20).all()
        if keywords:
            return [{
                "keyword": kw.term,
                "search_volume": kw.search_volume or 0,
                "difficulty": kw.difficulty or 0,
                "trend": kw.trend or 0,
                "opportunity_score": 0.0,
                "current_apps": 0
            } for kw in keywords]
        return []
    
    return opportunities


@router.get("/keywords", response_model=List[KeywordResponse])
def get_keywords(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    return db.query(models.Keyword).offset(skip).limit(limit).all()


@router.post("/keywords", response_model=KeywordResponse)
def create_keyword(keyword: KeywordCreate, db: Session = Depends(get_db)):
    db_keyword = models.Keyword(**keyword.dict())
    db.add(db_keyword)
    db.commit()
    db.refresh(db_keyword)
    return db_keyword


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


@router.post("/scrape/all")
async def scrape_all_apps(db: Session = Depends(get_db)):
    from app.workers.tasks import ScraperWorker
    import asyncio
    
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
    import asyncio

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
    radar = NicheRadarEngine(db)
    niches = radar.scan(limit=limit)
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
