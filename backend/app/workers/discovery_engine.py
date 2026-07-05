"""
Large-scale App Store Discovery Engine.

Discovers app IDs via four complementary sources and feeds them into a
persistent queue (discovery_queue table) for background full scraping:

  1. Top charts  — all chart types × all 21 genre categories × 20 countries
  2. Keywords    — 100+ broad keywords via iTunes Search API
  3. Developer   — all other apps published by each already-known developer
  4. Related     — apps surfaced via iTunes artist/software lookup

Discovery is chunked and resumable: progress is tracked in discovery_progress
so each (chart, category, country) and keyword combination is only re-fetched
once per day, and the system picks up where it stopped after a restart.

The queue processor scrapes full details (metadata + versions + reviews) for
every queued app in priority order: newer + higher-priority apps first.
"""

import asyncio
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from app.services.apple_http_client import apple_fetch_json, ITUNES_SEARCH_URL, ITUNES_LOOKUP_URL

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.models import App, DiscoveryProgress, DiscoveryQueue

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Discovery sources configuration
# ---------------------------------------------------------------------------

# All 21 Apple App Store genre IDs
ALL_GENRE_IDS: dict = {
    "productivity":      "6007",
    "utilities":         "6002",
    "finance":           "6015",
    "games":             "6014",
    "health-fitness":    "6013",
    "education":         "6017",
    "entertainment":     "6016",
    "social-networking": "6005",
    "music":             "6011",
    "photo-video":       "6008",
    "travel":            "6003",
    "news":              "6009",
    "sports":            "6004",
    "lifestyle":         "6012",
    "business":          "6000",
    "medical":           "6020",
    "food-drink":        "6023",
    "reference":         "6006",
    "navigation":        "6010",
    "weather":           "6001",
    "books":             "6018",
}

# iTunes RSS chart slugs
ALL_CHART_SLUGS = [
    "topfreeapplications",
    "toppaidapplications",
    "topgrossingapplications",
]

# 20 major App Store storefronts
DISCOVERY_COUNTRIES = [
    "us", "gb", "au", "ca", "de", "fr", "jp", "kr",
    "in", "br", "mx", "es", "it", "nl", "sg", "se",
    "za", "ar", "ru", "cn",
]

