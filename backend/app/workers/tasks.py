import asyncio
import logging
import time as _time
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import App, Category, Ranking, Keyword, KeywordStatus, AppKeyword, Review, AppVersion
from app.scrapers.appstore import AppStoreScraper
from app.scrapers.app_details import AppStoreAppScraper
from app.scoring.engine import ScoringEngine
from app.utils.batch_utils import iter_batches, iter_batches_keyset, log_memory

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
                current_rank=app_data.get("rank"),
                ingestion_stage="light",
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
        from app.services.global_keyword_sink import GlobalKeywordSink

        logger.info(f"Starting search results scrape for {len(keywords)} keywords (uncapped)")

        sink = GlobalKeywordSink(self.db)
        processed_keywords = set()

        for keyword in keywords:
            try:
                results = await self.scraper.get_search_results(keyword, limit=200)
                logger.info(f"Found {len(results)} results for '{keyword}'")

                if keyword not in processed_keywords:
                    sink.push(keywords=[keyword], source="search_scrape", discovered_from=None)
                    processed_keywords.add(keyword)

                existing_keyword = self.db.query(Keyword).filter(
                    Keyword.term == keyword
                ).first()

                if not existing_keyword:
                    continue

                for i, result in enumerate(results):
                    app = self.get_or_create_app(result)

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
                self.db.rollback()
                logger.error(f"Error scraping keyword '{keyword}': {e}")

        logger.info("Search results scrape completed")
    
    async def scrape_top_charts(self, chart_types: List[str] = None, categories: List[str] = None, country: str = "us"):
        if chart_types is None:
            chart_types = ["topfree", "toppaid", "topgrossing"]

        if categories is None:
            categories = [None]  # None → "all" genres in the RSS API

        cc = (country or "us").lower()
        logger.info(f"Starting top charts scrape [{cc}]: {len(chart_types)} chart types (uncapped)")

        for chart_type in chart_types:
            for category in categories:
                # Chart scope: 'all' (overall) or a genre slug. This is the axis
                # the rank is measured on — distinct from an app's own category.
                chart_genre = (
                    category.lower().replace(" & ", "-").replace(" ", "-")
                    if category else "all"
                )
                try:
                    results = await self.scraper.get_top_charts(chart_type, category, limit=200, country=cc)
                    logger.info(f"Found {len(results)} apps in {cc}/{chart_type}/{chart_genre}")

                    new_apps_added = 0
                    for result in results:
                        existing_app = self.db.query(App).filter(
                            App.app_id == result["app_id"]
                        ).first()

                        if existing_app is None:
                            app = self.get_or_create_app(result)
                            new_apps_added += 1
                        else:
                            # current_rank is the global (US) headline rank — only
                            # update it from the US storefront to avoid per-country drift.
                            if cc == "us":
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
                            Ranking.country == cc,
                            Ranking.genre == chart_genre,
                        ).order_by(Ranking.recorded_at.desc()).first()

                        if existing_ranking:
                            previous_rank = existing_ranking.rank

                        ranking = Ranking(
                            app_id=app.id,
                            chart_type=chart_type,
                            category_id=category_id,   # the app's own category (metadata)
                            country=cc,
                            genre=chart_genre,          # the chart's scope
                            rank=result.get("rank", 0),
                            previous_rank=previous_rank,
                            rank_velocity=(previous_rank - result.get("rank", 0)) if previous_rank else 0
                        )
                        self.db.add(ranking)

                    self.db.commit()
                    logger.info(
                        f"Chart {cc}/{chart_type}/{chart_genre}: "
                        f"{len(results)} ranks stored, {new_apps_added} new apps added"
                    )

                except Exception as e:
                    self.db.rollback()
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
            # Mark as fully enriched
            app.ingestion_stage = "full"
            app.last_enriched_at = datetime.now(timezone.utc)

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
    
    async def scrape_light_details(self, app_id: str, country: str = "us") -> bool:
        """
        Fetch a single iTunes Lookup API call for `app_id` and persist the
        partial metadata to the apps table.  This is the 'light' enrichment
        path — 1 HTTP call vs 3 for a full scrape.

        - Does NOT overwrite ingestion_stage if the row already has 'full'.
        - Does NOT scrape version history HTML or reviews.
        - Sets ingestion_stage='light' only if the row was 'light' already (or new).
        - Creates a minimal row if the app doesn't exist yet.

        Returns True on success, False on failure.
        """
        logger.debug(f"[LIGHT] Scraping light details for app {app_id}")
        try:
            details = await self.app_scraper.get_app_details(app_id, country)
            if not details:
                logger.warning(f"[LIGHT] No details returned for app {app_id}")
                return False

            app = self.db.query(App).filter(App.app_id == app_id).first()
            if not app:
                app = App(app_id=app_id, ingestion_stage="light")
                self.db.add(app)

            # Update partial fields from iTunes Lookup
            app.name = details.get("name") or app.name or "Unknown"
            app.developer = details.get("developer") or app.developer
            app.developer_id = details.get("developer_id") or app.developer_id
            app.icon_url = details.get("icon_url") or app.icon_url
            app.primary_category = details.get("primary_category") or app.primary_category
            app.is_free = details.get("is_free", app.is_free if app.is_free is not None else True)
            app.price = details.get("price", app.price or 0.0)
            app.current_rating = details.get("current_rating") or app.current_rating
            app.current_reviews = details.get("current_reviews") or app.current_reviews or 0
            app.current_version = details.get("current_version") or app.current_version
            app.url = details.get("url") or app.url

            if details.get("release_date"):
                app.release_date = details["release_date"]
            if details.get("last_updated"):
                app.last_updated = details["last_updated"]

            # Recompute freshness
            app.freshness_score = _compute_freshness_score(app.release_date)

            # Only set light stage if not already fully enriched
            if app.ingestion_stage != "full":
                app.ingestion_stage = "light"

            self.db.commit()
            return True

        except Exception as exc:
            logger.error(f"[LIGHT] scrape_light_details failed for {app_id}: {exc}")
            self.db.rollback()
            return False

    async def scrape_quick_refresh_all(self, max_wall_time: float = None) -> int:
        """
        Lightweight hourly refresh for all tracked apps — runs concurrently.

        For each app:
        - Fetches current metadata via iTunes Lookup API (rating, review count,
          current version, icon, last-updated date).
        - Fetches up to 50 most-recent reviews and saves any that are new.

        Concurrency: asyncio.Semaphore(15) — max 15 apps in-flight at once.
        Isolation: each task opens its own DB session so failures don't bleed.
        Timeout: 60 s per app; timed-out apps are logged and counted as failures.
        max_wall_time: if set, stop processing new batches after this many
        seconds of total elapsed time (apps are sorted by priority, so the
        most important ones are always refreshed first).
        """
        _CONCURRENCY = 5   # was 15 — each spawns a SessionLocal, pool max=30
        _TIMEOUT = 60.0    # seconds per app
        _SEM = asyncio.Semaphore(_CONCURRENCY)

        log_memory("quick_refresh", "start")

        # Count total apps for logging
        total_apps = self.db.query(App.id).count()
        logger.info(
            f"Quick refresh: {total_apps} apps  "
            f"concurrency={_CONCURRENCY}  timeout={_TIMEOUT}s"
        )

        async def _refresh_one(db_id: int, app_store_id: str) -> bool:
            """Refresh a single app in an isolated session with timeout guard."""
            async with _SEM:
                db = SessionLocal()
                try:
                    async def _do() -> bool:
                        app = db.query(App).filter(App.id == db_id).first()
                        if not app:
                            return False

                        # --- 1. Update metadata via iTunes Lookup API ---
                        details = await self.app_scraper.get_app_details(app_store_id)
                        if details:
                            app.current_rating = details.get("current_rating", app.current_rating)
                            app.current_reviews = details.get("current_reviews", app.current_reviews or 0)
                            app.current_version = details.get("current_version", app.current_version)
                            if details.get("last_updated"):
                                app.last_updated = details["last_updated"]
                            if details.get("icon_url"):
                                app.icon_url = details["icon_url"]
                            db.commit()

                        # --- 2. Save new reviews ---
                        reviews = await self.app_scraper.get_app_reviews(app_store_id, limit=50)
                        new_reviews = 0
                        for rv in reviews:
                            exists = db.query(Review).filter(
                                Review.review_id == rv.get("review_id")
                            ).first()
                            if not exists:
                                db.add(Review(
                                    app_id=db_id,
                                    review_id=rv.get("review_id"),
                                    user_name=rv.get("user_name"),
                                    user_url=rv.get("user_url"),
                                    rating=rv.get("rating"),
                                    title=rv.get("title"),
                                    content=rv.get("content"),
                                    date=rv.get("date"),
                                    app_version=rv.get("app_version"),
                                    storefront=rv.get("storefront"),
                                    developer_reply_text=rv.get("developer_reply_text"),
                                    developer_reply_date=rv.get("developer_reply_date"),
                                    helpful_count=rv.get("helpful_count", 0),
                                ))
                                new_reviews += 1
                        if new_reviews:
                            db.commit()

                        rating = details.get("current_rating") if details else "n/a"
                        logger.info(
                            f"Quick refresh OK  app={app_store_id}  "
                            f"rating={rating}  +{new_reviews} new reviews"
                        )
                        return True

                    return await asyncio.wait_for(_do(), timeout=_TIMEOUT)

                except asyncio.TimeoutError:
                    logger.warning(
                        f"Quick refresh TIMEOUT  app={app_store_id}  (>{_TIMEOUT}s)"
                    )
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    return False
                except Exception as exc:
                    logger.error(f"Quick refresh FAILED  app={app_store_id}: {exc}")
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    return False
                finally:
                    db.close()

        # Process in batches of 200 to avoid creating 100K+ coroutines at once
        _BATCH_SIZE = 200
        success_count = 0
        total_processed = 0
        wall_start = _time.monotonic()
        base_query = (
            self.db.query(App.id, App.app_id)
            .order_by(App.freshness_score.desc().nullslast(), App.created_at.desc())
        )
        for batch in iter_batches(base_query, _BATCH_SIZE):
            if max_wall_time and (_time.monotonic() - wall_start) > max_wall_time:
                logger.warning(
                    f"Quick refresh: wall-time budget ({max_wall_time}s) exceeded "
                    f"after {total_processed}/{total_apps} apps — stopping early"
                )
                break
            results = await asyncio.gather(
                *[_refresh_one(db_id, sid) for db_id, sid in batch]
            )
            success_count += sum(1 for r in results if r)
            total_processed += len(batch)
            self.db.expire_all()

        failed_count = total_processed - success_count
        log_memory("quick_refresh", "end")
        logger.info(
            f"Quick refresh complete: {success_count}/{total_processed} OK  "
            f"{failed_count} failed/timed-out"
        )
        return success_count

    async def scrape_all_tracked_apps(self):
        logger.info("Starting scrape for all tracked apps (uncapped)")
        log_memory("scrape_all_tracked", "start")

        total_apps = self.db.query(App.id).count()
        logger.info(f"Found {total_apps} tracked apps to scrape")

        # Process in batches of 100 to bound memory usage
        _BATCH_SIZE = 100
        success_count = 0
        total_processed = 0
        base_query = (
            self.db.query(App.app_id)
            .order_by(App.freshness_score.desc().nullslast(), App.created_at.desc())
        )
        for batch in iter_batches(base_query, _BATCH_SIZE):
            app_ids = [row[0] for row in batch]
            for app_id in app_ids:
                try:
                    success = await self.scrape_app_full_details(app_id)
                    if success:
                        success_count += 1
                except Exception as e:
                    logger.error(f"Failed to scrape app {app_id}: {e}")
            total_processed += len(app_ids)
            # Release ORM identity map between batches
            self.db.expire_all()

        log_memory("scrape_all_tracked", "end")
        logger.info(f"Scraped {success_count}/{total_processed} apps successfully")
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
        log_memory("update_opportunities", "start")

        from sqlalchemy import text

        # Mark truly orphaned keywords as PRUNED using raw SQL (no ORM load)
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        try:
            result = self.db.execute(text("""
                UPDATE keywords SET status = 'pruned'
                WHERE id IN (
                    SELECT k.id FROM keywords k
                    LEFT JOIN app_keywords ak ON ak.keyword_id = k.id
                    WHERE ak.id IS NULL
                      AND k.last_enriched IS NULL
                      AND k.last_updated < :cutoff
                      AND k.status != 'enriched'
                )
            """), {"cutoff": cutoff_24h})
            if result.rowcount:
                logger.info(f"Marked {result.rowcount} orphaned keywords as PRUNED")
            self.db.commit()
        except Exception as e:
            logger.error(f"Keyword pruning mark failed: {e}")
            self.db.rollback()

        # Delete keywords that were previously marked PRUNED
        try:
            result = self.db.execute(text("DELETE FROM keywords WHERE status = 'pruned'"))
            if result.rowcount:
                logger.info(f"Deleted {result.rowcount} PRUNED keywords")
            self.db.commit()
        except Exception as e:
            logger.error(f"Keyword pruning delete failed: {e}")
            self.db.rollback()

        self.db.expire_all()

        engine = ScoringEngine(self.db)

        # Populate search_volume / difficulty / trend estimates from app data
        logger.info("Updating keyword metrics from app data")
        engine.update_keyword_metrics()
        self.db.expire_all()

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
        self.db.expire_all()
        logger.info("Opportunity scores updated")

        # Compute market weakness — paginated by app ID instead of loading all
        logger.info("Computing market weakness stats")
        _BATCH = 100
        mw_count = 0
        mw_query = (
            self.db.query(App.id)
            .join(Review, Review.app_id == App.id)
            .distinct()
            .order_by(App.id)
        )
        for batch in iter_batches(mw_query, _BATCH):
            for (app_id,) in batch:
                try:
                    engine.compute_market_weakness(app_id)
                    mw_count += 1
                except Exception as e:
                    self.db.rollback()
                    logger.error(f"Market weakness computation failed for app {app_id}: {e}")
            self.db.commit()
            self.db.expire_all()
        logger.info(f"Market weakness computed for {mw_count} apps")

        # Compute feature gap analysis — paginated
        logger.info("Computing feature gap analysis")
        from app.scoring.feature_gaps import FeatureGapAnalyzer
        fg_analyzer = FeatureGapAnalyzer(self.db)
        fg_count = 0
        fg_query = (
            self.db.query(App.id)
            .join(Review, Review.app_id == App.id)
            .filter(Review.rating <= 3, Review.content.isnot(None))
            .distinct()
            .order_by(App.id)
        )
        for batch in iter_batches(fg_query, _BATCH):
            for (app_id,) in batch:
                try:
                    gaps = fg_analyzer.compute_for_app(app_id)
                    if gaps:
                        fg_count += 1
                except Exception as e:
                    self.db.rollback()
                    logger.error(f"Feature gap analysis failed for app {app_id}: {e}")
            self.db.commit()
            self.db.expire_all()
        logger.info(f"Feature gaps computed for {fg_count} apps")

        # Recompute keyword opportunity + feasibility scores in batches
        logger.info("Recomputing keyword intelligence scores")
        try:
            from app.services.keyword_intelligence_pipeline import KeywordIntelligencePipeline
            kw_pipeline = KeywordIntelligencePipeline(self.db)
            scored_total = 0
            kw_query = self.db.query(Keyword)
            for batch in iter_batches_keyset(kw_query, Keyword.id, 500):
                scored_total += kw_pipeline.recompute_scores(batch)
                self.db.expire_all()
            logger.info(f"Keyword scores updated for {scored_total} keywords")
        except Exception as e:
            logger.error(f"Keyword score recompute failed: {e}")

        # Generate AI app ideas from aggregated signals
        logger.info("Generating AI app ideas")
        try:
            from app.scoring.idea_generator import IdeaGenerator
            idea_gen = IdeaGenerator(self.db)
            count = idea_gen.generate_all()
            logger.info(f"Generated/updated {count} app ideas")
        except Exception as e:
            logger.error(f"Idea generation failed: {e}")

        # Compute metric snapshots (download + revenue estimates in one coordinated pass)
        logger.info("Computing metric snapshots (downloads + revenue)")
        try:
            from app.services.metric_snapshot_service import MetricSnapshotService
            snap_svc = MetricSnapshotService(self.db)
            snap_count = snap_svc.compute_all()
            logger.info(f"Metric snapshots written for {snap_count} apps")
        except Exception as e:
            logger.error(f"Metric snapshot computation failed: {e}")

        log_memory("update_opportunities", "end")

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


