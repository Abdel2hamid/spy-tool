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
import socket
import time
import urllib.error
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
_TIMEOUT = 4  # Hard cap: Apple API must respond within 4 seconds
_APPLE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}
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


def _is_timeout_error(exc: Exception) -> bool:
    """Return True if the exception represents a network timeout."""
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    # urllib wraps socket.timeout inside URLError.reason
    if isinstance(exc, urllib.error.URLError):
        return isinstance(exc.reason, (TimeoutError, socket.timeout))
    return False


def _search_itunes(keyword: str, limit: int = 20) -> Tuple[List[Dict], Optional[str]]:
    """Search iTunes API for apps.

    Returns (results, error_hint).
    error_hint is None on success; a human-readable string on failure.
    Never raises — always returns within _TIMEOUT seconds.
    """
    params = urllib.parse.urlencode({
        "term": keyword,
        "country": "us",
        "entity": "software",
        "limit": limit,
        "lang": "en_us",
    }, quote_via=urllib.parse.quote)
    url = f"{_ITUNES_SEARCH_URL}?{params}"
    req = urllib.request.Request(url, headers=_APPLE_HEADERS)

    logger.info(f"[Search] iTunes search start: '{keyword}' (timeout={_TIMEOUT}s)")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
            results = data.get("results", [])
            logger.info(
                f"[Search] iTunes search success: {len(results)} results "
                f"in {time.time() - t0:.2f}s for '{keyword}'"
            )
            return results, None
    except Exception as e:
        elapsed = time.time() - t0
        if _is_timeout_error(e):
            logger.warning(
                f"[Search] iTunes search timeout after {elapsed:.1f}s for '{keyword}'"
            )
            return [], "Apple API timeout. Try again in a moment."
        logger.warning(
            f"[Search] iTunes search failed after {elapsed:.1f}s "
            f"for '{keyword}': {type(e).__name__}: {e}"
        )
        return [], "Apple API unavailable. Showing local results only."


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
            # Update metadata fields that may have been missing
            subtitle = item.get("subtitle") or ""
            if subtitle:
                existing.subtitle = subtitle
            description = item.get("description") or ""
            if description:
                existing.description = description
            screenshots = item.get("screenshotUrls") or item.get("ipadScreenshotUrls") or []
            if screenshots:
                existing.screenshots = screenshots
            langs = item.get("languageCodesISO2A") or []
            if langs:
                existing.supported_languages = langs
            last_updated_str = item.get("currentVersionReleaseDate")
            if last_updated_str:
                try:
                    existing.last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
                except Exception:
                    pass
            content_rating = item.get("contentRating", "")
            if content_rating:
                existing.content_rating = content_rating
            min_os = item.get("minimumOsVersion", "")
            if min_os:
                existing.minimum_ios_version = min_os
            db.commit()
        return existing, False

    # iTunes returns genres as a list of strings e.g. ["Productivity", "Business"].
    # Use the last element (if more than one) as the secondary category.
    genres = item.get("genres") or []
    secondary_category: Optional[str] = None
    if isinstance(genres, list) and len(genres) > 1 and isinstance(genres[-1], str):
        secondary_category = genres[-1]

    screenshots = item.get("screenshotUrls") or item.get("ipadScreenshotUrls") or []
    last_updated = None
    last_updated_str = item.get("currentVersionReleaseDate")
    if last_updated_str:
        try:
            last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
        except Exception:
            pass

    new_app = App(
        app_id=track_id,
        name=name,
        subtitle=item.get("subtitle", ""),
        description=item.get("description", ""),
        developer=developer,
        developer_id=str(item.get("artistId", "") or ""),
        icon_url=icon_url,
        screenshots=screenshots,
        primary_category=primary_category,
        secondary_category=secondary_category,
        price=price,
        currency=item.get("currency", "USD"),
        is_free=is_free,
        current_version=item.get("version", ""),
        minimum_ios_version=item.get("minimumOsVersion", ""),
        supported_languages=supported_languages,
        release_date=release_date,
        last_updated=last_updated,
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
        # Race condition: another concurrent request may have inserted first.
        # Retry the lookup — if the row now exists, return it as non-new.
        try:
            existing = db.query(App).filter(App.app_id == track_id).first()
            if existing:
                logger.info(f"[Search] Recovered existing app after rollback: {track_id}")
                return existing, False
        except Exception:
            pass
        return None, False


def _get_full_app_details(track_id: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Fetch full app metadata from iTunes Lookup API.

    Returns (item_dict, error_hint).
    item_dict is the first iTunes result, or None on failure / not found.
    error_hint is None on success.
    Never raises — always returns within _TIMEOUT seconds.
    """
    params = urllib.parse.urlencode({
        "id": track_id,
        "country": "us",
        "entity": "software",
    }, quote_via=urllib.parse.quote)
    url = f"{_ITUNES_LOOKUP_URL}?{params}"
    req = urllib.request.Request(url, headers=_APPLE_HEADERS)

    logger.info(f"[Search] iTunes lookup start: trackId={track_id} (timeout={_TIMEOUT}s)")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
            results = data.get("results", [])
            elapsed = time.time() - t0
            if results:
                logger.info(f"[Search] iTunes lookup success in {elapsed:.2f}s for {track_id}")
                return results[0], None
            logger.info(f"[Search] iTunes lookup: no results in {elapsed:.2f}s for {track_id}")
            return None, None
    except Exception as e:
        elapsed = time.time() - t0
        if _is_timeout_error(e):
            logger.warning(
                f"[Search] iTunes lookup timeout after {elapsed:.1f}s for {track_id}"
            )
            return None, "Apple API timeout. Try again in a moment."
        logger.warning(
            f"[Search] iTunes lookup failed after {elapsed:.1f}s "
            f"for {track_id}: {type(e).__name__}: {e}"
        )
        return None, "Apple API unavailable. Try again."


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
        Search for apps: local DB first, then App Store.

        IMPORTANT: This endpoint never writes to the database.
        It returns raw results from local DB and iTunes API so the
        caller can decide which apps to actually import (via lookup_app).

        Local results  → source='database'
        iTunes results → source='app_store'  (id=0, not yet imported)
        """
        if not query or len(query.strip()) < 1:
            return {
                "query": query,
                "results": [],
                "total": 0,
                "from_cache": 0,
            }

        original_query = query.strip()
        logger.info(f"[Search] query='{original_query}'")

        # 1. Search local DB
        db_results = _search_local_db_advanced(self.db, original_query, limit=limit)
        db_count = len(db_results)
        logger.info(f"[Search] db_results={db_count}")

        # 2. If enough local results, skip App Store entirely
        if db_count >= _MIN_LOCAL_RESULTS:
            logger.info(f"[Search] returning {db_count} local results (skipping App Store)")
            return {
                "query": original_query,
                "results": db_results[:limit],
                "total": len(db_results[:limit]),
                "from_cache": db_count,
            }

        # 3. Search iTunes (read-only — no DB writes)
        remaining = max(limit - db_count, 5)
        itunes_results, itunes_error = _search_itunes(original_query, limit=remaining * 2)
        logger.info(
            f"[Search] itunes_results={len(itunes_results)}"
            + (f" error='{itunes_error}'" if itunes_error else "")
        )

        existing_app_ids: Set[str] = {r['app_id'] for r in db_results}

        store_results: List[Dict] = []
        for item in itunes_results:
            track_id = str(item.get("trackId", ""))
            if not track_id or track_id in existing_app_ids:
                continue

            name = item.get("trackName", "")
            if not name:
                continue

            icon_url = item.get("artworkUrl100", "") or item.get("artworkUrl512", "")
            if icon_url:
                icon_url = icon_url.replace("100x100", "512x512").replace("200x200", "512x512")

            price = item.get("price", 0)
            if isinstance(price, str):
                try:
                    price = float(price)
                except Exception:
                    price = 0
            is_free = price == 0 or bool(item.get("isFree", False))

            store_results.append({
                'id': 0,           # Not in DB yet — must call lookup_app to import
                'app_id': track_id,
                'name': name,
                'developer': item.get("artistName", "") or "",
                'icon_url': icon_url or None,
                'current_rating': item.get("averageUserRating") or None,
                'current_reviews': item.get("userRatingCount") or None,
                'primary_category': item.get("primaryGenreName") or None,
                'price': price,
                'is_free': is_free,
                'url': item.get("trackViewUrl") or None,
                'is_new': False,
                'source': 'app_store',
                'match_score': 0.0,
                'match_type': 'api',
            })
            existing_app_ids.add(track_id)

            if len(store_results) >= remaining:
                break

        # 4. Combine: local DB results first, then App Store results
        final_results = db_results + store_results
        logger.info(
            f"[Search] final_results={len(final_results)} "
            f"(db={db_count}, store={len(store_results)})"
        )

        # Only surface the iTunes error when there are no local results to show.
        # If DB results exist, the user sees them and the API error is noise.
        surface_error = itunes_error if (itunes_error and db_count == 0) else None

        return {
            "query": original_query,
            "results": final_results[:limit],
            "total": len(final_results[:limit]),
            "from_cache": db_count,
            "error_hint": surface_error,
        }

    def lookup_app(self, track_id: str) -> Dict:
        """Fetch full app details by trackId and insert into database."""
        logger.info(f"[Search] Looking up app: {track_id}")

        itunes_data, lookup_error = _get_full_app_details(track_id)
        if not itunes_data:
            error_msg = lookup_error or "App not found in App Store"
            return {"error": error_msg}

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
