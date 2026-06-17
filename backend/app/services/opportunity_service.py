"""
Keyword Opportunity Scoring Service
=====================================
Computes (or re-computes) opportunity_score for every discovered keyword
belonging to an app, using the canonical Phase-1 formula.

Formula
-------
opportunity_score =
    search_volume   × 0.4
  + (100-difficulty) × 0.3
  + trend_score      × 0.2
  + rank_gap_score   × 0.1

rank_gap_score rules
--------------------
  app_rank is None → 100   (not ranking at all — huge gap)
  app_rank > 30    →  80   (outside top-30)
  app_rank > 10    →  50   (top 11-30)
  app_rank ≤ 10    →  10   (already ranking well)

Scores are clamped to [0, 100].
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.config.scoring_config import OPPORTUNITY_CONFIG

logger = logging.getLogger(__name__)

_W = OPPORTUNITY_CONFIG["weights"]
_RGS = OPPORTUNITY_CONFIG["rank_gap_scores"]


# ---------------------------------------------------------------------------
# Pure scoring functions (no DB, no I/O)
# ---------------------------------------------------------------------------

def rank_gap_score(app_rank: Optional[int]) -> float:
    """Return the rank-gap component (0-100) of the opportunity formula."""
    if app_rank is None:
        return _RGS[None]
    if app_rank > 30:
        return _RGS[30]
    if app_rank > 10:
        return _RGS[10]
    return _RGS[0]


def compute_opportunity_score(
    search_volume: int,
    difficulty: float,
    trend_score: float,
    app_rank: Optional[int],
) -> float:
    """Canonical opportunity score formula — returns value in [0, 100]."""
    score = (
        search_volume * _W["search_volume"]
        + (100.0 - min(difficulty, 100.0)) * _W["difficulty"]
        + trend_score * _W["trend"]
        + rank_gap_score(app_rank) * _W["rank_gap"]
    )
    return round(min(max(score, 0.0), 100.0), 1)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class OpportunityScoreService:
    """
    Recomputes opportunity_score for all discovered keywords of an app and
    identifies the highest-scoring targets.

    Usage::
        svc = OpportunityScoreService(db)
        updated = svc.score_for_app(app_id)
        top     = svc.get_top_opportunities(app_id, limit=50)
    """

    def __init__(self, db: Session):
        self.db = db

    def score_for_app(self, app_id: int) -> int:
        """
        Recompute and persist opportunity_score for every discovered keyword
        belonging to this app. Returns count of rows updated.
        """
        from app.models.models import AppDiscoveredKeyword

        rows = (
            self.db.query(AppDiscoveredKeyword)
            .filter(AppDiscoveredKeyword.app_id == app_id)
            .all()
        )

        if not rows:
            return 0

        updated = 0
        best_keyword = ""
        best_score = 0.0

        for row in rows:
            new_score = compute_opportunity_score(
                row.search_volume,
                row.difficulty,
                row.trend_score,
                row.app_rank,
            )
            if abs(new_score - (row.opportunity_score or 0.0)) > 0.05:
                row.opportunity_score = new_score
                updated += 1
            if new_score > best_score:
                best_score = new_score
                best_keyword = row.keyword

        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.warning(f"[OpportunityScore] commit failed for app {app_id}: {exc}")
            return 0

        logger.info(
            f"[OpportunityScore] Updated {updated} opportunity scores for app {app_id}"
        )
        if best_keyword:
            logger.info(
                f"[OpportunityScore] Top opportunity keyword: {best_keyword!r} "
                f"(score={best_score:.1f})"
            )

        # Backfill global keywords table with every opportunity keyword so the
        # intelligence pipeline can enrich them (covers old rows too).
        try:
            from app.services.global_keyword_sink import GlobalKeywordSink
            terms = [row.keyword for row in rows]
            sink = GlobalKeywordSink(self.db)
            sink.push(keywords=terms, source="opportunity")
        except Exception as exc:
            logger.warning(f"[OpportunityScore] global_keyword_sink failed: {exc}")

        return updated

    def get_top_opportunities(self, app_id: int, limit: int = 50) -> List[Dict]:
        """
        Return top keywords sorted by opportunity_score DESC.
        Includes all fields needed for the frontend opportunities table.
        """
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
                "search_volume": r.search_volume,
                "difficulty": r.difficulty,
                "trend_score": r.trend_score,
                "trend_direction": r.trend_direction,
                "app_rank": r.app_rank,
                "competitor_rank": getattr(r, "competitor_rank", None),
                "keyword_gap": bool(getattr(r, "keyword_gap", False)),
                "opportunity_score": r.opportunity_score,
                "source": r.source,
                # V2 scores
                "chance_score": float(akw.chance_score or 0) if akw else 0.0,
                "kei": float(akw.kei or 0) if akw else 0.0,
                "estimated_installs": float(akw.estimated_installs or 0) if akw else 0.0,
                "volume_score": float(kw.volume_score or 0) if kw else 0.0,
                "difficulty_v2": float(kw.difficulty_v2 or 0) if kw else 0.0,
            })
        return result