def prune_keywords_job(db) -> dict:
    """
    Multi-rule keyword pruning job.  Deletes low-value, stale, and orphaned
    keywords from the global keywords table in a fixed rule order.

    Rules (executed sequentially):
      1  low_quality_stale  — quality_score < 30 AND last_seen_at stale > 14 days
      2  pruned_status      — status = 'pruned' (previously marked by enrichment)
      3  orphaned_weak      — quality_score < 45 AND no app links AND not enriched recently
      4  weak_alphabet      — alphabet source, quality_score < 50, times_seen < 2
      5  zero_signal_stale  — apps_count=0 AND search_volume=0 AND stale > 90 days
      6  tier_c_cap         — global cap: delete weakest Tier-C until count < 850k

    Returns a dict with per-rule deleted counts and totals.
    """
    from sqlalchemy import text

    stats = {
        "low_quality_stale": 0,
        "pruned_status": 0,
        "orphaned_weak": 0,
        "weak_alphabet": 0,
        "zero_signal_stale": 0,
        "tier_c_cap": 0,
        "total_deleted": 0,
        "remaining_keywords": 0,
    }

    # Rule 1 — low quality + stale (unseen > 14 days)
    try:
        r1 = db.execute(text("""
            DELETE FROM keywords
            WHERE quality_score < 30
              AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '14 days')
        """))
        stats["low_quality_stale"] = r1.rowcount or 0
        db.commit()
    except Exception as exc:
        logger.error(f"[Pruning] Rule 1 (low_quality_stale) failed: {exc}")
        try:
            db.rollback()
        except Exception:
            pass

    # Rule 2 — PRUNED status (existing 2-pass merge: delete immediately)
    try:
        r2 = db.execute(text(
            "DELETE FROM keywords WHERE status = 'pruned'"
        ))
        stats["pruned_status"] = r2.rowcount or 0
        db.commit()
    except Exception as exc:
        logger.error(f"[Pruning] Rule 2 (pruned_status) failed: {exc}")
        try:
            db.rollback()
        except Exception:
            pass

    # Rule 3 — orphaned weak: no app relations + weak + not recently enriched
    try:
        r3 = db.execute(text("""
            DELETE FROM keywords
            WHERE quality_score < 45
              AND NOT EXISTS (
                  SELECT 1 FROM app_keywords WHERE keyword_id = keywords.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM app_keyword_intelligence WHERE keyword_id = keywords.id
              )
              AND (last_enriched IS NULL OR last_enriched < NOW() - INTERVAL '30 days')
        """))
        stats["orphaned_weak"] = r3.rowcount or 0
        db.commit()
    except Exception as exc:
        logger.error(f"[Pruning] Rule 3 (orphaned_weak) failed: {exc}")
        try:
            db.rollback()
        except Exception:
            pass

    # Rule 4 — weak alphabet: low score + rarely seen
    try:
        r4 = db.execute(text("""
            DELETE FROM keywords
            WHERE keyword_source = 'alphabet'
              AND quality_score < 50
              AND COALESCE(times_seen, 1) < 2
        """))
        stats["weak_alphabet"] = r4.rowcount or 0
        db.commit()
    except Exception as exc:
        logger.error(f"[Pruning] Rule 4 (weak_alphabet) failed: {exc}")
        try:
            db.rollback()
        except Exception:
            pass

    # Rule 5 — zero signal stale: no Apple data, no volume, unseen > 90 days
    try:
        r5 = db.execute(text("""
            DELETE FROM keywords
            WHERE COALESCE(apps_count, 0) = 0
              AND COALESCE(search_volume, 0) = 0
              AND quality_score < 45
              AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '90 days')
        """))
        stats["zero_signal_stale"] = r5.rowcount or 0
        db.commit()
    except Exception as exc:
        logger.error(f"[Pruning] Rule 5 (zero_signal_stale) failed: {exc}")
        try:
            db.rollback()
        except Exception:
            pass

    # Rule 6 — global Tier-C cap
    try:
        from app.services.keyword_quality_engine import KeywordQualityEngine
        tier_c_deleted = KeywordQualityEngine.prune_tier_c_to_target(db)
        stats["tier_c_cap"] = tier_c_deleted
    except Exception as exc:
        logger.error(f"[Pruning] Rule 6 (tier_c_cap) failed: {exc}")

    # Final count
    try:
        remaining = db.execute(text("SELECT COUNT(*) FROM keywords")).scalar() or 0
        stats["remaining_keywords"] = remaining
    except Exception:
        pass

    stats["total_deleted"] = (
        stats["low_quality_stale"]
        + stats["pruned_status"]
        + stats["orphaned_weak"]
        + stats["weak_alphabet"]
        + stats["zero_signal_stale"]
        + stats["tier_c_cap"]
    )

    logger.info(
        f"[Pruning] low_quality_stale={stats['low_quality_stale']}, "
        f"pruned_status={stats['pruned_status']}, "
        f"orphaned_weak={stats['orphaned_weak']}, "
        f"weak_alphabet={stats['weak_alphabet']}, "
        f"zero_signal_stale={stats['zero_signal_stale']}, "
        f"tier_c_cap={stats['tier_c_cap']}, "
        f"total_deleted={stats['total_deleted']}, "
        f"remaining_keywords={stats['remaining_keywords']}"
    )
    return stats


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
            try:
                from app.workers.discovery_engine import DiscoveryEngine
                engine = DiscoveryEngine(db)
                await engine.process_queue(batch_size=50)
            finally:
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
