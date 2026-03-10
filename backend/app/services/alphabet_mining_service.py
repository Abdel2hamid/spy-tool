"""
Alphabet Keyword Mining Service
================================
Generates long-tail keyword candidates by expanding each seed keyword with
every letter a–z and fetching Apple autocomplete suggestions for each
expansion.

Example
-------
seed = "youtube"
→ queries: "youtube a", "youtube b", ..., "youtube z"
→ autocomplete "youtube a" → ["youtube audio", "youtube app", ...]
→ autocomplete "youtube b" → ["youtube background music", ...]
→ result: deduplicated set of long-tail keywords

Limits
------
• Max seeds processed:   5   (alphabet expansion is 26× per seed)
• Max suggestions/seed:  30  (capped per spec)
• Polite delay:          0.15 s between autocomplete calls

The service writes enriched rows to app_discovered_keywords using the
same iTunes enrichment pipeline as KeywordDiscoveryService so opportunity
scores are immediately available.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.services.apple_autocomplete_service import fetch_autocomplete

logger = logging.getLogger(__name__)

_ALPHABET = list("abcdefghijklmnopqrstuvwxyz")
_MAX_SEEDS = 5        # alphabet expand only top-N extracted seeds
_MAX_PER_SEED = 30    # cap autocomplete suggestions per seed
_AUTOCOMPLETE_DELAY = 0.15   # seconds between calls


# ---------------------------------------------------------------------------
# Shared enrichment helpers (mirrors keyword_discovery_service internals)
# ---------------------------------------------------------------------------

def _itunes_search_enrichment(keyword: str, app_store_id: str) -> Dict:
    """
    Call iTunes Search API for *keyword* and return enrichment signals:
    search_volume, difficulty, app_rank, traffic_score.
    Does NOT call Google Trends (too slow per-keyword at scale).
    """
    import json
    import math
    import urllib.parse
    import urllib.request

    _URL = "https://itunes.apple.com/search"
    _TIMEOUT = 12

    params = urllib.parse.urlencode({
        "term": keyword,
        "country": "us",
        "entity": "software",
        "limit": 50,
        "lang": "en_us",
    })
    url = f"{_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "AppStoreSpy/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except Exception:
        return {
            "search_volume": 0, "difficulty": 0.0, "app_rank": None,
            "traffic_score": 0.0, "competitor_rank": None,
        }

    items = data.get("results", [])
    result_count = data.get("resultCount", len(items))

    # App rank + competitor rank
    app_rank: Optional[int] = None
    competitor_rank: Optional[int] = None
    for i, item in enumerate(items, 1):
        if str(item.get("trackId", "")) == app_store_id:
            app_rank = i
        elif competitor_rank is None and i <= 10:
            competitor_rank = i

    # Search volume (0-100, log-scaled)
    sv = 0.0
    if result_count > 0:
        sv += min(math.log10(result_count + 1) / math.log10(1001) * 40, 40)
    kw_lower = keyword.lower()
    hits = sum(
        1 for item in items[:10]
        if kw_lower in (item.get("trackName") or "").lower()
        or kw_lower in (item.get("subtitle") or "").lower()
    )
    sv += min(hits * 5, 30)
    counts = [item.get("userRatingCount", 0) for item in items[:5] if item.get("userRatingCount")]
    if counts:
        avg = sum(counts) / len(counts)
        sv += min(math.log10(avg + 1) / math.log10(100_001) * 30, 30)
    search_volume = min(round(sv), 100)

    # Difficulty (0-100)
    df = 0.0
    top = items[:10]
    ratings = [item.get("averageUserRating", 0) for item in top if item.get("averageUserRating")]
    if ratings:
        df += (sum(ratings) / len(ratings) / 5.0) * 40
    rcounts = [item.get("userRatingCount", 0) for item in top if item.get("userRatingCount")]
    if rcounts:
        avg = sum(rcounts) / len(rcounts)
        df += min(math.log10(avg + 1) / math.log10(50_001) * 40, 40)
    df += min(len(items) / 50 * 20, 20)
    difficulty = min(round(df, 1), 100.0)

    # CTR → traffic score
    if app_rank is None:
        ctr = 0.5
    elif app_rank == 1:
        ctr = 30.0
    elif app_rank == 2:
        ctr = 15.0
    elif app_rank == 3:
        ctr = 10.0
    elif app_rank <= 5:
        ctr = 7.0
    elif app_rank <= 10:
        ctr = 4.0
    elif app_rank <= 20:
        ctr = 2.0
    else:
        ctr = 0.5
    traffic_score = round(search_volume * ctr / 100, 1)

    return {
        "search_volume": search_volume,
        "difficulty": difficulty,
        "app_rank": app_rank,
        "traffic_score": traffic_score,
        "competitor_rank": competitor_rank,
    }


def _opportunity_score(
    search_volume: int,
    difficulty: float,
    trend_score: float,
    app_rank: Optional[int],
) -> float:
    if app_rank is None:
        rank_gap = 100
    elif app_rank > 30:
        rank_gap = 80
    elif app_rank > 10:
        rank_gap = 50
    else:
        rank_gap = 10
    return round(
        search_volume * 0.4
        + (100 - min(difficulty, 100)) * 0.3
        + trend_score * 0.2
        + rank_gap * 0.1,
        1,
    )


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class AlphabetMiningService:
    """
    Generates long-tail keywords via alphabet expansion + Apple autocomplete,
    enriches them with iTunes signals, and stores them in app_discovered_keywords.

    Usage::
        svc = AlphabetMiningService(db)
        count = svc.mine_for_app(app_id)
    """

    def __init__(self, db: Session):
        self.db = db

    def mine_for_app(self, app_id: int) -> int:
        """
        Full alphabet mining pipeline for one app.
        Returns count of newly stored keywords.
        """
        from app.models.models import App

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            logger.warning(f"[AlphabetMining] app {app_id} not found")
            return 0

        logger.info(f"[AlphabetMining] Running Phase-1 discovery for app {app_id} ({app.name!r})")

        # Load seed keywords from existing extraction
        seeds = self._load_seeds(app_id)
        if not seeds:
            logger.info(f"[AlphabetMining] app {app_id}: no extracted keywords — run extraction first")
            return 0

        # Load already-known keywords to skip
        known = self._load_known(app_id)

        # Alphabet expansion + autocomplete
        candidates: Set[str] = set()
        for seed in seeds[:_MAX_SEEDS]:
            found_for_seed = 0
            logger.info(f"[AlphabetMining] Expanding seed: {seed!r}")
            for letter in _ALPHABET:
                if found_for_seed >= _MAX_PER_SEED:
                    break
                query = f"{seed} {letter}"
                try:
                    suggestions = fetch_autocomplete(query)
                    time.sleep(_AUTOCOMPLETE_DELAY)
                except Exception as exc:
                    logger.debug(f"[AlphabetMining] autocomplete failed for {query!r}: {exc}")
                    continue
                for suggestion in suggestions:
                    suggestion = suggestion.strip().lower()
                    if (
                        len(suggestion) >= 3
                        and suggestion not in known
                        and suggestion not in candidates
                        and found_for_seed < _MAX_PER_SEED
                    ):
                        candidates.add(suggestion)
                        found_for_seed += 1
            logger.info(f"[AlphabetMining] {seed!r} → {found_for_seed} new suggestions")

        logger.info(f"[AlphabetMining] Total candidates to enrich: {len(candidates)}")

        # Enrich + store each candidate
        app_store_id = str(app.app_id)
        stored = 0
        for keyword in candidates:
            try:
                enrich = _itunes_search_enrichment(keyword, app_store_id)
                opp = _opportunity_score(
                    enrich["search_volume"],
                    enrich["difficulty"],
                    0.0,  # no trend score (skipping Google Trends for speed)
                    enrich["app_rank"],
                )
                saved = self._save_one(app_id, keyword, seeds[0], enrich, opp)
                if saved:
                    stored += 1
                time.sleep(0.3)
            except Exception as exc:
                logger.warning(f"[AlphabetMining] enrich failed for {keyword!r}: {exc}")

        logger.info(f"[AlphabetMining] Stored {stored} new alphabet keywords for app {app_id}")

        # Push candidates into the global keywords table for intelligence enrichment.
        if candidates:
            try:
                from app.services.global_keyword_sink import GlobalKeywordSink
                sink = GlobalKeywordSink(self.db)
                sink.push(
                    keywords=list(candidates),
                    source="alphabet",
                    discovered_from=seeds[0] if seeds else None,
                )
            except Exception as exc:
                logger.warning(f"[AlphabetMining] global_keyword_sink failed: {exc}")

        return stored

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load_seeds(self, app_id: int) -> List[str]:
        from app.models.models import AppKeywordIntelligence, Keyword as KW
        rows = (
            self.db.query(KW.term)
            .join(AppKeywordIntelligence, AppKeywordIntelligence.keyword_id == KW.id)
            .filter(AppKeywordIntelligence.app_id == app_id)
            .order_by(AppKeywordIntelligence.traffic_score.desc())
            .limit(20)
            .all()
        )
        return [r[0] for r in rows]

    def _load_known(self, app_id: int) -> Set[str]:
        from app.models.models import AppKeywordIntelligence, AppDiscoveredKeyword, Keyword as KW
        extracted = {
            r[0]
            for r in self.db.query(KW.term)
            .join(AppKeywordIntelligence, AppKeywordIntelligence.keyword_id == KW.id)
            .filter(AppKeywordIntelligence.app_id == app_id)
            .all()
        }
        discovered = {
            r[0]
            for r in self.db.query(AppDiscoveredKeyword.keyword)
            .filter(AppDiscoveredKeyword.app_id == app_id)
            .all()
        }
        return extracted | discovered

    def _save_one(
        self,
        app_id: int,
        keyword: str,
        source_keyword: str,
        enrich: Dict,
        opportunity_score: float,
    ) -> bool:
        from app.models.models import AppDiscoveredKeyword
        from datetime import datetime, timezone
        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = (
                pg_insert(AppDiscoveredKeyword.__table__)
                .values(
                    app_id=app_id,
                    keyword=keyword,
                    source="alphabet",
                    source_keyword=source_keyword,
                    search_volume=enrich["search_volume"],
                    difficulty=enrich["difficulty"],
                    traffic_score=enrich["traffic_score"],
                    app_rank=enrich["app_rank"],
                    competitor_rank=enrich.get("competitor_rank"),
                    keyword_gap=False,
                    trend_score=0.0,
                    trend_direction="stable",
                    opportunity_score=opportunity_score,
                    created_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(index_elements=["app_id", "keyword"])
            )
            result = self.db.execute(stmt)
            self.db.commit()
            return (result.rowcount or 0) > 0
        except Exception as exc:
            self.db.rollback()
            logger.warning(f"[AlphabetMining] _save_one failed for {keyword!r}: {exc}")
            return False