# 100+ keywords covering every major App Store vertical
DISCOVERY_KEYWORDS = [
    # Productivity / utilities
    "productivity", "todo list", "task manager", "notes", "calendar",
    "reminder", "time tracker", "habit tracker", "planner", "focus timer",
    "pomodoro", "checklist", "journal", "daily planner", "goal tracker",
    # AI / tech
    "ai assistant", "chatgpt", "ai chat", "artificial intelligence",
    "ai writer", "ai photo editor", "voice ai", "ai summarizer",
    "ai tool", "chat bot",
    # Social / communication
    "social media", "messaging", "video call", "dating", "friends app",
    "anonymous chat", "group chat", "community",
    # Finance
    "budget", "expense tracker", "investment", "crypto", "stock market",
    "banking", "savings", "money manager", "financial planning",
    "invoice", "accounting", "receipt scanner",
    # Health / fitness
    "workout", "gym", "running", "yoga", "meditation", "sleep tracker",
    "diet", "weight loss", "mental health", "therapy", "calories",
    "step counter", "heart rate", "blood pressure",
    # Education
    "language learning", "math", "coding", "kids learning", "flashcards",
    "quiz", "study", "ebook reader", "online course", "tutor",
    # Entertainment
    "puzzle game", "word game", "trivia", "strategy game", "arcade",
    "music player", "video editor", "photo editor", "drawing",
    "streaming", "podcast player",
    # Lifestyle
    "recipe", "cooking", "food delivery", "travel", "hotel", "flight",
    "weather", "news", "shopping", "fashion", "beauty",
    # Business / tools
    "crm", "project management", "team collaboration", "email",
    "pdf editor", "scanner", "vpn", "password manager", "cloud storage",
    "file manager",
    # Kids / family
    "kids app", "children", "toddler", "baby", "parenting",
    "period tracker", "pregnancy",
    # Sports
    "football", "basketball", "soccer", "baseball", "tennis", "golf",
    "cycling", "swimming",
    # Religion / lifestyle
    "bible", "prayer", "church", "meditation",
    # Other high-volume
    "audiobook", "ebook", "news reader", "video downloader",
    "screen recorder", "alarm clock", "flashlight", "calculator",
    "unit converter", "translator", "dictionary",
    # AI & emerging tech
    "ai productivity", "ai image generator", "stable diffusion", "midjourney",
    "text to image", "ai video", "ai music", "ai code", "copilot", "llm",
    "ai notes", "ai journal", "ai fitness", "ai diet", "ai tutor",
    "ai language", "ai therapy", "ai companion", "ai dating", "ai coach",
    "smart home", "iot", "ar app", "augmented reality", "virtual reality",
    # Mental health & wellness
    "anxiety app", "depression help", "stress relief", "mindfulness",
    "breathing exercise", "panic attack", "ptsd", "self care", "burnout",
    "emotional wellness", "gratitude journal", "mood tracker", "cbt app",
    "adhd planner", "autism app", "adhd focus", "executive function",
    # Creator tools
    "content creator", "influencer", "tiktok tools", "instagram analytics",
    "youtube tools", "shorts editor", "reel maker", "thumbnail maker",
    "caption generator", "hashtag generator", "social media scheduler",
    "link in bio", "creator monetization", "newsletter", "substack",
    # Niche fitness
    "hiit workout", "pilates app", "crossfit", "calisthenics", "stretching",
    "flexibility", "posture corrector", "back pain", "physical therapy",
    "sports nutrition", "protein tracker", "macro calculator", "fasting app",
    "intermittent fasting", "keto diet", "vegan tracker", "water reminder",
    # Finance & crypto
    "defi", "nft", "web3", "bitcoin wallet", "ethereum", "portfolio tracker",
    "options trading", "forex", "day trading", "dividend tracker",
    "tax calculator", "tax filing", "real estate investment", "peer lending",
    "savings challenge", "debt payoff", "net worth tracker", "fire calculator",
    # Gaming niches
    "idle game", "clicker game", "roguelike", "tower defense", "city builder",
    "survival game", "horror game", "escape room", "visual novel", "rpg",
    "card game", "board game", "chess", "sudoku", "crossword", "wordle",
    "math game", "brain training", "memory game",
    # Productivity niches
    "second brain", "pkm", "zettelkasten", "obsidian", "notion alternative",
    "kanban", "gtd app", "inbox zero", "deep work", "time blocking",
    "digital detox", "screen time", "focus mode", "distraction blocker",
    # Niche lifestyle
    "plant care", "garden app", "pet tracker", "dog training", "cat app",
    "astrology", "horoscope", "tarot", "numerology", "manifestation",
    "vision board", "affirmations", "law of attraction", "journaling app",
    "dream journal", "sleep sounds", "white noise", "meditation timer",
    # Travel & local
    "travel planner", "trip organizer", "packing list", "currency converter",
    "language translator offline", "offline maps", "local guide", "yelp alternative",
    "restaurant finder", "happy hour", "bar app", "nightlife",
]

# ---------------------------------------------------------------------------
# Mass keyword list — 1000+ long-tail terms for Phase 2+ discovery
# ---------------------------------------------------------------------------

def _build_mass_keywords() -> List[str]:
    """
    Generate 1000+ long-tail search terms from base keywords + modifiers.
    Called once at module load; result cached as MASS_KEYWORDS constant.
    """
    base = DISCOVERY_KEYWORDS
    modifiers = ["app", "tracker", "best", "free", "2024", "planner", "tool"]
    seen: set = set(base)
    result: List[str] = list(base)
    for kw in base:
        for mod in modifiers:
            term = f"{kw} {mod}"
            if term not in seen:
                seen.add(term)
                result.append(term)
    return result


