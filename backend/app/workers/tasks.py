import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import App, Category, Ranking, Keyword, AppKeyword, Review, AppVersion
from app.scrapers.appstore import AppStoreScraper
from app.scrapers.app_details import AppStoreAppScraper
from app.scoring.engine import ScoringEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _compute_freshness_score(release_date: Optional[datetime]) -> float:
    """Convert a release_date into a 0-100 freshness score.

    100 = released <30 days ago (very high priority)
     80 = released <60 days ago
     60 = released <90 days ago  (medium priority)
     40 = released <180 days ago
     20 = released <365 days ago
      0 = older than 1 year      (normal priority)
    """
    if not release_date:
        return 0.0
    now = datetime.utcnow()
    # Normalise to naive UTC for arithmetic
    rd = release_date.replace(tzinfo=None) if release_date.tzinfo else release_date
    age_days = (now - rd).days
    if age_days < 0:
        return 100.0
    if age_days < 30:
        return 100.0
    if age_days < 60:
        return 80.0
    if age_days < 90:
        return 60.0
    if age_days < 180:
        return 40.0
    if age_days < 365:
        return 20.0
    return 0.0


class ScraperWorker:
    def __init__(self):
        self.scraper = None
        self.app_scraper = None
        self.db: Session = None
    
    async def initialize(self):
        self.scraper = AppStoreScraper()
        self.app_scraper = AppStoreAppScraper()
        self.db = SessionLocal()
    
    async def cleanup(self):
        if self.scraper:
            await self.scraper.close()
        if self.db:
            self.db.close()
    
    def get_or_create_category(self, name: str, slug: str) -> Category:
        category = self.db.query(Category).filter(Category.slug == slug).first()
        if not category:
            category = Category(name=name, slug=slug)
            self.db.add(category)
            self.db.commit()
            self.db.refresh(category)
        return category
    
    def get_or_create_app(self, app_data: dict) -> App:
        app = self.db.query(App).filter(App.app_id == app_data["app_id"]).first()
        
        if not app:
            app = App(
                app_id=app_data["app_id"],
                name=app_data.get("name", "Unknown"),
                developer=app_data.get("developer"),
                icon_url=app_data.get("icon_url"),
                current_rating=app_data.get("rating"),
                current_rank=app_data.get("rank")
            )
            self.db.add(app)
        else:
            app.name = app_data.get("name", app.name)
            app.developer = app_data.get("developer", app.developer)
            app.icon_url = app_data.get("icon_url", app.icon_url)
            app.current_rank = app_data.get("rank", app.current_rank)
        
        self.db.commit()
        self.db.refresh(app)
        return app
    
    def save_rankings(self, app: App, rankings_data: List[dict], chart_type: str):
        for rank_data in rankings_data:
            app = self.get_or_create_app(rank_data)
            
            previous_rank = rank_data.get("previous_rank")
            rank_velocity = 0
            if previous_rank and rank_data.get("rank"):
                rank_velocity = previous_rank - rank_data["rank"]
            
            ranking = Ranking(
                app_id=app.id,
                chart_type=chart_type,
                rank=rank_data.get("rank", 0),
                previous_rank=previous_rank,
                rank_velocity=rank_velocity
            )
            self.db.add(ranking)
        
        self.db.commit()
    
    async def scrape_search_results(self, keywords: List[str]):
        logger.info(f"Starting search results scrape for {len(keywords)} keywords (uncapped)")

        for keyword in keywords:
            try:
                results = await self.scraper.get_search_results(keyword, limit=200)
                logger.info(f"Found {len(results)} results for '{keyword}'")

                for i, result in enumerate(results):
                    app = self.get_or_create_app(result)
                    
                    existing_keyword = self.db.query(Keyword).filter(
                        Keyword.term == keyword
                    ).first()
                    if not existing_keyword:
                        existing_keyword = Keyword(term=keyword)
                        self.db.add(existing_keyword)
                        self.db.commit()
                        self.db.refresh(existing_keyword)
                    
                    app_keyword = self.db.query(AppKeyword).filter(
                        AppKeyword.app_id == app.id,
                        AppKeyword.keyword_id == existing_keyword.id
                    ).first()
                    
                    if not app_keyword:
                        app_keyword = AppKeyword(
                            app_id=app.id,
                            keyword_id=existing_keyword.id,
                            position=i + 1,
                            relevance=1.0 - (i * 0.02)
                        )
                        self.db.add(app_keyword)
                
                self.db.commit()
                
            except Exception as e:
                logger.error(f"Error scraping keyword '{keyword}': {e}")
        
        logger.info("Search results scrape completed")
    
    async def scrape_top_charts(self, chart_types: List[str] = None, categories: List[str] = None):
        if chart_types is None:
            chart_types = ["topfree", "toppaid", "topgrossing"]

        if categories is None:
            categories = [None]  # None → "all" genres in the RSS API

        logger.info(f"Starting top charts scrape: {len(chart_types)} chart types (uncapped)")

        for chart_type in chart_types:
            for category in categories:
                try:
                    results = await self.scraper.get_top_charts(chart_type, category, limit=200)
                    logger.info(f"Found {len(results)} apps in {chart_type}/{category or 'all'}")

                    new_apps_added = 0
                    for result in results:
                        existing_app = self.db.query(App).filter(
                            App.app_id == result["app_id"]
                        ).first()

                        if existing_app is None:
                            app = self.get_or_create_app(result)
                            new_apps_added += 1
                        else:
                            # Always update rank for existing apps
                            existing_app.current_rank = result.get("rank", existing_app.current_rank)
                            app = existing_app

                        # Resolve category from the RSS result and link to App
                        category_id = None
                        cat_name = result.get("category_name")
                        if cat_name:
                            cat_slug = cat_name.lower().replace(" & ", "-").replace(" ", "-")
                            cat_obj = self.get_or_create_category(cat_name, cat_slug)
                            category_id = cat_obj.id
                            if app.category_id is None:
                                app.category_id = category_id

                        previous_rank = None
                        existing_ranking = self.db.query(Ranking).filter(
                            Ranking.app_id == app.id,
                            Ranking.chart_type == chart_type,
                            Ranking.category_id == category_id,
                        ).order_by(Ranking.recorded_at.desc()).first()

                        if existing_ranking:
                            previous_rank = existing_ranking.rank

                        ranking = Ranking(
                            app_id=app.id,
                            chart_type=chart_type,
                            category_id=category_id,
                            rank=result.get("rank", 0),
                            previous_rank=previous_rank,
                            rank_velocity=(previous_rank - result.get("rank", 0)) if previous_rank else 0
                        )
                        self.db.add(ranking)

                    self.db.commit()
                    logger.info(
                        f"Chart {chart_type}/{category or 'all'}: "
                        f"{len(results)} ranks stored, {new_apps_added} new apps added"
                    )

                except Exception as e:
                    logger.error(f"Error scraping chart {chart_type}/{category}: {e}")

        logger.info("Top charts scrape completed")
    
    async def scrape_app_full_details(self, app_id: str, country: str = "us"):
        logger.info(f"Scraping full details for app {app_id}")
        
        try:
            result = await self.app_scraper.scrape_full_app_data(app_id, country)
            
            if not result or not result.get("app_details"):
                logger.warning(f"No details found for app {app_id}")
                return False
            
            details = result["app_details"]
            
            app = self.db.query(App).filter(App.app_id == app_id).first()
            if not app:
                app = App(app_id=app_id)
                self.db.add(app)
            
            app.name = details.get("name", app.name)
            app.subtitle = details.get("subtitle")
            app.description = details.get("description")
            app.developer = details.get("developer", app.developer)
            app.developer_id = details.get("developer_id")
            app.icon_url = details.get("icon_url", app.icon_url)
            app.screenshots = details.get("screenshots")
            app.primary_category = details.get("primary_category")
            app.secondary_category = details.get("secondary_category")
            app.is_free = details.get("is_free", True)
            app.price = details.get("price", 0)
            app.currency = details.get("currency", "USD")
            iap = details.get("in_app_purchases")
            app.in_app_purchases = (iap if isinstance(iap, bool) else bool(iap)) if iap not in (None, "", "[]") else False
            app.current_version = details.get("current_version")
            app.minimum_ios_version = details.get("minimum_ios_version")
            app.supported_languages = details.get("supported_languages")
            app.content_rating = details.get("content_rating")
            app.current_rating = details.get("current_rating", app.current_rating)
            app.current_reviews = details.get("current_reviews", app.current_reviews or 0)
            app.url = details.get("url", app.url)
            
            if details.get("release_date"):
                app.release_date = details.get("release_date")
            if details.get("last_updated"):
                app.last_updated = details.get("last_updated")

            # Freshness score — recomputed on every full scrape
            app.freshness_score = _compute_freshness_score(app.release_date)

            self.db.commit()
            self.db.refresh(app)
            
            versions_to_save = result.get("versions", [])
            if versions_to_save:
                # Reset is_latest for all existing versions of this app before
                # applying the freshly-scraped is_latest flags.
                self.db.query(AppVersion).filter(
                    AppVersion.app_id == app.id
                ).update({"is_latest": False})
                self.db.commit()

            saved_versions = 0
            for version_data in versions_to_save:
                existing = self.db.query(AppVersion).filter(
                    AppVersion.app_id == app.id,
                    AppVersion.version == version_data.get("version")
                ).first()

                if existing:
                    # Update is_latest on already-known versions
                    existing.is_latest = version_data.get("is_latest", False)
                else:
                    version = AppVersion(
                        app_id=app.id,
                        version=version_data.get("version"),
                        release_date=version_data.get("release_date"),
                        release_notes=version_data.get("release_notes"),
                        is_latest=version_data.get("is_latest", False)
                    )
                    self.db.add(version)
                    saved_versions += 1

            if versions_to_save:
                self.db.commit()
            
            saved_reviews = 0
            for review_data in result.get("reviews", []):
                existing = self.db.query(Review).filter(
                    Review.review_id == review_data.get("review_id")
                ).first()
                
                if not existing:
                    review = Review(
                        app_id=app.id,
                        review_id=review_data.get("review_id"),
                        user_name=review_data.get("user_name"),
                        user_url=review_data.get("user_url"),
                        rating=review_data.get("rating"),
                        title=review_data.get("title"),
                        content=review_data.get("content"),
                        date=review_data.get("date"),
                        app_version=review_data.get("app_version"),
                        storefront=review_data.get("storefront"),
                        developer_reply_text=review_data.get("developer_reply_text"),
                        developer_reply_date=review_data.get("developer_reply_date"),
                        helpful_count=review_data.get("helpful_count", 0)
                    )
                    self.db.add(review)
                    saved_reviews += 1
            
            if saved_reviews > 0:
                self.db.commit()
            
            logger.info(f"Saved {saved_versions} versions and {saved_reviews} reviews for app {app_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error scraping full details for app {app_id}: {e}")
            self.db.rollback()
            return False
    
    async def scrape_quick_refresh_all(self) -> int:
        """
        Lightweight hourly refresh for all tracked apps.

        For each app:
        - Fetches current metadata via iTunes Lookup API (rating, review count,
          current version, icon, last-updated date).
        - Fetches up to 50 most-recent reviews and saves any that are new.

        Intentionally skips version history HTML scraping (that is the
        responsibility of the heavier scrape_all_tracked_apps() job).
        """
        logger.info("Starting quick refresh for all tracked apps (uncapped)")
        # Fresh apps first — they benefit most from frequent updates
        apps = (
            self.db.query(App)
            .order_by(App.freshness_score.desc().nullslast(), App.created_at.desc())
            .all()
        )
        logger.info(f"Quick refresh: {len(apps)} apps to process")

        success_count = 0
        for app in apps:
            try:
                # --- 1. Update ratings / version / icon via iTunes API ---
                details = await self.app_scraper.get_app_details(app.app_id)
                if details:
                    app.current_rating = details.get("current_rating", app.current_rating)
                    app.current_reviews = details.get("current_reviews", app.current_reviews or 0)
                    app.current_version = details.get("current_version", app.current_version)
                    if details.get("last_updated"):
                        app.last_updated = details["last_updated"]
                    if details.get("icon_url"):
                        app.icon_url = details["icon_url"]
                    self.db.commit()

                # --- 2. Save new reviews ---
                reviews = await self.app_scraper.get_app_reviews(app.app_id, limit=50)
                saved_reviews = 0
                for review_data in reviews:
                    existing = self.db.query(Review).filter(
                        Review.review_id == review_data.get("review_id")
                    ).first()
                    if not existing:
                        review = Review(
                            app_id=app.id,
                            review_id=review_data.get("review_id"),
                            user_name=review_data.get("user_name"),
                            user_url=review_data.get("user_url"),
                            rating=review_data.get("rating"),
                            title=review_data.get("title"),
                            content=review_data.get("content"),
                            date=review_data.get("date"),
                            app_version=review_data.get("app_version"),
                            storefront=review_data.get("storefront"),
                            developer_reply_text=review_data.get("developer_reply_text"),
                            developer_reply_date=review_data.get("developer_reply_date"),
                            helpful_count=review_data.get("helpful_count", 0),
                        )
                        self.db.add(review)
                        saved_reviews += 1

                if saved_reviews > 0:
                    self.db.commit()

                rating_val = details.get("current_rating") if details else "n/a"
                logger.info(
                    f"Quick refresh OK  app={app.app_id}  "
                    f"rating={rating_val}  +{saved_reviews} new reviews"
                )
                success_count += 1

            except Exception as e:
                logger.error(f"Quick refresh failed for app {app.app_id}: {e}")
                try:
                    self.db.rollback()
                except Exception:
                    pass

        logger.info(f"Quick refresh complete: {success_count}/{len(apps)} apps")
        return success_count

    async def scrape_all_tracked_apps(self):
        logger.info("Starting scrape for all tracked apps (uncapped)")

        # Process fresh apps (high freshness_score) before older ones
        apps = (
            self.db.query(App)
            .order_by(App.freshness_score.desc().nullslast(), App.created_at.desc())
            .all()
        )
        app_ids = [app.app_id for app in apps]

        logger.info(f"Found {len(app_ids)} tracked apps to scrape")
        
        success_count = 0
        for app_id in app_ids:
            try:
                success = await self.scrape_app_full_details(app_id)
                if success:
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to scrape app {app_id}: {e}")
        
        logger.info(f"Scraped {success_count}/{len(app_ids)} apps successfully")
        return success_count


