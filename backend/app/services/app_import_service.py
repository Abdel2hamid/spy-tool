"""
On-Demand App Import Service
============================
Allows users to search for apps by name and import them on-demand.

Improved Search Algorithm:
1. Query normalization (lowercase, strip punctuation, remove stopwords)
2. Multi-field search (name, developer, bundle_id)
3. Weighted scoring system for ranking
4. Fuzzy matching with PostgreSQL similarity
5. Token-based search for multi-word queries
6. Fallback to iTunes API if local results < 10
7. Deduplication by trackId
8. Result ranking by match quality + popularity
"""

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
_ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
_REQUEST_DELAY = 0.1
_TIMEOUT = 15
_MIN_LOCAL_RESULTS = 10
_MAX_RESULTS = 20
_FUZZY_THRESHOLD = 0.35

_STOPWORDS = frozenset({
    'app', 'apps', 'free', 'ios', 'iphone', 'ipad', 'mobile', 'download',
    'the', 'a', 'an', 'and', 'or', 'for', 'to', 'of', 'in', 'on', 'at',
})

_PLURAL_MAP = {
    'trackers': 'tracker', 'editors': 'editor', 'games': 'game',
    'apps': 'app', 'photos': 'photo', 'music': 'music', 'videos': 'video',
    'messages': 'message', 'chats': 'chat', 'calls': 'call',
}


def _normalize_query(query: str) -> str:
    """
    Normalize query string:
    - lowercase
    - strip punctuation
    - collapse multiple spaces
    - remove stopwords
    - normalize plurals
    """
    q = query.lower()
    q = re.sub(r'[^\w\s]', ' ', q)
    q = re.sub(r'\s+', ' ', q).strip()
    
    words = q.split()
    words = [w for w in words if w not in _STOPWORDS]
    words = [_PLURAL_MAP.get(w, w) for w in words]
    
    return ' '.join(words)


def _tokenize(query: str) -> List[str]:
    """Split query into tokens."""
    normalized = _normalize_query(query)
    return normalized.split() if normalized else []


def _get_exact_match_score(name: str, query: str) -> float:
    """Check for exact name match."""
    name_lower = name.lower()
    query_lower = query.lower().strip()
    if name_lower == query_lower:
        return 1.0
    return 0.0


def _get_prefix_match_score(name: str, query: str) -> float:
    """Check if query is a prefix of the name."""
    name_lower = name.lower()
    query_lower = query.lower().strip()
    if name_lower.startswith(query_lower):
        return 1.0
    return 0.0


def _get_substring_match_score(name: str, query: str) -> float:
    """Check if query is a substring in the name."""
    name_lower = name.lower()
    query_lower = query.lower().strip()
    if query_lower in name_lower:
        return 0.5
    return 0.0


def _get_developer_match_score(developer: str, query: str) -> float:
    """Check for developer name match."""
    if not developer:
        return 0.0
    dev_lower = developer.lower()
    query_lower = query.lower().strip()
    if query_lower in dev_lower:
        return 0.3
    return 0.0


def _calculate_match_score(name: str, developer: str, query: str, tokens: List[str]) -> Tuple[float, str]:
    """
    Calculate weighted match score.
    
    Returns: (score, match_type)
    """
    exact_score = _get_exact_match_score(name, query)
    if exact_score > 0:
        return 5.0 * exact_score, 'exact'
    
    prefix_score = _get_prefix_match_score(name, query)
    if prefix_score > 0:
        return 3.0 * prefix_score, 'prefix'
    
    substring_score = _get_substring_match_score(name, query)
    if substring_score > 0:
        return 2.0 * substring_score, 'substring'
    
    dev_score = _get_developer_match_score(developer, query)
    if dev_score > 0:
        return 1.0 * dev_score, 'developer'
    
    if tokens:
        name_lower = name.lower()
        dev_lower = (developer or '').lower()
        token_matches = sum(1 for t in tokens if t in name_lower or t in dev_lower)
        if token_matches > 0:
            return (token_matches / len(tokens)) * 1.5, 'tokens'
    
    return 0.0, 'none'


