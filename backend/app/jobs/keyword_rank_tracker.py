"""
Keyword Rank Tracker Job
========================
For each tracked Keyword in the DB:
  1. Run App Store search scraper (Playwright)
  2. Save top-20 results to keyword_search_snapshots
  3. Update AppKeyword.position from organic results
  4. Log structured metrics

Max 50 keywords per run (configurable).
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import App, AppKeyword, Keyword, KeywordSearchSnapshot
from app.scrapers.appstore_search_scraper import AppStoreSearchScraper

logger = logging.getLogger(__name__)

MAX_KEYWORDS_PER_RUN = 50
MAX_RESULTS_PER_KEYWORD = 20
SCRAPE_CONCURRENCY = 2   # parallel browser tabs


class KeywordRankTracker:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        country: str = "us",
        keyword_limit: int = MAX_KEYWORDS_PER_RUN,
        custom_keywords: Optional[List[str]] = None,
    ) -> dict:
        """
        Run a full keyword rank-tracking scan.
        Returns a summary dict with counts.
        """
        t0 = time.monotonic()

        if custom_keywords:
            keywords_to_scan = custom_keywords[:keyword_limit]
        else:
            keywords_to_scan = self._get_tracked_keywords(keyword_limit)

        if not keywords_to_scan:
            logger.info("[rank_tracker] No keywords to scan")
            return {
                "keywords_scanned": 0,
                "total_results": 0,
                "sponsored_results": 0,
                "elapsed_seconds": 0.0,
            }

        logger.info(
            f"[rank_tracker] Starting scan: {len(keywords_to_scan)} keywords, "
            f"country={country}, concurrency={SCRAPE_CONCURRENCY}"
        )

        total_results = 0
        sponsored_results = 0

        async with AppStoreSearchScraper() as scraper:
            all_search_data = await scraper.search_many(
                keywords=keywords_to_scan,
                country=country,
                max_results=MAX_RESULTS_PER_KEYWORD,
                concurrency=SCRAPE_CONCURRENCY,
            )

        for search_data in all_search_data:
            keyword = search_data["keyword"]
            results = search_data.get("results", [])

            n_saved = self._save_snapshots(search_data)
            n_sponsored = sum(1 for r in results if r.get("is_sponsored"))

            total_results += n_saved
            sponsored_results += n_sponsored

            self._update_app_keyword_positions(keyword, results, country)

            logger.info(
                f"[rank_tracker] keyword={keyword!r}: "
                f"{len(results)} results ({n_sponsored} sponsored), "
                f"{n_saved} rows saved"
            )

        self.db.commit()
        elapsed = time.monotonic() - t0

        logger.info(
            f"[rank_tracker] Done: {len(keywords_to_scan)} keywords, "
            f"{total_results} results ({sponsored_results} sponsored) "
            f"in {elapsed:.1f}s"
        )

        return {
            "keywords_scanned": len(keywords_to_scan),
            "total_results": total_results,
            "sponsored_results": sponsored_results,
            "elapsed_seconds": round(elapsed, 2),
        }

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _get_tracked_keywords(self, limit: int) -> List[str]:
        """
        Select the most useful keywords for rank tracking.

        Priority order:
          1. High quality_score keywords (quality_tier A/B)
          2. Keywords linked to many apps (apps_count > 0)
          3. Keywords seen multiple times (times_seen > 1)
          4. Reasonable length (3-40 chars, no garbage strings)

        Falls back to search_volume ordering only if quality data is absent.
        """
        from sqlalchemy import func as sqla_func

        # Try quality-based selection first
        rows = (
            self.db.query(Keyword.term)
            .filter(
                Keyword.term.isnot(None),
                sqla_func.length(Keyword.term) >= 3,
                sqla_func.length(Keyword.term) <= 40,
                # Exclude keywords that are just numbers or single chars
                Keyword.term.op("~")(r"[a-zA-Z]"),
            )
            .order_by(
                # Prefer keywords with quality data, then by score
                case(
                    (Keyword.quality_tier == "A", 3),
                    (Keyword.quality_tier == "B", 2),
                    (Keyword.quality_tier == "C", 1),
                    else_=0,
                ).desc(),
                Keyword.quality_score.desc().nullslast(),
                Keyword.apps_count.desc().nullslast(),
                Keyword.times_seen.desc().nullslast(),
                Keyword.search_volume.desc().nullslast(),
            )
            .limit(limit)
            .all()
        )

        terms = [r.term for r in rows]
        if terms:
            logger.info(
                f"[rank_tracker] Selected {len(terms)} keywords "
                f"(top: {terms[:3]!r})"
            )
        else:
            logger.warning(
                "[rank_tracker] No suitable keywords found. "
                "Ensure keyword discovery jobs have run."
            )
        return terms

    def _save_snapshots(self, search_data: dict) -> int:
        keyword = search_data["keyword"]
        country = search_data["country"]
        captured_at_str = search_data.get("captured_at", "")

        try:
            captured_at = datetime.fromisoformat(captured_at_str)
        except Exception:
            captured_at = datetime.now(timezone.utc)

        count = 0
        for item in search_data.get("results", []):
            snap = KeywordSearchSnapshot(
                keyword=keyword,
                country=country,
                app_id=str(item.get("app_id", "")),
                app_name=item.get("app_name", "")[:500] if item.get("app_name") else None,
                developer=item.get("developer", "")[:500] if item.get("developer") else None,
                icon_url=item.get("icon", "")[:512] if item.get("icon") else None,
                position=item.get("position", 0),
                organic_position=item.get("organic_position"),
                is_sponsored=bool(item.get("is_sponsored", False)),
                captured_at=captured_at,
            )
            self.db.add(snap)
            count += 1

        return count

    def _update_app_keyword_positions(
        self,
        keyword: str,
        results: List[dict],
        country: str,
    ):
        """
        Update AppKeyword.position for apps that appear in organic results.
        Only updates if the app already has a DB record.
        """
        # Map app_id → organic position for this keyword
        organic_map = {
            r["app_id"]: r["organic_position"]
            for r in results
            if not r.get("is_sponsored") and r.get("organic_position")
        }
        if not organic_map:
            return

        kw_row = self.db.query(Keyword).filter(Keyword.term == keyword).first()
        if not kw_row:
            return

        for app_id_str, pos in organic_map.items():
            app = self.db.query(App).filter(App.app_id == app_id_str).first()
            if not app:
                continue
            app_kw = (
                self.db.query(AppKeyword)
                .filter(
                    AppKeyword.app_id == app.id,
                    AppKeyword.keyword_id == kw_row.id,
                )
                .first()
            )
            if app_kw:
                app_kw.position = pos
            else:
                new_kw = AppKeyword(
                    app_id=app.id,
                    keyword_id=kw_row.id,
                    position=pos,
                    relevance=max(0.0, 1.0 - (pos - 1) * 0.05),
                )
                self.db.add(new_kw)


# ---------------------------------------------------------------------------
# Standalone runner (used by scheduler and manual API trigger)
# ---------------------------------------------------------------------------

async def run_keyword_rank_tracker(
    country: str = "us",
    keyword_limit: int = MAX_KEYWORDS_PER_RUN,
    custom_keywords: Optional[List[str]] = None,
) -> dict:
    """
    Create a DB session, run the tracker, return summary.
    Safe to call from the APScheduler job.
    """
    db = SessionLocal()
    try:
        tracker = KeywordRankTracker(db)
        return await tracker.run(
            country=country,
            keyword_limit=keyword_limit,
            custom_keywords=custom_keywords,
        )
    finally:
        db.close()