MASS_KEYWORDS: List[str] = _build_mass_keywords()

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DiscoveryEngine:
    """
    Orchestrates large-scale App Store app ID discovery and queue management.

    Usage (via scheduler jobs):
        engine = DiscoveryEngine(db)
        await engine.run_chart_discovery_batch(batch_size=10)
        await engine.run_keyword_discovery()
        await engine.run_developer_expansion()
        n = await engine.process_queue(batch_size=25)
    """

    def __init__(self, db: Session):
        self.db = db

    # -----------------------------------------------------------------------
    # Queue helpers
    # -----------------------------------------------------------------------

    def enqueue(
        self,
        app_ids: List[str],
        source: str,
        priority: int = 0,
        enrich_mode: str = "full",
    ) -> int:
        """
        Add new app IDs to the discovery queue.
        Deduplicates against both the apps table and the existing queue.
        Returns the count of IDs newly added.

        enrich_mode: 'full' (default) or 'light' — stored on the queue row so
        the processor knows whether to call scrape_light_details or scrape_app_full_details.
        """
        if not app_ids:
            return 0

        # Dedup against apps table; the queue itself is handled by
        # ON CONFLICT DO NOTHING (app_id is unique) so a concurrent
        # discovery job can't poison the whole batch with IntegrityError.
        existing_apps: set = {
            row[0]
            for row in self.db.query(App.app_id).filter(App.app_id.in_(app_ids)).all()
        }
        new_ids = [aid for aid in app_ids if aid not in existing_apps]
        if not new_ids:
            return 0

        stmt = (
            pg_insert(DiscoveryQueue.__table__)
            .values([
                {
                    "app_id": aid,
                    "source": source,
                    "priority": priority,
                    "status": "pending",
                    "enrich_mode": enrich_mode,
                }
                for aid in new_ids
            ])
            .on_conflict_do_nothing(index_elements=["app_id"])
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount or 0

    def _get_progress(self, key: str) -> Optional[DiscoveryProgress]:
        return (
            self.db.query(DiscoveryProgress)
            .filter(DiscoveryProgress.source_key == key)
            .first()
        )

    def _mark_progress(self, key: str, apps_found: int) -> None:
        prog = self._get_progress(key)
        if prog:
            prog.apps_found += apps_found
            prog.last_run = datetime.now(timezone.utc)
        else:
            prog = DiscoveryProgress(
                source_key=key,
                apps_found=apps_found,
                last_run=datetime.now(timezone.utc),
            )
            self.db.add(prog)
        self.db.commit()

    def _ran_today(self, key: str) -> bool:
        prog = self._get_progress(key)
        if not prog or not prog.last_run:
            return False
        return prog.last_run.date() >= datetime.now(timezone.utc).date()

    # -----------------------------------------------------------------------
    # Sync fetch helpers (always run via asyncio.to_thread)
    # -----------------------------------------------------------------------

    @staticmethod
    def _fetch_chart(chart_slug: str, genre_id: Optional[str], country: str) -> List[str]:
        """Fetch iTunes RSS chart → list of app_id strings (up to 200)."""
        if genre_id:
            url = (
                f"https://itunes.apple.com/{country}/rss/{chart_slug}"
                f"/limit=200/genre={genre_id}/json"
            )
        else:
            url = f"https://itunes.apple.com/{country}/rss/{chart_slug}/limit=200/json"
        try:
            data = apple_fetch_json(url, timeout=20)
            if not data:
                return []
            entries = data.get("feed", {}).get("entry", [])
            return [
                str(e["id"]["attributes"]["im:id"])
                for e in entries
                if e.get("id", {}).get("attributes", {}).get("im:id")
            ]
        except Exception as exc:
            logger.warning(f"[DISC] Chart {chart_slug}/{genre_id}/{country} failed: {exc}")
            return []

    @staticmethod
    def _fetch_keyword(keyword: str) -> List[str]:
        """iTunes Search API → list of app_id strings (up to 200)."""
        try:
            data = apple_fetch_json(
                ITUNES_SEARCH_URL,
                params={"term": keyword, "entity": "software", "limit": 200, "country": "us"},
                timeout=15,
            )
            if not data:
                return []
            return [
                str(r["trackId"])
                for r in data.get("results", [])
                if r.get("trackId")
            ]
        except Exception as exc:
            logger.warning(f"[DISC] Keyword '{keyword}' failed: {exc}")
            return []

    @staticmethod
    def _fetch_keyword_with_dates(keyword: str) -> List[dict]:
        """iTunes Search API → list of {app_id, release_date} dicts (up to 200).

        Returns release_date as a datetime object when available, so the
        caller can assign higher queue priority to recently released apps.
        """
        try:
            data = apple_fetch_json(
                ITUNES_SEARCH_URL,
                params={"term": keyword, "entity": "software", "limit": 200, "country": "us"},
                timeout=15,
            )
            if not data:
                return []
            results = []
            for r in data.get("results", []):
                if not r.get("trackId"):
                    continue
                rd = None
                raw_date = r.get("releaseDate") or r.get("currentVersionReleaseDate")
                if raw_date:
                    try:
                        rd = datetime.fromisoformat(raw_date.rstrip("Z"))
                    except Exception:
                        pass
                results.append({"app_id": str(r["trackId"]), "release_date": rd})
            return results
        except Exception as exc:
            logger.warning(f"[DISC] Keyword '{keyword}' (with dates) failed: {exc}")
            return []

    @staticmethod
    def _fetch_keyword_with_dates_rich(keyword: str) -> List[dict]:
        """
        iTunes Search API → list of rich info dicts (up to 200).

        Like _fetch_keyword_with_dates but returns the full iTunes result
        dict fields needed for light_insert_batch:
          app_id, release_date, current_rank (None for keyword results),
          developer_id, icon_url, primary_category, is_free, price,
          current_rating, current_reviews (userRatingCount), name, developer.

        Single HTTP call — no extra API cost vs the basic version.
        """
        try:
            data = apple_fetch_json(
                ITUNES_SEARCH_URL,
                params={"term": keyword, "entity": "software", "limit": 200, "country": "us"},
                timeout=15,
            )
            if not data:
                return []
            results = []
            for r in data.get("results", []):
                if not r.get("trackId"):
                    continue
                rd = None
                raw_date = r.get("releaseDate") or r.get("currentVersionReleaseDate")
                if raw_date:
                    try:
                        rd = datetime.fromisoformat(raw_date.rstrip("Z"))
                    except Exception:
                        pass
                results.append({
                    "app_id": str(r["trackId"]),
                    "release_date": rd,
                    "current_rank": None,  # keyword search results have no chart rank
                    "name": r.get("trackName", ""),
                    "developer": r.get("artistName", ""),
                    "developer_id": str(r["artistId"]) if r.get("artistId") else None,
                    "icon_url": r.get("artworkUrl512") or r.get("artworkUrl100") or r.get("artworkUrl60"),
                    "primary_category": r.get("primaryGenreName"),
                    "is_free": r.get("price", 0) == 0,
                    "price": r.get("price", 0.0),
                    "current_rating": r.get("averageUserRating"),
                    "current_reviews": r.get("userRatingCount", 0),
                    "url": r.get("trackViewUrl"),
                })
            return results
        except Exception as exc:
            logger.warning(f"[DISC] Keyword '{keyword}' (rich) failed: {exc}")
            return []

    @staticmethod
    def _freshness_priority(release_date: Optional[datetime]) -> int:
        """Map a release_date to a queue priority level.

        Very fresh apps get priority=5 so they jump to the front of the
        scrape queue — they're most likely to generate useful signals.

        Priority scale:
          5 = released <30 days  (very high / fresh)
          4 = released <90 days  (medium / recent)
          2 = older / unknown    (normal keyword priority)
        """
        if not release_date:
            return 2
        rd = release_date.replace(tzinfo=None) if release_date.tzinfo else release_date
        age_days = (datetime.utcnow() - rd).days
        if age_days < 0:
            return 5
        if age_days < 30:
            return 5
        if age_days < 90:
            return 4
        return 2

    @staticmethod
    def _fetch_developer_apps(developer_id: str) -> List[str]:
        """iTunes artist lookup → all app IDs by that developer (up to 200)."""
        try:
            data = apple_fetch_json(
                ITUNES_LOOKUP_URL,
                params={"id": developer_id, "entity": "software", "limit": 200},
                timeout=15,
            )
            if not data:
                return []
            return [
                str(r["trackId"])
                for r in data.get("results", [])
                if r.get("trackId") and r.get("wrapperType") == "software"
            ]
        except Exception as exc:
            logger.warning(f"[DISC] Developer {developer_id} lookup failed: {exc}")
            return []

    # -----------------------------------------------------------------------
    # Light insert (two-speed pipeline)
    # -----------------------------------------------------------------------

    def light_insert_batch(self, app_infos: List[dict]) -> int:
        """
        Bulk-insert new apps from keyword/chart discovery without fetching full
        details.  Sets ingestion_stage='light' so the tiering + enrichment jobs
        know to come back and complete the scrape.

        Deduplicates against the apps table in a single query.
        Uses ON CONFLICT DO NOTHING so concurrent inserts are safe.

        Returns count of rows inserted.
        """
        if not app_infos:
            return 0

        from app.workers.tasks import _compute_freshness_score

        # Dedup: find which app_ids already exist
        candidate_ids = [str(info["app_id"]) for info in app_infos if info.get("app_id")]
        if not candidate_ids:
            return 0

        existing: set = {
            row[0]
            for row in self.db.query(App.app_id).filter(App.app_id.in_(candidate_ids)).all()
        }

        rows = []
        for info in app_infos:
            aid = str(info.get("app_id", ""))
            if not aid or aid in existing:
                continue

            rd = info.get("release_date")
            freshness = _compute_freshness_score(rd) if rd else 0.0

            rows.append({
                "app_id": aid,
                "name": info.get("name") or "Unknown",
                "developer": info.get("developer"),
                "developer_id": info.get("developer_id"),
                "icon_url": info.get("icon_url"),
                "primary_category": info.get("primary_category"),
                "is_free": bool(info.get("is_free", True)),
                "price": float(info.get("price") or 0.0),
                "current_rating": info.get("current_rating"),
                "current_reviews": int(info.get("current_reviews") or 0),
                "current_rank": info.get("current_rank"),
                "release_date": rd,
                "url": info.get("url"),
                "freshness_score": freshness,
                "ingestion_stage": "light",
                "sync_tier": "warm",
            })

        if not rows:
            return 0

        try:
            stmt = pg_insert(App.__table__).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["app_id"])
            result = self.db.execute(stmt)
            self.db.commit()
            inserted = result.rowcount if result.rowcount >= 0 else len(rows)
            logger.info(f"[DISC] light_insert_batch: {inserted}/{len(rows)} new rows inserted")
            return inserted
        except Exception as exc:
            logger.error(f"[DISC] light_insert_batch failed: {exc}")
            self.db.rollback()
            return 0

    async def run_mass_keyword_discovery(self, keywords: List[str]) -> dict:
        """
        Run keyword discovery for a large list of keywords using the rich
        iTunes result dict + pre-filter → light insert pipeline.

        Returns {discovered, filtered_out, inserted}.
        """
        from app.services.pre_filter_service import PreFilterService

        pre_filter = PreFilterService()
        total_discovered = 0
        total_filtered_out = 0
        total_inserted = 0

        for kw in keywords:
            try:
                raw = await asyncio.to_thread(self._fetch_keyword_with_dates_rich, kw)
                total_discovered += len(raw)

                passing = pre_filter.filter_batch(raw)
                total_filtered_out += len(raw) - len(passing)

                if passing:
                    inserted = await asyncio.to_thread(self.light_insert_batch, passing)
                    total_inserted += inserted

                await asyncio.sleep(0.3)
            except Exception as exc:
                logger.warning(f"[DISC] mass keyword '{kw}' failed: {exc}")

        logger.info(
            f"[DISC] run_mass_keyword_discovery: {total_discovered} discovered, "
            f"{total_filtered_out} filtered out, {total_inserted} inserted"
        )
        return {
            "discovered": total_discovered,
            "filtered_out": total_filtered_out,
            "inserted": total_inserted,
        }

    def _enqueue_light_apps_for_tier(self, tier: str, limit: int) -> int:
        """
        Find apps with ingestion_stage='light' and sync_tier=tier that are not
        already in the discovery queue (any status), and enqueue them for full
        enrichment.

        Priority: HOT=5, WARM=2, COLD=0
        Returns count of items enqueued.
        """
        priority_map = {"hot": 5, "warm": 2, "cold": 0}
        priority = priority_map.get(tier, 0)

        # Use NOT EXISTS subquery instead of loading all queue IDs into memory
        from sqlalchemy import exists

        queued_subq = (
            self.db.query(DiscoveryQueue.app_id)
            .filter(DiscoveryQueue.app_id == App.app_id)
            .exists()
        )

        candidates = (
            self.db.query(App.app_id)
            .filter(
                App.ingestion_stage == "light",
                App.sync_tier == tier,
                ~queued_subq,
            )
            .limit(limit)
            .all()
        )

        new_ids = [row[0] for row in candidates]

        if not new_ids:
            return 0

        count = 0
        for aid in new_ids:
            self.db.add(DiscoveryQueue(
                app_id=aid,
                source=f"tier_enrich:{tier}",
                priority=priority,
                status="pending",
                enrich_mode="full",
            ))
            count += 1

        if count:
            self.db.commit()

        logger.info(f"[DISC] _enqueue_light_apps_for_tier({tier}): {count} enqueued")
        return count

    # -----------------------------------------------------------------------
    # Discovery phases
    # -----------------------------------------------------------------------

    def _process_chart_sync(
        self, chart: str, genre_id: Optional[str], country: str
    ) -> tuple:
        """
        All DB + HTTP work for one chart combo.
        Returns (key, ids_found, new_queued, did_work).
        did_work=False means already ran today — caller should skip sleep/counter.
        Safe to call via asyncio.to_thread — keeps self.db access off event loop.
        """
        key = f"chart:{chart}:{country}:{'all' if genre_id is None else genre_id}"
        if self._ran_today(key):
            return key, 0, 0, False
        ids = self._fetch_chart(chart, genre_id, country)
        new = self.enqueue(ids, source=key, priority=1)
        self._mark_progress(key, new)
        return key, len(ids), new, True

    async def run_chart_discovery_batch(self, batch_size: int = 10) -> int:
        """
        Fetch the next `batch_size` (chart × genre × country) combinations
        not yet run today, enqueue discovered app IDs.
        Returns total new IDs enqueued.
        """
        total_new = 0
        processed = 0

        for chart in ALL_CHART_SLUGS:
            for country in DISCOVERY_COUNTRIES:
                # All-genres chart for this country
                key, found, new, did_work = await asyncio.to_thread(
                    self._process_chart_sync, chart, None, country
                )
                if did_work:
                    total_new += new
                    processed += 1
                    logger.info(f"[DISC] {key}: {found} found, {new} queued")
                    await asyncio.sleep(0.3)
                    if processed >= batch_size:
                        return total_new

                # Per-genre charts
                for slug, genre_id in ALL_GENRE_IDS.items():
                    key, found, new, did_work = await asyncio.to_thread(
                        self._process_chart_sync, chart, genre_id, country
                    )
                    if did_work:
                        total_new += new
                        processed += 1
                        logger.info(f"[DISC] {key}: {found} found, {new} queued")
                        await asyncio.sleep(0.3)
                        if processed >= batch_size:
                            return total_new

        return total_new

    def _process_keyword_sync(self, kw: str) -> int:
        """
        All DB + HTTP work for one keyword.
        Returns count of new app IDs queued, or 0 if already ran today.
        Safe to call via asyncio.to_thread — keeps self.db access off event loop.
        """
        key = f"keyword:{kw}"
        if self._ran_today(key):
            return 0
        app_infos = self._fetch_keyword_with_dates(kw)
        new = 0
        for info in app_infos:
            prio = self._freshness_priority(info["release_date"])
            new += self.enqueue([info["app_id"]], source=key, priority=prio)
        self._mark_progress(key, new)
        fresh_count = sum(
            1 for i in app_infos
            if i["release_date"] and
            (datetime.utcnow() - (i["release_date"].replace(tzinfo=None) if i["release_date"].tzinfo else i["release_date"])).days < 30
        )
        logger.info(
            f"[DISC] keyword '{kw}': {len(app_infos)} found, "
            f"{new} queued ({fresh_count} fresh <30d)"
        )
        return new

    async def run_keyword_discovery(self) -> int:
        """
        Run keyword search for all DISCOVERY_KEYWORDS not yet run today.
        Assigns per-app queue priority based on release_date freshness:
          priority=5 (fresh <30d) | 4 (recent <90d) | 2 (older/unknown)
        Returns total new IDs enqueued.
        """
        total_new = 0
        for kw in DISCOVERY_KEYWORDS:
            new = await asyncio.to_thread(self._process_keyword_sync, kw)
            total_new += new
            await asyncio.sleep(0.2)
        return total_new

    def _process_developer_sync(
        self, developer_id: str, developer_name: str
    ) -> tuple:
        """
        All DB + HTTP work for one developer.
        Returns (new_queued, already_done).
        Safe to call via asyncio.to_thread — keeps self.db access off event loop.
        """
        key = f"developer:{developer_id}"
        if self._get_progress(key):
            return 0, True  # already expanded
        ids = self._fetch_developer_apps(developer_id)
        new = self.enqueue(ids, source=key, priority=1)
        self._mark_progress(key, new)
        logger.info(
            f"[DISC] developer {developer_name} ({developer_id}): "
            f"{len(ids)} found, {new} queued"
        )
        return new, False

    async def run_developer_expansion(self, limit: int = 50) -> int:
        """
        For recently added apps with a developer_id not yet expanded,
        fetch all other apps by that developer and enqueue them.
        Returns total new IDs enqueued.
        """
        # Fetch candidate apps list off the event loop
        apps = await asyncio.to_thread(
            lambda: (
                self.db.query(App)
                .filter(App.developer_id.isnot(None), App.developer_id != "")
                .order_by(App.created_at.desc())
                .limit(limit * 3)
                .all()
            )
        )

        seen_devs: set = set()
        expanded = 0
        total_new = 0
        for app in apps:
            if not app.developer_id or app.developer_id in seen_devs:
                continue
            seen_devs.add(app.developer_id)

            new, already_done = await asyncio.to_thread(
                self._process_developer_sync, app.developer_id, app.developer or ""
            )
            if already_done:
                continue
            total_new += new
            expanded += 1
            await asyncio.sleep(0.2)
            if expanded >= limit:
                break

        return total_new

    # -----------------------------------------------------------------------
    # Queue processor
    # -----------------------------------------------------------------------

    async def process_queue(
        self,
        batch_size: int = 100,
        concurrency: int = 10,
        tier: Optional[str] = None,
    ) -> int:
        """
        Pick up to `batch_size` pending items from the discovery queue,
        scrape details concurrently (up to `concurrency` workers), persist
        to the apps table, mark done.

        Parameters
        ----------
        batch_size  : max items to claim per call (default 100)
        concurrency : max simultaneous scrape coroutines (default 10)
        tier        : optional filter — only process items whose source
                      contains f"tier_enrich:{tier}" (HOT/WARM/COLD enrichment jobs)

        Ordering: higher priority first, then newest added_at.
        Routes each item to scrape_light_details or scrape_app_full_details
        based on the item.enrich_mode column (default 'full').

        Returns number of apps successfully scraped.
        """
        from app.workers.tasks import ScraperWorker
        from app.database import SessionLocal

        # Reap stale claims: rows stuck in 'scraping' (job timed out or the
        # container restarted mid-batch) would otherwise never be retried.
        # processed_at doubles as the claim timestamp (set below).
        from sqlalchemy import or_
        stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        self.db.query(DiscoveryQueue).filter(
            DiscoveryQueue.status == "scraping",
            or_(
                DiscoveryQueue.processed_at.is_(None),  # claimed before claim-stamping existed
                DiscoveryQueue.processed_at < stale_cutoff,
            ),
        ).update({"status": "pending"}, synchronize_session=False)
        self.db.commit()

        query = self.db.query(DiscoveryQueue).filter(DiscoveryQueue.status == "pending")
        if tier:
            query = query.filter(DiscoveryQueue.source.like(f"%tier_enrich:{tier}%"))
        else:
            # Generic processor must not drain tier-enrichment rows — the
            # enrich_hot/warm/cold jobs own those (prevents double-scraping).
            # NULL-safe: legacy rows with no source must still be processed
            # (SQL `NULL NOT LIKE …` is NULL, which would wrongly exclude them).
            query = query.filter(
                or_(
                    DiscoveryQueue.source.is_(None),
                    ~DiscoveryQueue.source.like("%tier_enrich:%"),
                )
            )

        pending = (
            query
            .order_by(
                DiscoveryQueue.priority.desc(),
                DiscoveryQueue.added_at.desc(),
            )
            .limit(batch_size)
            .with_for_update(skip_locked=True)
            .all()
        )

        if not pending:
            logger.info("[DISC] Queue empty — nothing to process")
            self.db.commit()
            return 0

        # Atomically claim items (rows are locked by the SELECT above until
        # this commit, and concurrent claimers skip locked rows).
        ids_to_claim = [q.id for q in pending]
        self.db.query(DiscoveryQueue).filter(
            DiscoveryQueue.id.in_(ids_to_claim)
        ).update(
            {"status": "scraping", "processed_at": datetime.now(timezone.utc)},
            synchronize_session=False,
        )
        self.db.commit()

        # Cap concurrency to avoid pool exhaustion — each worker needs 1
        # session for scraping + 1 for status update (sequential, not parallel).
        effective_concurrency = min(concurrency, 5)
        semaphore = asyncio.Semaphore(effective_concurrency)
        success_count = 0

        async def _process_one(item: DiscoveryQueue) -> bool:
            """Scrape one item; update queue row status in its own session."""
            async with semaphore:
                mode = item.enrich_mode or "full"
                worker = ScraperWorker()
                await worker.initialize()
                ok = False
                try:
                    if mode == "light":
                        ok = await worker.scrape_light_details(item.app_id)
                        await asyncio.sleep(0.1)
                    else:
                        ok = await worker.scrape_app_full_details(item.app_id)
                        await asyncio.sleep(0.5)
                except Exception as exc:
                    logger.error(f"[DISC] Queue scrape failed {item.app_id}: {exc}")
                finally:
                    # Close worker session BEFORE opening status-update session
                    await worker.cleanup()

                # Update queue row in a dedicated session
                db2 = SessionLocal()
                try:
                    row = db2.query(DiscoveryQueue).filter(DiscoveryQueue.id == item.id).first()
                    if row:
                        if ok:
                            row.status = "done"
                            row.processed_at = datetime.now(timezone.utc)
                        else:
                            row.failed_attempts = (row.failed_attempts or 0) + 1
                            row.status = (
                                "pending" if row.failed_attempts < 3 else "failed"
                            )
                        db2.commit()
                except Exception as exc:
                    logger.error(f"[DISC] Queue status update failed {item.app_id}: {exc}")
                    db2.rollback()
                finally:
                    db2.close()

                return ok

        results = await asyncio.gather(*[_process_one(item) for item in pending])
        success_count = sum(1 for r in results if r)

        logger.info(f"[DISC] Queue batch done: {success_count}/{len(pending)} scraped (concurrency={concurrency})")
        return success_count

    # -----------------------------------------------------------------------
    # Metrics
    # -----------------------------------------------------------------------

    def get_metrics(self) -> dict:
        """Return live discovery queue and DB metrics."""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        yesterday_start = today_start - timedelta(days=1)
        ago_30d = today_start - timedelta(days=30)
        ago_90d = today_start - timedelta(days=90)

        total_apps = self.db.query(App).count()
        new_today = (
            self.db.query(App)
            .filter(App.created_at >= today_start)
            .count()
        )
        new_yesterday = (
            self.db.query(App)
            .filter(App.created_at >= yesterday_start, App.created_at < today_start)
            .count()
        )
        # Apps whose App Store release_date is within the freshness windows
        new_apps_last_30_days = (
            self.db.query(App)
            .filter(App.release_date.isnot(None), App.release_date >= ago_30d)
            .count()
        )
        new_apps_last_90_days = (
            self.db.query(App)
            .filter(App.release_date.isnot(None), App.release_date >= ago_90d)
            .count()
        )

        pending_queue = (
            self.db.query(DiscoveryQueue)
            .filter(DiscoveryQueue.status == "pending")
            .count()
        )
        scraping_queue = (
            self.db.query(DiscoveryQueue)
            .filter(DiscoveryQueue.status == "scraping")
            .count()
        )
        done_queue = (
            self.db.query(DiscoveryQueue)
            .filter(DiscoveryQueue.status == "done")
            .count()
        )
        failed_queue = (
            self.db.query(DiscoveryQueue)
            .filter(DiscoveryQueue.status == "failed")
            .count()
        )
        total_queue = self.db.query(DiscoveryQueue).count()

        sources_scanned = self.db.query(DiscoveryProgress).count()
        sources_today = (
            self.db.query(DiscoveryProgress)
            .filter(DiscoveryProgress.last_run >= today_start)
            .count()
        )

        # Total possible chart sources = charts × genres × countries + all-genre
        total_chart_sources = (
            len(ALL_CHART_SLUGS)
            * len(DISCOVERY_COUNTRIES)
            * (len(ALL_GENRE_IDS) + 1)   # +1 for all-genres
        )
        total_keyword_sources = len(DISCOVERY_KEYWORDS)

        return {
            "total_apps_in_db": total_apps,
            "new_apps_today": new_today,
            "new_apps_yesterday": new_yesterday,
            "new_apps_last_30_days": new_apps_last_30_days,
            "new_apps_last_90_days": new_apps_last_90_days,
            "queue_pending": pending_queue,
            "queue_scraping": scraping_queue,
            "queue_done": done_queue,
            "queue_failed": failed_queue,
            "queue_total": total_queue,
            "sources_scanned_ever": sources_scanned,
            "sources_scanned_today": sources_today,
            "total_chart_source_slots": total_chart_sources,
            "total_keyword_slots": total_keyword_sources,
            "coverage_pct": round(
                min(total_apps / max(total_queue + total_apps, 1) * 100, 100), 1
            ),
        }
