"""
Competitor Keyword Mining Service
==================================
Extracts ASO keywords from competitor apps that rank for the target app's
top keywords. Competitor keywords are stored in app_discovered_keywords with
source="competitor".

Pipeline
--------
1. Load top extracted keywords from app_keyword_intelligence (up to 10 seeds).
2. For each seed keyword, search iTunes: entity=software, limit=20.
3. Take top 5 non-self results (competitors).
4. Extract unigrams, bigrams, trigrams from trackName + subtitle.
5. Deduplicate against already-known keywords for this app.
6. Enrich remaining phrases (iTunes search → volume, difficulty, app_rank).
7. Persist to app_discovered_keywords with source="competitor".
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.services.apple_http_client import apple_fetch_json, ITUNES_SEARCH_URL

logger = logging.getLogger(__name__)

_REQUEST_DELAY = 0.35
_TIMEOUT = 12
_MAX_SEEDS = 10
_TOP_COMPETITORS = 5
_MAX_PHRASES = 80   # cap total phrases to enrich per run

_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "out", "is", "are", "was", "be",
    "your", "our", "my", "this", "that", "its", "it", "app", "free",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _itunes_search(keyword: str, limit: int = 20) -> List[Dict]:
    data = apple_fetch_json(
        ITUNES_SEARCH_URL,
        params={
            "term": keyword,
            "country": "us",
            "entity": "software",
            "limit": limit,
            "lang": "en_us",
        },
        timeout=_TIMEOUT,
    )
    if not data:
        return []
    return data.get("results", [])


def _tokenize(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if len(t) >= 3 and t not in _STOP_WORDS]


def _ngrams(tokens: List[str], n: int) -> List[str]:
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _extract_phrases(track_name: str, subtitle: str) -> Set[str]:
    """Extract unigrams, bigrams, trigrams from app name + subtitle."""
    phrases: Set[str] = set()
    for text in (track_name or "", subtitle or ""):
        tokens = _tokenize(text)
        for n in (1, 2, 3):
            for phrase in _ngrams(tokens, n):
                if len(phrase) >= 3:
                    phrases.add(phrase)
    return phrases


def _enrich_one(keyword: str, app_store_id: str) -> Dict:
    """
    iTunes enrichment for a single keyword — returns volume, difficulty, ranks.
    """
    import math

    try:
        results = _itunes_search(keyword, limit=50)
    except Exception:
        return {
            "search_volume": 0, "difficulty": 0.0, "app_rank": None,
            "traffic_score": 0.0, "competitor_rank": None,
        }

    result_count = len(results)

    # App rank + competitor rank
    app_rank: Optional[int] = None
    competitor_rank: Optional[int] = None
    for i, item in enumerate(results, 1):
        if str(item.get("trackId", "")) == app_store_id:
            app_rank = i
        elif competitor_rank is None and i <= 10:
            competitor_rank = i

    # Search volume (0-100)
    sv = 0.0
    if result_count > 0:
        sv += min(math.log10(result_count + 1) / math.log10(1001) * 40, 40)
    kw_lower = keyword.lower()
    hits = sum(
        1 for item in results[:10]
        if kw_lower in (item.get("trackName") or "").lower()
        or kw_lower in (item.get("subtitle") or "").lower()
    )
    sv += min(hits * 5, 30)
    counts = [item.get("userRatingCount", 0) for item in results[:5] if item.get("userRatingCount")]
    if counts:
        avg = sum(counts) / len(counts)
        sv += min(math.log10(avg + 1) / math.log10(100_001) * 30, 30)
    search_volume = min(round(sv), 100)

    # Difficulty (0-100)
    df = 0.0
    top = results[:10]
    ratings = [item.get("averageUserRating", 0) for item in top if item.get("averageUserRating")]
    if ratings:
        df += (sum(ratings) / len(ratings) / 5.0) * 40
    rcounts = [item.get("userRatingCount", 0) for item in top if item.get("userRatingCount")]
    if rcounts:
        avg = sum(rcounts) / len(rcounts)
        df += min(math.log10(avg + 1) / math.log10(50_001) * 40, 40)
    df += min(len(results) / 50 * 20, 20)
    difficulty = min(round(df, 1), 100.0)

    # Traffic score
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
        "apps_count": result_count,  # Actual iTunes result count (for validation_score)
        "difficulty": difficulty,
        "app_rank": app_rank,
        "traffic_score": traffic_score,
        "competitor_rank": competitor_rank,
    }


def _opportunity_score(
    search_volume: int,
    difficulty: float,
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
        + 0  # trend_score = 0 (not querying Google Trends here)
        + rank_gap * 0.1,
        1,
    )


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class CompetitorKeywordService:
    """
    Mines keywords from competitor apps to identify phrases the target app
    is missing from its metadata.

    Usage::
        svc = CompetitorKeywordService(db)
        count = svc.mine_for_app(app_id)
    """

    def __init__(self, db: Session):
        self.db = db

    def mine_for_app(self, app_id: int) -> int:
        """
        Run competitor keyword mining for one app.
        Returns the number of newly stored competitor keywords.
        """
        from app.models.models import App

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            logger.warning(f"[CompetitorMining] app {app_id} not found")
            return 0

        app_store_id = str(app.app_id)
        logger.info(f"[CompetitorMining] Running for app {app_id} ({app.name!r})")

        # 1. Load seeds from extraction
        seeds = self._load_seeds(app_id)
        if not seeds:
            logger.info(f"[CompetitorMining] app {app_id}: no extracted keywords yet")
            return 0

        # 2. Load already-known keywords to skip
        known = self._load_known(app_id)

        # 3. Find competitors and extract their phrases
        all_phrases: Set[str] = set()
        for seed in seeds[:_MAX_SEEDS]:
            try:
                results = _itunes_search(seed, limit=20)
                time.sleep(_REQUEST_DELAY)
            except Exception as exc:
                logger.debug(f"[CompetitorMining] search failed for {seed!r}: {exc}")
                continue

            # Exclude our own app
            competitors = [
                r for r in results
                if str(r.get("trackId", "")) != app_store_id
            ][:_TOP_COMPETITORS]

            for comp in competitors:
                phrases = _extract_phrases(
                    comp.get("trackName", ""),
                    comp.get("subtitle", ""),
                )
                all_phrases.update(phrases)

        # 4. Deduplicate
        new_phrases = [
            p for p in all_phrases
            if p not in known and len(p) >= 3
        ][:_MAX_PHRASES]

        logger.info(
            f"[CompetitorMining] app {app_id}: {len(all_phrases)} phrases → "
            f"{len(new_phrases)} new to enrich"
        )

        # ── Per-app limit guard ───────────────────────────────────────────────
        from app.models.models import AppDiscoveredKeyword as _ADK
        _MAX_PER_APP = 100
        current_count = (
            self.db.query(func.count(_ADK.id))
            .filter(_ADK.app_id == app_id)
            .scalar() or 0
        )
        if current_count >= _MAX_PER_APP:
            logger.info(
                f"[KeywordLimit] app {app_id} already has {current_count} keywords "
                f"(limit={_MAX_PER_APP}) — skipping insertion"
            )
            return 0
        slots = _MAX_PER_APP - current_count
        if len(new_phrases) > slots:
            new_phrases = new_phrases[:slots]

        # 5. Enrich + store
        from app.services.keyword_quality_engine import KeywordQualityEngine
        _qe = KeywordQualityEngine()
        _reject_tier_c = _qe.should_reject_tier_c(self.db)

        stored = 0
        source_kw = seeds[0] if seeds else ""
        kw_enrichment_data: Dict[str, Dict] = {}
        quota_rejected = 0
        gate_rejected = 0
        quality_rejected = 0
        accepted = 0

        for phrase in new_phrases:
            try:
                # Quota check
                if not _qe.check_app_quota(self.db, app_id, "competitor"):
                    quota_rejected += 1
                    continue

                # Hard gate
                passes, reason = _qe.passes_hard_gate(phrase)
                if not passes:
                    gate_rejected += 1
                    continue

                enrich = _enrich_one(phrase, app_store_id)
                opp = _opportunity_score(
                    enrich["search_volume"],
                    enrich["difficulty"],
                    enrich["app_rank"],
                )

                # Quality score
                q_score, _, _ = _qe.compute_quality_score(
                    term=phrase,
                    keyword_source="competitor",
                    apps_count=enrich.get("apps_count", 0),  # Actual iTunes result count
                    search_volume=enrich.get("search_volume", 0),  # Derived volume score
                    difficulty=enrich.get("difficulty", 0.0),
                    app_title=app.name or "",
                    app_subtitle=app.subtitle or "",
                )
                tier = _qe.assign_tier(q_score)

                if tier is None:
                    quality_rejected += 1
                    continue
                if tier == "C" and _reject_tier_c:
                    quality_rejected += 1
                    continue

                accepted += 1
                if self._save_one(app_id, phrase, source_kw, enrich, opp):
                    stored += 1
                # Collect for app_keywords population
                kw_enrichment_data[phrase] = {
                    "rank": enrich.get("app_rank"),
                    "traffic": enrich.get("traffic_score", 0.0),
                    "opportunity_score": opp,
                }
                time.sleep(_REQUEST_DELAY)
            except Exception as exc:
                logger.warning(f"[CompetitorMining] enrich failed for {phrase!r}: {exc}")

        logger.info(
            f"[CompetitorMining] app {app_id}: quota_rejected={quota_rejected}, "
            f"gate_rejected={gate_rejected}, quality_rejected={quality_rejected}, "
            f"accepted={accepted}"
        )
        logger.info(f"[CompetitorMining] Stored {stored} competitor keywords for app {app_id}")

        # Push into global keywords dictionary + app_keywords relation table
        if new_phrases:
            try:
                from app.services.global_keyword_sink import GlobalKeywordSink
                sink = GlobalKeywordSink(self.db)
                sink.push(
                    keywords=new_phrases,
                    source="competitor",
                    discovered_from=seeds[0] if seeds else None,
                )
                sink.push_app_keywords(
                    app_id=app_id,
                    kw_data=kw_enrichment_data,
                    source="competitor",
                )
            except Exception as exc:
                logger.warning(f"[CompetitorMining] global_keyword_sink failed: {exc}")

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
        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = (
                pg_insert(AppDiscoveredKeyword.__table__)
                .values(
                    app_id=app_id,
                    keyword=keyword,
                    source="competitor",
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
            logger.warning(f"[CompetitorMining] _save_one failed for {keyword!r}: {exc}")
            return False
