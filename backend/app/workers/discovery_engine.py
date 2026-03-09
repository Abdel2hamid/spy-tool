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
import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

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
]

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_UA = "Mozilla/5.0 (compatible; AppStoreCrawler/2.0)"


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

    def enqueue(self, app_ids: List[str], source: str, priority: int = 0) -> int:
        """
        Add new app IDs to the discovery queue.
        Deduplicates against both the apps table and the existing queue.
        Returns the count of IDs newly added.
        """
        if not app_ids:
            return 0

        # Single-query dedup against both tables
        existing_apps: set = {
            row[0]
            for row in self.db.query(App.app_id).filter(App.app_id.in_(app_ids)).all()
        }
        existing_queue: set = {
            row[0]
            for row in self.db.query(DiscoveryQueue.app_id)
            .filter(DiscoveryQueue.app_id.in_(app_ids))
            .all()
        }

        new_ids = [
            aid for aid in app_ids
            if aid not in existing_apps and aid not in existing_queue
        ]

        count = 0
        for aid in new_ids:
            self.db.add(DiscoveryQueue(
                app_id=aid,
                source=source,
                priority=priority,
                status="pending",
            ))
            count += 1

        if count:
            self.db.commit()

        return count

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
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
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
            encoded = urllib.parse.quote(keyword)
            url = (
                f"https://itunes.apple.com/search"
                f"?term={encoded}&entity=software&limit=200&country=us"
            )
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return [
                str(r["trackId"])
                for r in data.get("results", [])
                if r.get("trackId")
            ]
        except Exception as exc:
            logger.warning(f"[DISC] Keyword '{keyword}' failed: {exc}")
            return []

    @staticmethod
    def _fetch_developer_apps(developer_id: str) -> List[str]:
        """iTunes artist lookup → all app IDs by that developer (up to 200)."""
        try:
            url = (
                f"https://itunes.apple.com/lookup"
                f"?id={developer_id}&entity=software&limit=200"
            )
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return [
                str(r["trackId"])
                for r in data.get("results", [])
                if r.get("trackId") and r.get("wrapperType") == "software"
            ]
        except Exception as exc:
            logger.warning(f"[DISC] Developer {developer_id} lookup failed: {exc}")
            return []

    # -----------------------------------------------------------------------
    # Discovery phases
    # -----------------------------------------------------------------------

    async def run_chart_discovery_batch(self, batch_size: int = 10) -> int:
        """
        Fetch the next `batch_size` (chart × genre × country) combinations
        not yet run today, enqueue discovered app IDs.
        Returns total new IDs enqueued.
        """
        today = datetime.now(timezone.utc).date()
        total_new = 0
        processed = 0

        for chart in ALL_CHART_SLUGS:
            for country in DISCOVERY_COUNTRIES:
                # All-genres chart for this country
                key_all = f"chart:{chart}:{country}:all"
                if not self._ran_today(key_all):
                    ids = await asyncio.to_thread(
                        self._fetch_chart, chart, None, country
                    )
                    new = self.enqueue(ids, source=key_all, priority=1)
                    self._mark_progress(key_all, new)
                    total_new += new
                    processed += 1
                    logger.info(
                        f"[DISC] {key_all}: {len(ids)} found, {new} queued"
                    )
                    await asyncio.sleep(0.3)
                    if processed >= batch_size:
                        return total_new

                # Per-genre charts
                for slug, genre_id in ALL_GENRE_IDS.items():
                    key = f"chart:{chart}:{country}:{genre_id}"
                    if not self._ran_today(key):
                        ids = await asyncio.to_thread(
                            self._fetch_chart, chart, genre_id, country
                        )
                        new = self.enqueue(ids, source=key, priority=1)
                        self._mark_progress(key, new)
                        total_new += new
                        processed += 1
                        logger.info(
                            f"[DISC] {key}: {len(ids)} found, {new} queued"
                        )
                        await asyncio.sleep(0.3)
                        if processed >= batch_size:
                            return total_new

        return total_new

    async def run_keyword_discovery(self) -> int:
        """
        Run keyword search for all DISCOVERY_KEYWORDS not yet run today.
        Keywords get priority=2 (higher than charts) because search results
        are most aligned with what users are actually looking for.
        Returns total new IDs enqueued.
        """
        total_new = 0
        for kw in DISCOVERY_KEYWORDS:
            key = f"keyword:{kw}"
            if self._ran_today(key):
                continue
            ids = await asyncio.to_thread(self._fetch_keyword, kw)
            new = self.enqueue(ids, source=key, priority=2)
            self._mark_progress(key, new)
            total_new += new
            logger.info(f"[DISC] keyword '{kw}': {len(ids)} found, {new} queued")
            await asyncio.sleep(0.2)
        return total_new

    async def run_developer_expansion(self, limit: int = 50) -> int:
        """
        For recently added apps with a developer_id not yet expanded,
        fetch all other apps by that developer and enqueue them.
        Returns total new IDs enqueued.
        """
        total_new = 0
        # Get recently added apps with a developer_id
        apps = (
            self.db.query(App)
            .filter(App.developer_id.isnot(None), App.developer_id != "")
            .order_by(App.created_at.desc())
            .limit(limit * 3)   # fetch extra so we can dedup seen devs
            .all()
        )

        seen_devs: set = set()
        expanded = 0
        for app in apps:
            if not app.developer_id or app.developer_id in seen_devs:
                continue
            seen_devs.add(app.developer_id)

            key = f"developer:{app.developer_id}"
            if self._get_progress(key):
                continue  # already expanded this developer

            ids = await asyncio.to_thread(
                self._fetch_developer_apps, app.developer_id
            )
            new = self.enqueue(ids, source=key, priority=1)
            self._mark_progress(key, new)
            total_new += new
            expanded += 1
            logger.info(
                f"[DISC] developer {app.developer} ({app.developer_id}): "
                f"{len(ids)} found, {new} queued"
            )
            await asyncio.sleep(0.2)
            if expanded >= limit:
                break

        return total_new

    # -----------------------------------------------------------------------
    # Queue processor
    # -----------------------------------------------------------------------

    async def process_queue(self, batch_size: int = 25) -> int:
        """
        Pick up to `batch_size` pending items from the discovery queue,
        scrape full details, persist to the apps table, mark done.

        Ordering: higher priority first, then oldest added_at (FIFO within
        the same priority so newest keyword hits are processed before old
        chart entries, but within a priority class oldest wins to prevent
        starvation).

        Returns number of apps successfully scraped.
        """
        from app.workers.tasks import ScraperWorker

        pending = (
            self.db.query(DiscoveryQueue)
            .filter(DiscoveryQueue.status == "pending")
            .order_by(
                DiscoveryQueue.priority.desc(),
                DiscoveryQueue.added_at.asc(),
            )
            .limit(batch_size)
            .all()
        )

        if not pending:
            logger.info("[DISC] Queue empty — nothing to process")
            return 0

        # Atomically claim items
        ids_to_claim = [q.id for q in pending]
        self.db.query(DiscoveryQueue).filter(
            DiscoveryQueue.id.in_(ids_to_claim)
        ).update({"status": "scraping"}, synchronize_session=False)
        self.db.commit()

        worker = ScraperWorker()
        await worker.initialize()
        success = 0

        try:
            for item in pending:
                try:
                    ok = await worker.scrape_app_full_details(item.app_id)
                    if ok:
                        item.status = "done"
                        item.processed_at = datetime.now(timezone.utc)
                        success += 1
                    else:
                        item.failed_attempts = (item.failed_attempts or 0) + 1
                        item.status = (
                            "pending" if item.failed_attempts < 3 else "failed"
                        )
                except Exception as exc:
                    item.failed_attempts = (item.failed_attempts or 0) + 1
                    item.status = (
                        "pending" if item.failed_attempts < 3 else "failed"
                    )
                    logger.error(
                        f"[DISC] Queue scrape failed {item.app_id}: {exc}"
                    )
                self.db.commit()
                await asyncio.sleep(0.5)
        finally:
            await worker.cleanup()

        logger.info(f"[DISC] Queue batch done: {success}/{len(pending)} scraped")
        return success

    # -----------------------------------------------------------------------
    # Metrics
    # -----------------------------------------------------------------------

    def get_metrics(self) -> dict:
        """Return live discovery queue and DB metrics."""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        yesterday_start = today_start - timedelta(days=1)

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
