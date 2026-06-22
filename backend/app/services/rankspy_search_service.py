"""
RankSpy Search Service
======================
Unified search engine that merges local PostgreSQL results with live
App Store (iTunes Search API) results.

Flow:
1. Full-text + trigram search against local DB (instant).
2. If local results < threshold OR force_live_search=True → query iTunes.
3. Merge + deduplicate by app_id (track_id).
4. UPSERT newly discovered apps (source='discovered').
5. Queue background enrichment for new apps (fire-and-forget).
6. Return merged results immediately — never block on enrichment.
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.services.apple_http_client import apple_fetch_json, ITUNES_SEARCH_URL

logger = logging.getLogger(__name__)

_LOCAL_RESULT_THRESHOLD = 50
_MAX_ITUNES_RESULTS = 100
_ITUNES_TIMEOUT = 8

# In-flight enrichment tracker — prevents duplicate background jobs
_enrichment_in_progress: Set[int] = set()
_enrichment_lock = threading.Lock()


def _mark_enrichment_start(app_db_id: int) -> bool:
    """Return True if this app is NOT already being enriched (and mark it)."""
    with _enrichment_lock:
        if app_db_id in _enrichment_in_progress:
            return False
        _enrichment_in_progress.add(app_db_id)
        return True


def _mark_enrichment_done(app_db_id: int) -> None:
    with _enrichment_lock:
        _enrichment_in_progress.discard(app_db_id)


class RankSpySearchService:
    """Unified search: local DB + live App Store."""

    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        force_live: bool = False,
    ) -> Dict:
        if not query or len(query.strip()) < 2:
            return self._empty_response(query)

        query = query.strip()
        logger.info(f"[RankSpy] Search: '{query}' limit={limit} offset={offset} force_live={force_live}")

        # Phase 1: local DB search
        local_results = self._search_local(query, limit=limit + offset + 50)
        local_count = len(local_results)
        logger.info(f"[RankSpy] Local results: {local_count}")

        # Phase 2: iTunes API (if needed)
        itunes_results: List[Dict] = []
        itunes_error: Optional[str] = None
        need_itunes = force_live or local_count < _LOCAL_RESULT_THRESHOLD

        if need_itunes:
            itunes_results, itunes_error = self._search_itunes(query, limit=_MAX_ITUNES_RESULTS)
            logger.info(
                f"[RankSpy] iTunes results: {len(itunes_results)}"
                + (f" error='{itunes_error}'" if itunes_error else "")
            )

        # Phase 3: merge + deduplicate
        merged, new_app_ids = self._merge_results(local_results, itunes_results, query)

        # Phase 4: fire-and-forget enrichment for new apps
        if new_app_ids:
            self._queue_enrichment(new_app_ids)

        # Paginate
        total = len(merged)
        page = merged[offset : offset + limit]

        tracked = sum(1 for r in page if r["source"] == "tracked")
        discovered = sum(1 for r in page if r["source"] == "discovered")

        return {
            "query": query,
            "results": page,
            "total": total,
            "tracked_count": tracked,
            "discovered_count": discovered,
            "has_appstore_results": len(itunes_results) > 0,
            "error_hint": itunes_error if (itunes_error and local_count == 0) else None,
        }

    # ------------------------------------------------------------------
    # Phase 1: Local DB search (trigram + ILIKE)
    # ------------------------------------------------------------------

    def _search_local(self, query: str, limit: int = 100) -> List[Dict]:
        from app.models.models import App

        q_lower = query.lower().strip()
        tokens = [t for t in q_lower.split() if len(t) >= 2]

        conditions = [
            App.name.ilike(f"%{q_lower}%"),
            App.developer.ilike(f"%{q_lower}%"),
            App.subtitle.ilike(f"%{q_lower}%"),
        ]
        for token in tokens:
            conditions.append(App.name.ilike(f"%{token}%"))

        apps = (
            self.db.query(App)
            .filter(or_(*conditions))
            .limit(limit * 2)
            .all()
        )

        scored = []
        for app in apps:
            score, match_type = self._score_match(app.name or "", app.developer or "", query, tokens)
            if score > 0:
                popularity = (
                    (app.current_rating or 0) * 0.2
                    + min((app.current_reviews or 0) / 10000, 10)
                )
                scored.append({
                    "id": app.id,
                    "app_id": app.app_id,
                    "name": app.name,
                    "developer": app.developer,
                    "icon_url": app.icon_url,
                    "current_rating": app.current_rating,
                    "current_reviews": app.current_reviews,
                    "primary_category": app.primary_category,
                    "price": app.price or 0,
                    "is_free": app.is_free if app.is_free is not None else True,
                    "url": app.url,
                    "source": app.source or "tracked",
                    "match_score": round(score + popularity * 0.1, 3),
                    "match_type": match_type,
                    "enrichment_status": "complete" if app.last_enriched_at else "pending",
                })

        scored.sort(key=lambda x: (-x["match_score"], -(x.get("current_reviews") or 0)))
        return scored[:limit]

    def _score_match(
        self, name: str, developer: str, query: str, tokens: List[str]
    ) -> Tuple[float, str]:
        n = name.lower()
        q = query.lower().strip()

        if n == q:
            return 5.0, "exact"
        if n.startswith(q):
            return 3.0, "prefix"
        if q in n:
            return 2.0, "substring"
        if developer and q in developer.lower():
            return 1.0, "developer"
        if tokens:
            hits = sum(1 for t in tokens if t in n or t in developer.lower())
            if hits > 0:
                return (hits / len(tokens)) * 1.5, "tokens"
        return 0.0, "none"

    # ------------------------------------------------------------------
    # Phase 2: iTunes Search API
    # ------------------------------------------------------------------

    def _search_itunes(self, keyword: str, limit: int = 100) -> Tuple[List[Dict], Optional[str]]:
        try:
            data = apple_fetch_json(
                ITUNES_SEARCH_URL,
                params={
                    "term": keyword,
                    "country": "us",
                    "entity": "software",
                    "limit": min(limit, 200),
                    "lang": "en_us",
                },
                timeout=_ITUNES_TIMEOUT,
            )
            if not data:
                return [], "Apple API returned no data."
            return data.get("results", []), None
        except Exception as e:
            logger.warning(f"[RankSpy] iTunes search failed: {e}")
            return [], "Apple API unavailable. Showing local results only."

    # ------------------------------------------------------------------
    # Phase 3: Merge + deduplicate + UPSERT
    # ------------------------------------------------------------------

    def _merge_results(
        self, local: List[Dict], itunes: List[Dict], query: str
    ) -> Tuple[List[Dict], List[int]]:
        """Merge local + iTunes results. Returns (merged_list, new_app_db_ids)."""
        from app.models.models import App

        seen_app_ids: Set[str] = {r["app_id"] for r in local}
        merged = list(local)
        new_app_ids: List[int] = []

        if not itunes:
            return merged, new_app_ids

        # Batch-check which iTunes apps already exist in DB
        itunes_track_ids = [str(item.get("trackId", "")) for item in itunes if item.get("trackId")]
        # Filter to only those not in local results
        itunes_track_ids = [tid for tid in itunes_track_ids if tid not in seen_app_ids]

        existing_map: Dict[str, int] = {}
        if itunes_track_ids:
            rows = (
                self.db.query(App.app_id, App.id)
                .filter(App.app_id.in_(itunes_track_ids))
                .all()
            )
            existing_map = {row[0]: row[1] for row in rows}

        for item in itunes:
            track_id = str(item.get("trackId", ""))
            if not track_id or track_id in seen_app_ids:
                continue

            name = item.get("trackName", "")
            if not name:
                continue

            seen_app_ids.add(track_id)

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

            if track_id in existing_map:
                # App exists in DB but wasn't in local search results — update and include
                db_id = existing_map[track_id]
                app_obj = self.db.query(App).filter(App.id == db_id).first()
                enrichment = "complete" if (app_obj and app_obj.last_enriched_at) else "pending"
                source = (app_obj.source or "tracked") if app_obj else "tracked"
            else:
                # Truly new app — UPSERT
                app_obj, db_id = self._upsert_discovered_app(item)
                if not app_obj:
                    continue
                new_app_ids.append(db_id)
                enrichment = "pending"
                source = "discovered"

            merged.append({
                "id": db_id,
                "app_id": track_id,
                "name": name,
                "developer": item.get("artistName") or None,
                "icon_url": icon_url or None,
                "current_rating": item.get("averageUserRating"),
                "current_reviews": item.get("userRatingCount"),
                "primary_category": item.get("primaryGenreName"),
                "price": price,
                "is_free": is_free,
                "url": item.get("trackViewUrl"),
                "source": source,
                "match_score": 0.0,
                "match_type": "api",
                "enrichment_status": enrichment,
            })

        return merged, new_app_ids

    def _upsert_discovered_app(self, item: Dict):
        """Insert a newly discovered app into the DB. Returns (app, db_id) or (None, 0)."""
        from app.models.models import App

        track_id = str(item.get("trackId", ""))
        now = datetime.now(timezone.utc)

        icon_url = item.get("artworkUrl100", "") or item.get("artworkUrl512", "")
        if icon_url:
            icon_url = icon_url.replace("100x100", "512x512").replace("200x200", "512x512")

        price = item.get("price", 0)
        if isinstance(price, str):
            try:
                price = float(price)
            except Exception:
                price = 0

        release_date = None
        rd_str = item.get("releaseDate")
        if rd_str:
            try:
                release_date = datetime.fromisoformat(rd_str.replace("Z", "+00:00"))
            except Exception:
                pass

        last_updated = None
        lu_str = item.get("currentVersionReleaseDate")
        if lu_str:
            try:
                last_updated = datetime.fromisoformat(lu_str.replace("Z", "+00:00"))
            except Exception:
                pass

        genres = item.get("genres") or []
        secondary_category = None
        if isinstance(genres, list) and len(genres) > 1 and isinstance(genres[-1], str):
            secondary_category = genres[-1]

        screenshots = item.get("screenshotUrls") or item.get("ipadScreenshotUrls") or []

        new_app = App(
            app_id=track_id,
            name=item.get("trackName", ""),
            subtitle=item.get("subtitle", ""),
            description=item.get("description", ""),
            developer=item.get("artistName", ""),
            developer_id=str(item.get("artistId", "") or ""),
            icon_url=icon_url,
            screenshots=screenshots,
            primary_category=item.get("primaryGenreName", ""),
            secondary_category=secondary_category,
            price=price,
            currency=item.get("currency", "USD"),
            is_free=price == 0 or bool(item.get("isFree", False)),
            current_version=item.get("version", ""),
            minimum_ios_version=item.get("minimumOsVersion", ""),
            supported_languages=item.get("languageCodesISO2A", []),
            release_date=release_date,
            last_updated=last_updated,
            content_rating=item.get("contentRating", ""),
            current_rating=item.get("averageUserRating", 0),
            current_reviews=item.get("userRatingCount", 0),
            url=item.get("trackViewUrl", ""),
            source="discovered",
            discovered_at=now,
            ingestion_stage="light",
        )

        try:
            self.db.add(new_app)
            self.db.commit()
            self.db.refresh(new_app)
            logger.info(f"[RankSpy] Discovered new app: {new_app.name} ({track_id})")
            return new_app, new_app.id
        except Exception as e:
            self.db.rollback()
            logger.warning(f"[RankSpy] UPSERT failed for {track_id}: {e}")
            # Race condition recovery
            try:
                existing = self.db.query(App).filter(App.app_id == track_id).first()
                if existing:
                    return existing, existing.id
            except Exception:
                pass
            return None, 0

    # ------------------------------------------------------------------
    # Phase 4: Background enrichment (fire-and-forget)
    # ------------------------------------------------------------------

    def _queue_enrichment(self, app_db_ids: List[int]) -> None:
        """Spawn a single daemon thread to enrich all new apps."""
        # Filter out apps already being enriched
        to_enrich = [aid for aid in app_db_ids if _mark_enrichment_start(aid)]
        if not to_enrich:
            return

        logger.info(f"[RankSpy] Queuing enrichment for {len(to_enrich)} new apps: {to_enrich}")
        t = threading.Thread(
            target=self._run_enrichment_batch,
            args=(to_enrich,),
            daemon=True,
        )
        t.start()

    @staticmethod
    def _run_enrichment_batch(app_db_ids: List[int]) -> None:
        """Run enrichment for a batch of apps in a background thread."""
        from app.database import SessionLocal

        for app_db_id in app_db_ids:
            try:
                RankSpySearchService._enrich_single_app(app_db_id)
            except Exception as e:
                logger.warning(f"[RankSpy] Enrichment failed for app {app_db_id}: {e}")
            finally:
                _mark_enrichment_done(app_db_id)

    @staticmethod
    def _enrich_single_app(app_db_id: int) -> None:
        """Full enrichment pipeline for a single app."""
        from app.database import SessionLocal
        from app.models.models import App

        db = SessionLocal()
        try:
            app = db.query(App).filter(App.id == app_db_id).first()
            if not app:
                return

            store_id = app.app_id
            db.close()

            # Step 1: Full scrape (metadata + reviews + versions)
            from app.services.post_import_hydration import PostImportHydrationService
            hydrator = PostImportHydrationService()
            hydrator.hydrate(app_db_id, store_id)

            logger.info(f"[RankSpy] Enrichment complete for app {app_db_id}")
        except Exception as e:
            logger.warning(f"[RankSpy] Enrichment error for app {app_db_id}: {e}")
        finally:
            try:
                db.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_response(query: str) -> Dict:
        return {
            "query": query or "",
            "results": [],
            "total": 0,
            "tracked_count": 0,
            "discovered_count": 0,
            "has_appstore_results": False,
            "error_hint": None,
        }