def _search_local_db_advanced(db: Session, query: str, limit: int = 20) -> List[Dict]:
    """
    Advanced database search with weighted scoring.
    
    - Searches name, developer fields
    - Uses PostgreSQL similarity if available
    - Token-based matching
    - Weighted scoring + popularity ranking
    """
    from app.models.models import App

    if not query or len(query.strip()) < 1:
        return []

    normalized_query = _normalize_query(query)
    tokens = _tokenize(query)
    query_lower = query.lower().strip()
    
    logger.debug(f"[Search] normalized='{normalized_query}', tokens={tokens}")

    apps_query = db.query(App)

    search_conditions = []
    if query.strip():
        search_conditions.append(App.name.ilike(f"%{query_lower}%"))
        search_conditions.append(App.developer.ilike(f"%{query_lower}%"))
        search_conditions.append(App.name.ilike(f"{query_lower}%"))
    
    if tokens:
        for token in tokens:
            if len(token) >= 2:
                search_conditions.append(App.name.ilike(f"%{token}%"))
                search_conditions.append(App.developer.ilike(f"%{token}%"))

    if search_conditions:
        apps_query = apps_query.filter(or_(*search_conditions))

    apps = apps_query.limit(limit * 3).all()

    scored_results = []
    for app in apps:
        match_score, match_type = _calculate_match_score(
            app.name or '', 
            app.developer or '', 
            query,
            tokens
        )

        if match_score == 0:
            try:
                from sqlalchemy import func as sql_func
                similarity = sql_func.similarity(
                    func.lower(app.name), 
                    query_lower
                )
                if similarity is not None:
                    if similarity > _FUZZY_THRESHOLD:
                        match_score = float(similarity) * 2
                        match_type = 'fuzzy'
            except Exception:
                pass

        if match_score > 0 or not tokens:
            popularity_score = (
                (app.current_rating or 0) * 0.2 + 
                min((app.current_reviews or 0) / 10000, 10)
            )
            final_score = match_score + popularity_score * 0.1

            scored_results.append({
                'app': app,
                'match_score': final_score,
                'match_type': match_type,
                'name_match_score': match_score,
            })

    scored_results.sort(key=lambda x: (-x['match_score'], -(x['app'].current_reviews or 0)))

    results = []
    for item in scored_results[:limit]:
        app = item['app']
        results.append({
            'id': app.id,
            'app_id': app.app_id,
            'name': app.name,
            'developer': app.developer,
            'icon_url': app.icon_url,
            'current_rating': app.current_rating,
            'current_reviews': app.current_reviews,
            'primary_category': app.primary_category,
            'price': app.price,
            'is_free': app.is_free,
            'url': app.url,
            'is_new': False,
            'source': 'database',
            'match_score': round(item['name_match_score'], 2),
            'match_type': item['match_type'],
        })

    return results


def _search_itunes(keyword: str, limit: int = 20) -> List[Dict]:
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
        logger.warning(f"[Search] iTunes search failed for '{keyword}': {e}")
        return []


def _get_or_create_app(db: Session, item: Dict, update_existing: bool = True) -> tuple:
    """Check if app exists in DB, create or update if found."""
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
        logger.info(f"[Search] Created new app: {name} (trackId: {track_id})")
        return new_app, True
    except Exception as e:
        db.rollback()
        logger.warning(f"[Search] Failed to create app {track_id}: {e}")
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
        logger.warning(f"[Search] iTunes lookup failed for '{track_id}': {e}")
        return None


def _get_category_id(db: Session, category_name: str) -> Optional[int]:
    """Get category ID by name."""
    from app.models.models import Category
    if not category_name:
        return None
    cat = db.query(Category).filter(Category.name == category_name).first()
    return cat.id if cat else None


