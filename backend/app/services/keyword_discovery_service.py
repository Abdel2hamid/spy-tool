"""
Keyword Discovery Service
=========================
Expands an app's extracted keywords into a larger set of high-value ASO
candidates using Apple autocomplete suggestions and affix expansions,
then enriches each candidate with iTunes market signals, Google Trends
data, and a composite opportunity score.

Pipeline
--------
1. Load previously extracted keywords for the app
   (from app_keyword_intelligence via keyword_extraction_service)
2. For each extracted keyword:
   a. Fetch Apple autocomplete suggestions
   b. Generate prefix expansions  ("best {kw}", "free {kw}", …)
   c. Generate suffix expansions  ("{kw} app", "{kw} download", …)
3. Deduplicate aggressively (skip terms already in app_keyword_intelligence)
4. Enrich each new candidate:
   - iTunes Search API → search_volume, difficulty, app_rank, traffic_score
   - Google Trends     → trend_score, trend_direction
   - Opportunity score formula (see _opportunity_score())
5. Persist to app_discovered_keywords (ON CONFLICT DO NOTHING)

Opportunity score formula
-------------------------
opportunity_score =
    search_volume   × 0.4
  + (100-difficulty) × 0.3
  + trend_score      × 0.2
  + rank_gap_score   × 0.1

rank_gap_score:
  app not ranked → 100
  rank > 30      →  80
  rank > 10      →  50
  rank ≤ 10      →  10
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.services.apple_autocomplete_service import fetch_autocomplete
from app.services.apple_http_client import apple_fetch_json, ITUNES_SEARCH_URL
from app.services.keyword_trends_service import fetch_trend_score

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Expansion affixes
# ---------------------------------------------------------------------------
_PREFIXES = ["best", "free", "top", "new"]
_SUFFIXES = ["app", "download"]

# ---------------------------------------------------------------------------
# iTunes Search API
# ---------------------------------------------------------------------------
_REQUEST_DELAY = 0.35   # polite delay between iTunes calls (s)
_TIMEOUT = 12


def _itunes_search(keyword: str, limit: int = 50) -> Dict:
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
    return data or {}


def _opportunity_score(
    search_volume: int,
    difficulty: float,
    trend_score: float,
    app_rank: Optional[int],
) -> float:
    """Composite opportunity score 0-100."""
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
class KeywordDiscoveryService:
    """
    Discovers and enriches keyword candidates for a single app.

    Usage::
        svc = KeywordDiscoveryService(db)
        count = svc.discover_for_app(app_id)          # blocking
        rows  = svc.get_discovered(app_id, limit=200)
    """

    _MAX_EXPANSIONS = 200   # hard cap on candidates to enrich per run

    def __init__(self, db: Session):
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def discover_for_app(self, app_id: int) -> int:
        """
        Full discovery pipeline.  Returns count of newly stored keywords.
        Intended to run inside asyncio.to_thread() from async endpoints.
        """
        from app.models.models import App, AppKeywordIntelligence, Keyword as KW

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            logger.warning(f"[Discovery] app {app_id} not found")
            return 0

        logger.info(f"[Discovery] Running keyword discovery for app {app.app_id} ({app.name!r})")

        # ── 1. Seed keywords from existing extraction ─────────────────────
        seeds: List[str] = self._load_seed_keywords(app_id)
        if not seeds:
            logger.info(f"[Discovery] app {app_id}: no extracted keywords yet — run extraction first")
            return 0

        # ── 2. Expand seeds ───────────────────────────────────────────────
        already_known = self._load_known_keywords(app_id)
        candidates: Set[str] = set()

        for seed in seeds[:40]:   # cap seed scan to avoid rate-limit abuse
            # Autocomplete
            try:
                suggestions = fetch_autocomplete(seed)
                candidates.update(suggestions)
                time.sleep(0.1)
            except Exception as exc:
                logger.debug(f"[Discovery] autocomplete failed for {seed!r}: {exc}")

            # Prefix expansions
            for prefix in _PREFIXES:
                candidates.add(f"{prefix} {seed}")

            # Suffix expansions
            for suffix in _SUFFIXES:
                candidates.add(f"{seed} {suffix}")

        # ── 3. Deduplicate aggressively ───────────────────────────────────
        new_candidates = [
            c for c in candidates
            if c not in already_known
            and len(c) >= 3
            and c not in seeds
        ]
        new_candidates = new_candidates[: self._MAX_EXPANSIONS]

        logger.info(
            f"[Discovery] app {app_id}: {len(seeds)} seeds → "
            f"{len(candidates)} expansions → {len(new_candidates)} new to enrich"
        )

        # ── 4. Per-app limit guard ────────────────────────────────────────
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
        if len(new_candidates) > slots:
            new_candidates = new_candidates[:slots]

        # ── 5. Enrich + store ────────────────────────────────────────────
        from app.services.keyword_quality_engine import KeywordQualityEngine
        _qe = KeywordQualityEngine()
        _reject_tier_c = _qe.should_reject_tier_c(self.db)

        stored = 0
        best_keyword = ""
        best_score = 0.0
        kw_enrichment_data: Dict[str, Dict] = {}
        quota_rejected = 0
        gate_rejected = 0
        quality_rejected = 0
        accepted = 0

        for kw in new_candidates:
            try:
                # Quota check before expensive iTunes call
                if not _qe.check_app_quota(self.db, app_id, "autocomplete"):
                    quota_rejected += 1
                    continue

                # Hard gate
                passes, reason = _qe.passes_hard_gate(kw)
                if not passes:
                    gate_rejected += 1
                    continue

                row = self._enrich_one(kw, seeds, app_id, str(app.app_id))

                # Quality score using enriched data + app context
                q_score, _, _ = _qe.compute_quality_score(
                    term=kw,
                    keyword_source=row["source"],
                    apps_count=row.get("apps_count", 0),  # Actual iTunes result count
                    search_volume=row.get("search_volume", 0),  # Derived volume score
                    difficulty=row.get("difficulty", 0.0),
                    trend_score=row.get("trend_score", 0.0),
                    app_title=app.name or "",
                    app_subtitle=app.subtitle or "",
                )
                tier = _qe.assign_tier(q_score)

                # Reject if below minimum threshold or Tier C when global cap hit
                if tier is None:
                    quality_rejected += 1
                    continue
                if tier == "C" and _reject_tier_c:
                    quality_rejected += 1
                    continue

                accepted += 1
                saved = self._save_one(app_id, row)
                if saved:
                    stored += 1
                    if row["opportunity_score"] > best_score:
                        best_score = row["opportunity_score"]
                        best_keyword = kw
                # Collect enrichment data for app_keywords population
                kw_enrichment_data[kw] = {
                    "rank": row.get("app_rank"),
                    "traffic": row.get("traffic_score", 0.0),
                    "opportunity_score": row.get("opportunity_score", 0.0),
                }
                time.sleep(_REQUEST_DELAY)
            except Exception as exc:
                logger.warning(f"[Discovery] enrich failed for {kw!r}: {exc}")

        logger.info(
            f"[Discovery] app {app_id}: quota_rejected={quota_rejected}, "
            f"gate_rejected={gate_rejected}, quality_rejected={quality_rejected}, "
            f"accepted={accepted}, stored={stored}"
        )
        logger.info(f"[Discovery] Discovered {stored} new keywords for app {app_id}")
        if best_keyword:
            logger.info(
                f"[Discovery] Top opportunity keyword: {best_keyword!r} "
                f"(score={best_score:.1f})"
            )

        # Push into global keywords dictionary + app_keywords relation table
        if new_candidates:
            try:
                from app.services.global_keyword_sink import GlobalKeywordSink
                sink = GlobalKeywordSink(self.db)
                sink.push(
                    keywords=new_candidates,
                    source="discovered",
                    discovered_from=seeds[0] if seeds else None,
                )
                sink.push_app_keywords(
                    app_id=app_id,
                    kw_data=kw_enrichment_data,
                    source="discovered",
                )
            except Exception as exc:
                logger.warning(f"[Discovery] global_keyword_sink failed: {exc}")

        return stored

    def get_discovered(self, app_id: int, limit: int = 200) -> List[Dict]:
        """Return stored discovered keywords sorted by opportunity_score DESC."""
        from app.models.models import AppDiscoveredKeyword, Keyword as KW, AppKeyword as AKW

        rows = (
            self.db.query(AppDiscoveredKeyword)
            .filter(AppDiscoveredKeyword.app_id == app_id)
            .order_by(AppDiscoveredKeyword.opportunity_score.desc())
            .limit(limit)
            .all()
        )

        # Batch-load v2 scores from Keyword + AppKeyword tables
        terms = [r.keyword for r in rows]
        kw_map = {}
        if terms:
            kw_rows = self.db.query(KW).filter(KW.term.in_(terms)).all()
            kw_map = {k.term: k for k in kw_rows}
        akw_map = {}
        if terms:
            kw_ids = [k.id for k in kw_map.values()]
            if kw_ids:
                akw_rows = (
                    self.db.query(AKW)
                    .filter(AKW.app_id == app_id, AKW.keyword_id.in_(kw_ids))
                    .all()
                )
                akw_map = {a.keyword_id: a for a in akw_rows}

        result = []
        for r in rows:
            kw = kw_map.get(r.keyword)
            akw = akw_map.get(kw.id) if kw else None
            result.append({
                "keyword": r.keyword,
                "source": r.source,
                "source_keyword": r.source_keyword,
                "search_volume": r.search_volume,
                "difficulty": r.difficulty,
                "traffic_score": r.traffic_score,
                "app_rank": r.app_rank,
                "competitor_rank": getattr(r, "competitor_rank", None),
                "keyword_gap": bool(getattr(r, "keyword_gap", False)),
                "trend_score": r.trend_score,
                "trend_direction": r.trend_direction,
                "opportunity_score": r.opportunity_score,
                "created_at": r.created_at,
                # V2 scores
                "chance_score": float(akw.chance_score or 0) if akw else 0.0,
                "kei": float(akw.kei or 0) if akw else 0.0,
                "estimated_installs": float(akw.estimated_installs or 0) if akw else 0.0,
                "volume_score": float(kw.volume_score or 0) if kw else 0.0,
                "difficulty_v2": float(kw.difficulty_v2 or 0) if kw else 0.0,
            })
        return result

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load_seed_keywords(self, app_id: int) -> List[str]:
        """Return all extracted keywords for this app from app_keyword_intelligence."""
        from app.models.models import AppKeywordIntelligence, Keyword as KW

        rows = (
            self.db.query(KW.term)
            .join(AppKeywordIntelligence, AppKeywordIntelligence.keyword_id == KW.id)
            .filter(AppKeywordIntelligence.app_id == app_id)
            .order_by(AppKeywordIntelligence.traffic_score.desc())
            .limit(100)
            .all()
        )
        return [r[0] for r in rows]

    def _load_known_keywords(self, app_id: int) -> Set[str]:
        """All keywords already known for this app (extraction + discovery)."""
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

    def _find_source_keyword(self, keyword: str, seeds: List[str]) -> str:
        """Return which seed keyword triggered this candidate."""
        kw_lower = keyword.lower()
        for seed in seeds:
            if seed in kw_lower or kw_lower.startswith(seed) or kw_lower.endswith(seed):
                return seed
        return seeds[0] if seeds else ""

    def _classify_source(self, keyword: str, seeds: List[str]) -> str:
        """Classify how this candidate was generated."""
        kw_lower = keyword.lower()
        for p in _PREFIXES:
            if kw_lower.startswith(p + " "):
                return "prefix"
        for s in _SUFFIXES:
            if kw_lower.endswith(" " + s):
                return "suffix"
        return "autocomplete"

    def _enrich_one(
        self, keyword: str, seeds: List[str], app_id: int, app_store_id: str
    ) -> Dict:
        """Enrich a single keyword with iTunes + Trends signals."""
        import math

        data = _itunes_search(keyword)
        items = data.get("results", [])
        result_count = data.get("resultCount", len(items))

        # App rank
        app_rank: Optional[int] = None
        for i, item in enumerate(items):
            if str(item.get("trackId", "")) == app_store_id:
                app_rank = i + 1
                break

        # Search volume (0-100, log-scaled result count + title hits)
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

        # CTR → traffic
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

        # Google Trends
        trend_data = fetch_trend_score(keyword)
        trend_score = float(trend_data.get("trend_score", 0))
        trend_direction = trend_data.get("trend_direction", "stable")

        # Opportunity
        opp = _opportunity_score(search_volume, difficulty, trend_score, app_rank)

        return {
            "keyword": keyword,
            "source": self._classify_source(keyword, seeds),
            "source_keyword": self._find_source_keyword(keyword, seeds),
            "search_volume": search_volume,
            "apps_count": result_count,  # Actual iTunes result count (for validation_score)
            "difficulty": difficulty,
            "traffic_score": traffic_score,
            "app_rank": app_rank,
            "trend_score": trend_score,
            "trend_direction": trend_direction,
            "opportunity_score": opp,
        }

    def _save_one(self, app_id: int, row: Dict) -> bool:
        """
        Insert one row into app_discovered_keywords.
        Uses ON CONFLICT DO NOTHING — returns True if newly inserted.
        """
        from app.models.models import AppDiscoveredKeyword

        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = (
                pg_insert(AppDiscoveredKeyword.__table__)
                .values(
                    app_id=app_id,
                    keyword=row["keyword"],
                    source=row["source"],
                    source_keyword=row["source_keyword"],
                    search_volume=row["search_volume"],
                    difficulty=row["difficulty"],
                    traffic_score=row["traffic_score"],
                    app_rank=row["app_rank"],
                    trend_score=row["trend_score"],
                    trend_direction=row["trend_direction"],
                    opportunity_score=row["opportunity_score"],
                    created_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(index_elements=["app_id", "keyword"])
            )
            result = self.db.execute(stmt)
            self.db.commit()
            return (result.rowcount or 0) > 0
        except Exception as exc:
            self.db.rollback()
            logger.warning(f"[Discovery] _save_one failed for {row['keyword']!r}: {exc}")
            return False
