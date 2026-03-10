"""
Keyword Gap Analysis Service
=============================
Identifies keywords where competitors rank in the top 10 of iTunes search
results but the target app does not appear in the top 30.

Gap Condition
-------------
  app_rank IS NULL  OR  app_rank > 30
  AND competitor_rank <= 10

competitor_rank: best position (1-based) of any non-target result in top 10.

The service updates two columns in app_discovered_keywords:
  • competitor_rank  — best competitor position for this keyword
  • keyword_gap      — True when gap condition is met

Performance
-----------
Processes up to 50 keywords per run (highest search_volume first) to stay
within iTunes rate limits. Keywords where app_rank <= 30 are cleared of any
stale keyword_gap flag without an extra API call.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_ITUNES_SEARCH = "https://itunes.apple.com/search"
_REQUEST_DELAY = 0.3
_TIMEOUT = 12
_MAX_KEYWORDS = 50    # max keywords to analyse per run


# ---------------------------------------------------------------------------
# iTunes helper
# ---------------------------------------------------------------------------

def _find_ranks(keyword: str, app_store_id: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Search iTunes for *keyword* and return (app_rank, competitor_rank).

    app_rank       — 1-based position of our app; None if not in top-20.
    competitor_rank — best position of any OTHER app in top-10; None if empty.
    """
    params = urllib.parse.urlencode({
        "term": keyword,
        "country": "us",
        "entity": "software",
        "limit": 20,
        "lang": "en_us",
    })
    url = f"{_ITUNES_SEARCH}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "AppStoreSpy/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        logger.debug(f"[GapAnalysis] iTunes search failed for {keyword!r}: {exc}")
        return None, None

    results = data.get("results", [])
    app_rank: Optional[int] = None
    competitor_rank: Optional[int] = None

    for i, item in enumerate(results, 1):
        track_id = str(item.get("trackId", ""))
        if track_id == app_store_id:
            app_rank = i
        elif competitor_rank is None and i <= 10:
            competitor_rank = i   # best non-app result in top 10

    return app_rank, competitor_rank


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class KeywordGapService:
    """
    Marks keyword gaps: keywords where competitors outrank the target app.

    Usage::
        svc = KeywordGapService(db)
        gap_count = svc.analyze_for_app(app_id)
    """

    def __init__(self, db: Session):
        self.db = db

    def analyze_for_app(self, app_id: int) -> int:
        """
        Analyse gaps for all discovered keywords of this app.
        Updates competitor_rank and keyword_gap in app_discovered_keywords.
        Returns count of keywords marked as gaps.
        """
        from app.models.models import App, AppDiscoveredKeyword

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            logger.warning(f"[GapAnalysis] app {app_id} not found")
            return 0

        app_store_id = str(app.app_id)
        logger.info(f"[GapAnalysis] Running for app {app_id} ({app.name!r})")

        # Fetch top keywords sorted by search_volume (highest first)
        candidates = (
            self.db.query(AppDiscoveredKeyword)
            .filter(AppDiscoveredKeyword.app_id == app_id)
            .filter(AppDiscoveredKeyword.search_volume > 5)   # skip zero-volume noise
            .order_by(AppDiscoveredKeyword.search_volume.desc())
            .limit(_MAX_KEYWORDS)
            .all()
        )

        if not candidates:
            logger.info(f"[GapAnalysis] app {app_id}: no enriched discovered keywords")
            return 0

        gap_count = 0
        for row in candidates:
            # Fast path: if app ranks well, no gap (clear stale flag without API call)
            if row.app_rank is not None and row.app_rank <= 30:
                if row.keyword_gap:
                    try:
                        row.keyword_gap = False
                        self.db.commit()
                    except Exception:
                        self.db.rollback()
                continue

            # Slow path: do iTunes search to get fresh competitor_rank
            try:
                app_rank, competitor_rank = _find_ranks(row.keyword, app_store_id)
                time.sleep(_REQUEST_DELAY)
            except Exception as exc:
                logger.debug(f"[GapAnalysis] skipping {row.keyword!r}: {exc}")
                continue

            is_gap = (
                competitor_rank is not None
                and competitor_rank <= 10
                and (app_rank is None or app_rank > 30)
            )

            try:
                if app_rank is not None:
                    row.app_rank = app_rank
                row.competitor_rank = competitor_rank
                row.keyword_gap = is_gap
                self.db.commit()
            except Exception as exc:
                self.db.rollback()
                logger.warning(f"[GapAnalysis] update failed for {row.keyword!r}: {exc}")
                continue

            if is_gap:
                gap_count += 1
                logger.debug(
                    f"[GapAnalysis] GAP: {row.keyword!r} — "
                    f"app_rank={app_rank}, competitor_rank={competitor_rank}"
                )

        logger.info(f"[GapAnalysis] Found {gap_count} gap keywords for app {app_id}")
        return gap_count
