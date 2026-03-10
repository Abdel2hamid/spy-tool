"""
Keyword Search Service
======================
Allows users to search for apps by keyword and discover new apps
from the App Store even if they're not in the database yet.

Flow:
1. User enters keyword
2. Backend calls iTunes Search API (entity=software, limit=50)
3. For each result, check if trackId exists in apps table
4. If not, insert app metadata
5. Return results to frontend
6. Trigger background jobs for new apps (keyword extraction, competitor discovery)
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
_REQUEST_DELAY = 0.1
_TIMEOUT = 15


def _search_itunes(keyword: str, limit: int = 50) -> List[Dict]:
    """Call iTunes Search API and return results."""
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
        logger.warning(f"[KeywordSearch] iTunes API failed for '{keyword}': {e}")
        return []


def _get_or_create_app(db: Session, item: Dict) -> tuple:
    """
    Check if app exists in DB, create if not.
    Returns (app, is_new) tuple.
    """
    from app.models.models import App, Category

    track_id = str(item.get("trackId", ""))
    if not track_id:
        return None, False

    existing = db.query(App).filter(App.app_id == track_id).first()
    if existing:
        return existing, False

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
        logger.info(f"[KeywordSearch] Created new app: {name} (trackId: {track_id})")
        return new_app, True
    except Exception as e:
        db.rollback()
        logger.warning(f"[KeywordSearch] Failed to create app {track_id}: {e}")
        return None, False


def _get_category_id(db: Session, category_name: str) -> Optional[int]:
    """Get category ID by name, return None if not found."""
    from app.models.models import Category
    if not category_name:
        return None
    cat = db.query(Category).filter(Category.name == category_name).first()
    return cat.id if cat else None


class KeywordSearchService:
    """Service for keyword-based app discovery."""

    def __init__(self, db: Session):
        self.db = db

    def search(self, keyword: str, limit: int = 50) -> Dict:
        """
        Search for apps by keyword, insert new ones if not exists.
        Returns dict with results and metadata.
        """
        if not keyword or len(keyword.strip()) < 2:
            return {
                "keyword": keyword,
                "results": [],
                "total": 0,
                "new_apps_count": 0,
            }

        keyword = keyword.strip()
        logger.info(f"[KeywordSearch] Searching for keyword: '{keyword}'")

        items = _search_itunes(keyword, limit=limit)
        
        if not items:
            return {
                "keyword": keyword,
                "results": [],
                "total": 0,
                "new_apps_count": 0,
            }

        results = []
        new_apps = []

        for item in items:
            app, is_new = _get_or_create_app(self.db, item)
            if not app:
                continue

            if is_new:
                new_apps.append(app.id)

            category_id = _get_category_id(self.db, item.get("primaryGenreName", ""))
            if category_id and not app.category_id:
                app.category_id = category_id
                self.db.commit()

            results.append({
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
                "is_new": is_new,
            })

            time.sleep(_REQUEST_DELAY)

        logger.info(
            f"[KeywordSearch] Found {len(results)} apps for '{keyword}', "
            f"{len(new_apps)} new"
        )

        return {
            "keyword": keyword,
            "results": results,
            "total": len(results),
            "new_apps_count": len(new_apps),
            "new_app_ids": new_apps,
        }

    def trigger_background_enrichment(self, app_ids: List[int]) -> None:
        """
        Trigger background jobs for newly discovered apps.
        This queues the apps for keyword extraction, competitor discovery, etc.
        """
        if not app_ids:
            return

        from app.services.keyword_extraction_service import KeywordExtractionService
        from app.services.competitor_keyword_service import CompetitorKeywordService
        from app.services.keyword_intelligence_pipeline import KeywordIntelligencePipeline

        for app_id in app_ids:
            try:
                extractor = KeywordExtractionService(self.db)
                extractor.extract_for_app(app_id)
                logger.info(f"[KeywordSearch] Triggered extraction for app {app_id}")
            except Exception as e:
                logger.warning(f"[KeywordSearch] Extraction failed for app {app_id}: {e}")

            time.sleep(0.5)

            try:
                competitor_svc = CompetitorKeywordService(self.db)
                competitor_svc.mine_for_app(app_id)
                logger.info(f"[KeywordSearch] Triggered competitor mining for app {app_id}")
            except Exception as e:
                logger.warning(f"[KeywordSearch] Competitor mining failed for app {app_id}: {e}")

            time.sleep(0.5)

            try:
                pipeline = KeywordIntelligencePipeline(self.db)
                pipeline.enrich_app(app_id)
                logger.info(f"[KeywordSearch] Triggered intelligence enrichment for app {app_id}")
            except Exception as e:
                logger.warning(f"[KeywordSearch] Intelligence enrichment failed for app {app_id}: {e}")