class ScoringWorker:
    def __init__(self):
        self.db: Session = None
    
    def initialize(self):
        self.db = SessionLocal()
    
    def cleanup(self):
        if self.db:
            self.db.close()
    
    def update_opportunities(self):
        logger.info("Updating opportunity scores")

        # Remove junk / test keywords that have no apps linked to them
        stale = (
            self.db.query(Keyword)
            .outerjoin(AppKeyword, AppKeyword.keyword_id == Keyword.id)
            .filter(AppKeyword.id.is_(None))
            .all()
        )
        for kw in stale:
            logger.info(f"Removing stale keyword: '{kw.term}'")
            self.db.delete(kw)
        if stale:
            self.db.commit()

        engine = ScoringEngine(self.db)

        # Populate search_volume / difficulty / trend estimates from app data
        logger.info("Updating keyword metrics from app data")
        engine.update_keyword_metrics()
        
        # Process fresh apps first — new apps need opportunity scores quickly
        apps = (
            self.db.query(App)
            .filter(App.current_rank.isnot(None))
            .order_by(App.freshness_score.desc().nullslast(), App.current_rank.asc())
            .limit(200)
            .all()
        )
        
        for app in apps:
            keywords = self.db.query(AppKeyword).join(Keyword).filter(
                AppKeyword.app_id == app.id
            ).limit(5).all()
            
            if not keywords:
                continue
            
            for app_kw in keywords:
                result = engine.score_opportunity(app.id, app_kw.keyword.term)
                
                if result:
                    from app.models.models import Opportunity
                    
                    existing = self.db.query(Opportunity).filter(
                        Opportunity.app_id == app.id,
                        Opportunity.primary_keyword == app_kw.keyword.term
                    ).first()
                    
                    if existing:
                        existing.competition_score = result["competition_score"]
                        existing.trend_score = result["trend_score"]
                        existing.success_probability = result["success_probability"]
                        existing.ai_integration_potential = result["ai_integration_potential"]
                        existing.recommendation = result["recommendation"]
                    else:
                        opportunity = Opportunity(
                            app_id=app.id,
                            opportunity_type="keyword",
                            primary_keyword=app_kw.keyword.term,
                            competition_score=result["competition_score"],
                            trend_score=result["trend_score"],
                            success_probability=result["success_probability"],
                            ai_integration_potential=result["ai_integration_potential"],
                            recommendation=result["recommendation"]
                        )
                        self.db.add(opportunity)
        
        self.db.commit()
        logger.info("Opportunity scores updated")

        # Compute market weakness (per-country negative review ratio) for all apps with reviews
        logger.info("Computing market weakness stats")
        apps_with_reviews = (
            self.db.query(App)
            .join(Review, Review.app_id == App.id)
            .distinct()
            .all()
        )
        for app in apps_with_reviews:
            try:
                engine.compute_market_weakness(app.id)
            except Exception as e:
                logger.error(f"Market weakness computation failed for app {app.id}: {e}")
        logger.info(f"Market weakness computed for {len(apps_with_reviews)} apps")

        # Compute feature gap analysis for all apps with negative reviews
        logger.info("Computing feature gap analysis")
        from app.scoring.feature_gaps import FeatureGapAnalyzer
        fg_analyzer = FeatureGapAnalyzer(self.db)
        apps_with_neg_reviews = (
            self.db.query(App)
            .join(Review, Review.app_id == App.id)
            .filter(Review.rating <= 3, Review.content.isnot(None))
            .distinct()
            .all()
        )
        fg_count = 0
        for app in apps_with_neg_reviews:
            try:
                gaps = fg_analyzer.compute_for_app(app.id)
                if gaps:
                    fg_count += 1
            except Exception as e:
                logger.error(f"Feature gap analysis failed for app {app.id}: {e}")
        logger.info(f"Feature gaps computed for {fg_count} apps")

        # Generate AI app ideas from aggregated signals
        logger.info("Generating AI app ideas")
        try:
            from app.scoring.idea_generator import IdeaGenerator
            idea_gen = IdeaGenerator(self.db)
            count = idea_gen.generate_all()
            logger.info(f"Generated/updated {count} app ideas")
        except Exception as e:
            logger.error(f"Idea generation failed: {e}")

        # Compute install + revenue estimates for all apps
        logger.info("Computing install estimates")
        try:
            from app.services.install_estimator import InstallEstimator
            inst_est = InstallEstimator(self.db)
            inst_count = inst_est.compute_all()
            logger.info(f"Install estimates updated for {inst_count} apps")
        except Exception as e:
            logger.error(f"Install estimation failed: {e}")

        logger.info("Computing revenue estimates")
        try:
            from app.services.revenue_estimator import RevenueEstimator
            rev_est = RevenueEstimator(self.db)
            rev_count = rev_est.compute_all()
            logger.info(f"Revenue estimates updated for {rev_count} apps")
        except Exception as e:
            logger.error(f"Revenue estimation failed: {e}")

    def generate_daily_report(self):
        logger.info("Generating daily report")
        
        engine = ScoringEngine(self.db)
        
        trending = engine.get_top_trending_apps(10)
        
        opportunity_of_day = engine.generate_opportunity_of_day()
        
        from app.models.models import DailyReport
        
        today = datetime.utcnow().date()
        existing = self.db.query(DailyReport).filter(
            DailyReport.date >= today
        ).first()
        
        if existing:
            existing.top_trending_apps = trending
            existing.opportunity_of_day = opportunity_of_day
        else:
            report = DailyReport(
                date=datetime.utcnow(),
                top_trending_apps=trending,
                opportunity_of_day=opportunity_of_day
            )
            self.db.add(report)
        
        self.db.commit()
        logger.info("Daily report generated")


