"""
On-Demand App Import Service
============================
Allows users to search for apps by name and import them on-demand.

Flow:
1. User searches app name
2. Backend first searches local database
3. If not found (or needs more), query iTunes Search API
4. User clicks app → fetch full details via iTunes Lookup API
5. Insert/update app in database
6. Return full details to frontend
7. Trigger background enrichment jobs
"""

import json
import logging
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
_ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
_REQUEST_DELAY = 0.1
_TIMEOUT = 15


def _search_local_db(db: Session, query: str, limit: int = 10) -> List[Dict]:
    """Search for apps in local database by name."""
    from app.models.models import App

    search_term = f"%{query}%"
    apps = (
        db.query(App)
        .filter(App.name.ilike(search_term))
        .order_by(App.current_reviews.desc())
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
            "current_rating": app.current_rating,
            "current_reviews": app.current_reviews,
            "primary_category": app.primary_category,
            "price": app.price,
            "is_free": app.is_free,
            "url": app.url,
            "is_new": False,
            "source": "database",
        }
        for app in apps
    ]


def _search_itunes(keyword: str, limit: int = 10) -> List[Dict]:
    """Search iTunes API for apps."""
    params = urllib.parse.urlencode({
        "term": keyword,
        "country": "us",
        "entity": "software",
        "limit": limit,
        "lang": "en_us",
    })
    url = f"{_ITUNES_SEARCH_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "AppStoreSpy/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
            return data.get("results", [])
    except Exception as e:
        logger.warning(f"[AppImport] iTunes search failed for '{keyword}': {e}")
        return []


def _get_or_create_app(db: Session, item: Dict, update_existing: bool = True) -> tuple:
    """
    Check if app exists in DB, create or update if found.
    Returns (app, is_new) tuple.
    """
    from app.models.models import App, Category

    track_id = str(item.get("trackId", ""))
    if not track_id:
        return None, False

    existing = db.query(App).filter(App.app_id == track_id).first()

    name = item.get("trackName", "")
    developer = item.get("artistName", "")
    icon_url = item.get("artworkUrl100", "") or item.get("artworkUrl512", "")
    if icon_url:
        icon_url = icon_url.replace("100x100", "512x512").replace("200x200", "512x512")

    primary_category = item.get("primaryGenreName", "")
    price = item.get("price", 0)
    if isinstance(price, str):
        try:
            price = float(price)
        except:
            price = 0

    is_free = price == 0 or item.get("isFree", False)

    release_date_str = item.get("releaseDate")
    release_date = None
    if release_date_str:
        try:
            release_date = datetime.fromisoformat(release_date_str.replace("Z", "+00:00"))
        except:
            pass

    supported_languages = item.get("languageCodesISO2A", [])

    if existing:
        if update_existing:
            existing.name = name
            existing.developer = developer
            existing.icon_url = icon_url
            existing.primary_category = primary_category
            existing.price = price
            existing.is_free = is_free
            existing.current_version = item.get("version", "")
            existing.current_rating = item.get("averageUserRating", 0)
            existing.current_reviews = item.get("userRatingCount", 0)
            existing.url = item.get("trackViewUrl", "")
            if release_date:
                existing.release_date = release_date
        return existing, False

    new_app = App(
        app_id=track_id,
        name=name,
        subtitle=item.get("subtitle", ""),
        description=item.get("description", ""),
        developer=developer,
        developer_id=item.get("artistId", ""),
        icon_url=icon_url,
        primary_category=primary_category,
        secondary_category=item.get("genres", [{}])[-1].get("name") if item.get("genres") else None,
        price=price,
        currency=item.get("currency", "USD"),
        is_free=is_free,
        current_version=item.get("version", ""),
        minimum_ios_version=item.get("minimumOsVersion", ""),
        supported_languages=supported_languages,
        release_date=release_date,
        content_rating=item.get("contentRating", ""),
        current_rating=item.get("averageUserRating", 0),
        current_reviews=item.get("userRatingCount", 0),
        url=item.get("trackViewUrl", ""),
    )

    try:
        db.add(new_app)
        db.commit()
        db.refresh(new_app)
        logger.info(f"[AppImport] Created new app: {name} (trackId: {track_id})")
        return new_app, True
    except Exception as e:
        db.rollback()
        logger.warning(f"[AppImport] Failed to create app {track_id}: {e}")
        return None, False


