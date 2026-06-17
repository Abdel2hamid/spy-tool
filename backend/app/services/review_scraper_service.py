"""
Review Scraper Service
======================
Fetches up to 500 reviews per app from the iTunes RSS API and persists
new reviews to the database.

Usage (from async context):
    svc = ReviewScraperService(db)
    new_count = await svc.scrape_reviews_for_app(app_id=42, limit=500)
    stats    = await svc.scrape_reviews_for_top_apps(limit=300)
"""

import asyncio
import logging
from typing import Dict

from sqlalchemy.orm import Session

from app.models.models import App, Review

logger = logging.getLogger(__name__)

_CONCURRENT_APPS = 5    # max apps scraped simultaneously (was 20 — pool exhaustion)
_DEFAULT_LIMIT   = 500  # reviews per app


class ReviewScraperService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Single-app ingestion
    # ------------------------------------------------------------------

    async def scrape_reviews_for_app(
        self,
        app_id: int,
        limit: int = _DEFAULT_LIMIT,
        country: str = "us",
    ) -> int:
        """
        Fetch up to *limit* reviews for the app and upsert into DB.
        Returns number of *new* reviews saved.
        """
        from app.scrapers.app_details import AppStoreAppScraper

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app or not app.app_id:
            logger.warning(f"[ReviewScraper] app {app_id} not found or missing app_id")
            return 0

        scraper = AppStoreAppScraper()
        try:
            reviews_data = await scraper.get_app_reviews(
                app.app_id, country=country, limit=limit
            )
        except Exception as exc:
            logger.error(f"[ReviewScraper] Failed fetching reviews for app {app_id}: {exc}")
            return 0

        # Pre-fetch existing review_ids in one query (avoids N+1)
        candidate_ids = [str(rv.get("review_id")) for rv in reviews_data if rv.get("review_id")]
        existing_ids = set()
        if candidate_ids:
            existing_ids = {
                row[0] for row in
                self.db.query(Review.review_id)
                .filter(Review.review_id.in_(candidate_ids))
                .all()
            }

        new_count = 0
        for rv in reviews_data:
            review_id = rv.get("review_id")
            if not review_id:
                continue

            if str(review_id) in existing_ids:
                continue

            review = Review(
                app_id=app_id,
                review_id=str(review_id),
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
            )
            self.db.add(review)
            new_count += 1

        if new_count > 0:
            self.db.commit()
            logger.info(f"[ReviewScraper] app {app_id}: +{new_count} new reviews")
        return new_count

    # ------------------------------------------------------------------
    # Batch ingestion — top apps
    # ------------------------------------------------------------------

    async def scrape_reviews_for_top_apps(self, limit: int = 300) -> Dict:
        """
        Fetch reviews for the top *limit* ranked apps in parallel batches.
        Returns {"apps_processed": N, "new_reviews": M, "errors": K}.
        """
        from app.database import SessionLocal

        app_ids = [
            row[0]
            for row in (
                self.db.query(App.id)
                .filter(App.current_rank.isnot(None))
                .order_by(App.current_rank.asc(), App.current_reviews.desc())
                .limit(limit)
                .all()
            )
        ]

        semaphore = asyncio.Semaphore(_CONCURRENT_APPS)
        total_new = 0
        errors = 0

        async def _scrape_one(aid: int):
            nonlocal total_new, errors
            async with semaphore:
                db = SessionLocal()
                try:
                    svc = ReviewScraperService(db)
                    n = await svc.scrape_reviews_for_app(aid)
                    total_new += n
                except Exception as exc:
                    logger.warning(f"[ReviewScraper] app {aid} failed: {exc}")
                    errors += 1
                finally:
                    db.close()

        await asyncio.gather(*[_scrape_one(aid) for aid in app_ids])

        logger.info(
            f"[ReviewScraper] batch complete: {len(app_ids)} apps, "
            f"+{total_new} new reviews, {errors} errors"
        )
        return {
            "apps_processed": len(app_ids),
            "new_reviews": total_new,
            "errors": errors,
        }