async def run_scrape_task():
    """
    Full pipeline:
    1. Keyword discovery  → discover apps via 100+ keywords (via DiscoveryEngine)
    2. Chart discovery    → top charts all categories (via DiscoveryEngine)
    3. Queue processing   → scrape full details for every queued app
    4. Full refresh       → update details for already-tracked apps

    Falls back to legacy direct scrape if DiscoveryEngine is unavailable.
    """
    from app.workers.discovery_engine import DISCOVERY_KEYWORDS
    from app.database import SessionLocal

    worker = ScraperWorker()
    await worker.initialize()

    try:
        # --- Phase 1: keyword search (legacy path keeps existing apps updated) ---
        seed_keywords = [
            "productivity", "ai", "chat", "fitness", "finance",
            "education", "game", "health", "travel", "music",
            "budget", "meditation", "recipe", "weather", "news",
        ]
        logger.info(f"Phase 1: keyword search for {len(seed_keywords)} seed keywords")
        await worker.scrape_search_results(seed_keywords)

        # --- Phase 2: top charts across all genres (best-effort) ---
        logger.info("Phase 2: top charts across all chart types")
        try:
            await worker.scrape_top_charts(
                chart_types=["topfree", "toppaid", "topgrossing"],
                categories=None,   # None = all-genres; per-category handled by discovery engine
            )
        except Exception as e:
            logger.warning(f"Top charts scrape failed, skipping: {e}")

        # --- Phase 3: process discovery queue (if any items queued by engine) ---
        logger.info("Phase 3: processing discovery queue")
        try:
            db = SessionLocal()
            from app.workers.discovery_engine import DiscoveryEngine
            engine = DiscoveryEngine(db)
            await engine.process_queue(batch_size=50)
            db.close()
        except Exception as e:
            logger.warning(f"Discovery queue processing failed: {e}")

        # --- Phase 4: full details for all tracked apps ---
        logger.info("Phase 4: full details refresh for all tracked apps")
        success_count = await worker.scrape_all_tracked_apps()
        logger.info(f"Pipeline complete — {success_count} apps fully scraped")

    finally:
        await worker.cleanup()


def run_scoring_task():
    worker = ScoringWorker()
    worker.initialize()
    
    try:
        worker.update_opportunities()
        worker.generate_daily_report()
    finally:
        worker.cleanup()


if __name__ == "__main__":
    asyncio.run(run_scrape_task())