def _get_full_app_details(track_id: str) -> Optional[Dict]:
    """Fetch full app metadata from iTunes Lookup API."""
    url = f"{_ITUNES_LOOKUP_URL}?id={track_id}&country=us&entity=software"
    req = urllib.request.Request(url, headers={"User-Agent": "AppStoreSpy/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
            results = data.get("results", [])
            if results:
                return results[0]
    except Exception as e:
        logger.warning(f"[AppImport] iTunes lookup failed for '{track_id}': {e}")
        return None


def _get_category_id(db: Session, category_name: str) -> Optional[int]:
    """Get category ID by name."""
    from app.models.models import Category
    if not category_name:
        return None
    cat = db.query(Category).filter(Category.name == category_name).first()
    return cat.id if cat else None


class AppImportService:
    """Service for on-demand app import."""

    def __init__(self, db: Session):
        self.db = db

    def search_apps(self, query: str, limit: int = 10) -> Dict:
        """
        Search for apps: first check local DB, then iTunes if needed.
        """
        if not query or len(query.strip()) < 2:
            return {
                "query": query,
                "results": [],
                "total": 0,
                "from_cache": 0,
            }

        query = query.strip()
        logger.info(f"[AppImport] Searching for: '{query}'")

        db_results = _search_local_db(self.db, query, limit=limit)
        from_cache = len(db_results)

        if from_cache >= limit:
            return {
                "query": query,
                "results": db_results,
                "total": from_cache,
                "from_cache": from_cache,
            }

        itunes_results = _search_itunes(query, limit=limit)

        existing_ids = {r["app_id"] for r in db_results}

        for item in itunes_results:
            track_id = str(item.get("trackId", ""))
            if track_id and track_id not in existing_ids:
                app, _ = _get_or_create_app(self.db, item, update_existing=False)
                if app:
                    db_results.append({
                        "id": app.id,
                        "app_id": app.app_id,
                        "name": app.name,
                        "developer": app.developer,
                        "icon_url": app.icon_url,
                        "current_rating": app.current_rating,
                        "current_reviews": app.current_reviews,
                        "primary_category": app.primary_category,
                        "price": app.price,
                        "is_free": app.is_free,
                        "url": app.url,
                        "is_new": True,
                        "source": "itunes",
                    })
                    existing_ids.add(track_id)
                time.sleep(_REQUEST_DELAY)

            if len(db_results) >= limit:
                break

        logger.info(f"[AppImport] Found {len(db_results)} results for '{query}'")

        return {
            "query": query,
            "results": db_results,
            "total": len(db_results),
            "from_cache": from_cache,
        }

    def lookup_app(self, track_id: str) -> Dict:
        """
        Fetch full app details by trackId and insert into database.
        Returns full app metadata.
        """
        logger.info(f"[AppImport] Looking up app: {track_id}")

        itunes_data = _get_full_app_details(track_id)
        if not itunes_data:
            return {"error": "App not found in App Store"}

        app, is_new = _get_or_create_app(self.db, itunes_data, update_existing=True)
        if not app:
            return {"error": "Failed to import app"}

        category_id = _get_category_id(self.db, itunes_data.get("primaryGenreName", ""))
        if category_id and not app.category_id:
            app.category_id = category_id
            self.db.commit()

        screenshots = itunes_data.get("screenshotUrls", []) or itunes_data.get("ipadScreenshotUrls", [])
        
        in_app_purchases = None
        if itunes_data.get("inAppPurchases"):
            in_app_purchases = [
                {"name": p.get("productName"), "price": p.get("price")}
                for p in itunes_data.get("inAppPurchases", [])
            ]

        result = {
            "id": app.id,
            "app_id": app.app_id,
            "name": app.name,
            "subtitle": app.subtitle,
            "description": app.description,
            "developer": app.developer,
            "developer_id": app.developer_id,
            "icon_url": app.icon_url,
            "screenshots": screenshots,
            "primary_category": app.primary_category,
            "secondary_category": app.secondary_category,
            "price": app.price,
            "currency": app.currency,
            "is_free": app.is_free,
            "in_app_purchases": in_app_purchases,
            "current_version": app.current_version,
            "minimum_ios_version": app.minimum_ios_version,
            "supported_languages": app.supported_languages,
            "release_date": app.release_date.isoformat() if app.release_date else None,
            "last_updated": app.last_updated.isoformat() if app.last_updated else None,
            "content_rating": app.content_rating,
            "current_rating": app.current_rating,
            "current_reviews": app.current_reviews,
            "url": app.url,
            "is_new": is_new,
        }

        return result

    def trigger_enrichment(self, app_id: int) -> None:
        """Trigger background enrichment jobs for an app."""
        from app.services.keyword_extraction_service import KeywordExtractionService
        from app.services.competitor_keyword_service import CompetitorKeywordService
        from app.services.keyword_intelligence_pipeline import KeywordIntelligencePipeline

        try:
            extractor = KeywordExtractionService(self.db)
            extractor.extract_for_app(app_id)
            logger.info(f"[AppImport] Triggered extraction for app {app_id}")
        except Exception as e:
            logger.warning(f"[AppImport] Extraction failed for app {app_id}: {e}")

        time.sleep(0.5)

        try:
            competitor_svc = CompetitorKeywordService(self.db)
            competitor_svc.mine_for_app(app_id)
            logger.info(f"[AppImport] Triggered competitor mining for app {app_id}")
        except Exception as e:
            logger.warning(f"[AppImport] Competitor mining failed for app {app_id}: {e}")

        time.sleep(0.5)

        try:
            pipeline = KeywordIntelligencePipeline(self.db)
            pipeline.enrich_app(app_id)
            logger.info(f"[AppImport] Triggered intelligence enrichment for app {app_id}")
        except Exception as e:
            logger.warning(f"[AppImport] Intelligence enrichment failed for app {app_id}: {e}")