class AppImportService:
    """Service for on-demand app import with improved search."""

    def __init__(self, db: Session):
        self.db = db

    def search_apps(self, query: str, limit: int = 20) -> Dict:
        """
        Advanced search for apps with multi-stage ranking.
        
        1. Query normalization
        2. Database search with weighted scoring
        3. Fallback to iTunes API if needed
        4. Deduplication and final ranking
        """
        if not query or len(query.strip()) < 1:
            return {
                "query": query,
                "results": [],
                "total": 0,
                "from_cache": 0,
            }

        original_query = query.strip()
        normalized = _normalize_query(original_query)
        
        logger.info(f"[Search] query='{original_query}', normalized='{normalized}'")

        db_results = _search_local_db_advanced(self.db, original_query, limit=limit)
        db_count = len(db_results)
        
        logger.info(f"[Search] db_results={db_count}")

        if db_count >= _MIN_LOCAL_RESULTS:
            final_results = db_results[:limit]
            logger.info(f"[Search] final_results={len(final_results)} (local only)")
            return {
                "query": original_query,
                "results": final_results,
                "total": len(final_results),
                "from_cache": len([r for r in final_results if r['source'] == 'database']),
            }

        itunes_results = _search_itunes(original_query, limit=limit)
        logger.info(f"[Search] apple_results={len(itunes_results)}")

        existing_ids: Set[str] = {r['app_id'] for r in db_results}
        existing_ids.add('')
        existing_ids.add('0')

        apple_imported = 0
        for item in itunes_results:
            track_id = str(item.get("trackId", ""))
            if not track_id or track_id in existing_ids:
                continue

            app, is_new = _get_or_create_app(self.db, item, update_existing=False)
            if app:
                db_results.append({
                    'id': app.id,
                    'app_id': app.app_id,
                    'name': app.name,
                    'developer': app.developer,
                    'icon_url': app.icon_url,
                    'current_rating': app.current_rating,
                    'current_reviews': app.current_reviews,
                    'primary_category': app.primary_category,
                    'price': app.price,
                    'is_free': app.is_free,
                    'url': app.url,
                    'is_new': is_new,
                    'source': 'app_store',
                    'match_score': 0,
                    'match_type': 'api',
                })
                existing_ids.add(track_id)
                apple_imported += 1
                time.sleep(_REQUEST_DELAY)

            if len(db_results) >= limit:
                break

        logger.info(f"[Search] apple_imported={apple_imported}")

        final_results = db_results[:limit]
        
        final_results.sort(key=lambda x: (
            -x.get('match_score', 0),
            -(x.get('current_reviews') or 0),
            -(x.get('current_rating') or 0)
        ))

        logger.info(f"[Search] final_results={len(final_results)}")

        return {
            "query": original_query,
            "results": final_results,
            "total": len(final_results),
            "from_cache": db_count,
        }

    def lookup_app(self, track_id: str) -> Dict:
        """Fetch full app details by trackId and insert into database."""
        logger.info(f"[Search] Looking up app: {track_id}")

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
            logger.info(f"[Search] Triggered extraction for app {app_id}")
        except Exception as e:
            logger.warning(f"[Search] Extraction failed for app {app_id}: {e}")

        time.sleep(0.5)

        try:
            competitor_svc = CompetitorKeywordService(self.db)
            competitor_svc.mine_for_app(app_id)
            logger.info(f"[Search] Triggered competitor mining for app {app_id}")
        except Exception as e:
            logger.warning(f"[Search] Competitor mining failed for app {app_id}: {e}")

        time.sleep(0.5)

        try:
            pipeline = KeywordIntelligencePipeline(self.db)
            pipeline.enrich_app(app_id)
            logger.info(f"[Search] Triggered intelligence enrichment for app {app_id}")
        except Exception as e:
            logger.warning(f"[Search] Intelligence enrichment failed for app {app_id}: {e}")
