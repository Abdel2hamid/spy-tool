"""
Smart Keyword Suggestions Service
===================================
Aggregates keywords from all sources, deduplicates, and categorises into
actionable buckets:

  • Quick Wins   — you already rank 11-30, low difficulty, push to top 10
  • High-Value Gaps — competitors rank top 10, you don't; high volume
  • Untapped      — high volume + low difficulty, nobody owns them yet
  • Long Tail     — moderate volume, very low difficulty, easy pickings
  • Defend        — you rank top 5, competitors closing in

Each suggestion includes a reason explaining *why* it's recommended.
"""
from __future__ import annotations

import logging
from typing import Dict, List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_MAX_PER_BUCKET = 25
_MAX_TOTAL = 60


class KeywordSuggestionsService:
    def __init__(self, db: Session):
        self.db = db

    def suggest(self, app_id: int) -> dict:
        from app.models.models import (
            App,
            AppDiscoveredKeyword,
            AppKeywordIntelligence,
            Keyword,
        )

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return {"error": "App not found"}

        # ── Collect all keywords with metadata ──────────────────────

        # Source 1: Discovered keywords (richest data)
        disc_rows = (
            self.db.query(AppDiscoveredKeyword)
            .filter(AppDiscoveredKeyword.app_id == app_id)
            .all()
        )

        kw_data: Dict[str, dict] = {}
        for r in disc_rows:
            kw = r.keyword.lower().strip()
            kw_data[kw] = {
                "keyword": kw,
                "app_rank": r.app_rank,
                "competitor_rank": r.competitor_rank,
                "keyword_gap": bool(r.keyword_gap),
                "search_volume": r.search_volume or 0,
                "difficulty": r.difficulty or 0,
                "trend_score": r.trend_score or 0,
                "trend_direction": r.trend_direction or "stable",
                "opportunity_score": r.opportunity_score or 0,
                "source": r.source or "discovered",
            }

        # Source 2: Intelligence keywords (from app's own metadata)
        intel_rows = (
            self.db.query(
                AppKeywordIntelligence.app_rank,
                AppKeywordIntelligence.search_volume,
                AppKeywordIntelligence.difficulty,
                AppKeywordIntelligence.traffic_score,
                AppKeywordIntelligence.source,
                Keyword.term,
            )
            .join(Keyword, AppKeywordIntelligence.keyword_id == Keyword.id)
            .filter(AppKeywordIntelligence.app_id == app_id)
            .all()
        )
        for rank, sv, diff, traffic, src, term in intel_rows:
            kw = term.lower().strip()
            if kw not in kw_data:
                kw_data[kw] = {
                    "keyword": kw,
                    "app_rank": rank,
                    "competitor_rank": None,
                    "keyword_gap": False,
                    "search_volume": sv or 0,
                    "difficulty": diff or 0,
                    "trend_score": 0,
                    "trend_direction": "stable",
                    "opportunity_score": 0,
                    "source": f"metadata:{src}" if src else "metadata",
                }

        # ── Load v2 scores from global keywords table ──────────────
        all_terms = list(kw_data.keys())
        v2_map: Dict[str, dict] = {}
        batch_sz = 500
        for i in range(0, len(all_terms), batch_sz):
            # keywords.term is stored lowercase — lowering the Python side
            # keeps the plain index usable (func.lower() forced a seq scan).
            batch = [t.lower() for t in all_terms[i : i + batch_sz]]
            rows = (
                self.db.query(
                    Keyword.term,
                    Keyword.volume_score,
                    Keyword.difficulty_v2,
                )
                .filter(Keyword.term.in_(batch))
                .all()
            )
            for term, vs, dv in rows:
                v2_map[term.lower()] = {
                    "volume_score": float(vs or 0),
                    "difficulty_v2": float(dv or 0),
                }

        # Merge v2 scores into kw_data
        for kw, data in kw_data.items():
            v2 = v2_map.get(kw, {})
            data["volume_score"] = v2.get("volume_score", 0)
            data["difficulty_v2"] = v2.get("difficulty_v2", 0)

        # ── Categorise into buckets ────────────────────────────────
        quick_wins: List[dict] = []
        high_value_gaps: List[dict] = []
        untapped: List[dict] = []
        long_tail: List[dict] = []
        defend: List[dict] = []

        for kw, d in kw_data.items():
            rank = d["app_rank"]
            comp_rank = d["competitor_rank"]
            vs = d["volume_score"]
            dv = d["difficulty_v2"]
            sv = d["search_volume"]
            is_gap = d["keyword_gap"]

            # Quick Wins: you rank 11-30, difficulty < 50
            if rank and 11 <= rank <= 30 and dv < 50 and vs > 10:
                quick_wins.append({
                    **d,
                    "bucket": "quick_win",
                    "reason": f"You rank #{rank} — push to top 10 with title/subtitle optimization. Difficulty is only {dv:.0f}.",
                    "priority_score": vs * 0.6 + (100 - dv) * 0.4,
                })

            # High-Value Gaps: competitor ranks top 10, you don't rank or rank >30
            elif is_gap or (
                comp_rank and comp_rank <= 10 and (rank is None or rank > 30) and vs > 15
            ):
                high_value_gaps.append({
                    **d,
                    "bucket": "high_value_gap",
                    "reason": f"Competitors rank #{comp_rank or '?'} but you {'do not rank' if rank is None else f'rank #{rank}'}. Volume score: {vs:.0f}.",
                    "priority_score": vs * 0.7 + (100 - (dv or 50)) * 0.3,
                })

            # Defend: you rank top 5, competitor is close behind
            elif rank and rank <= 5 and comp_rank and comp_rank <= 15:
                defend.append({
                    **d,
                    "bucket": "defend",
                    "reason": f"You rank #{rank} but competitors are at #{comp_rank}. Maintain your position.",
                    "priority_score": vs * 0.5 + (15 - comp_rank) * 3,
                })

            # Untapped: high volume + low difficulty, no one dominates
            elif vs >= 40 and dv < 35 and (rank is None or rank > 20):
                untapped.append({
                    **d,
                    "bucket": "untapped",
                    "reason": f"High volume ({vs:.0f}) with low difficulty ({dv:.0f}). No strong incumbents.",
                    "priority_score": vs * 0.5 + (100 - dv) * 0.5,
                })

            # Long Tail: moderate volume, very low difficulty
            elif 10 < vs < 40 and dv < 25 and (rank is None or rank > 10):
                long_tail.append({
                    **d,
                    "bucket": "long_tail",
                    "reason": f"Low competition ({dv:.0f}) with decent volume. Easy to rank for.",
                    "priority_score": vs * 0.4 + (100 - dv) * 0.6,
                })

        # Sort each bucket by priority_score desc and trim
        for bucket in [quick_wins, high_value_gaps, untapped, long_tail, defend]:
            bucket.sort(key=lambda x: -x["priority_score"])
            del bucket[_MAX_PER_BUCKET:]

        # Build final list, interleave buckets for variety
        suggestions: List[dict] = []
        ordered_buckets = [
            ("quick_win", quick_wins),
            ("high_value_gap", high_value_gaps),
            ("untapped", untapped),
            ("long_tail", long_tail),
            ("defend", defend),
        ]

        # Take top items from each bucket
        for _name, bucket in ordered_buckets:
            suggestions.extend(bucket)

        suggestions.sort(key=lambda x: -x["priority_score"])
        suggestions = suggestions[:_MAX_TOTAL]

        # Clean output (remove internal priority_score)
        for s in suggestions:
            s.pop("priority_score", None)

        return {
            "app_id": app.id,
            "app_name": app.name,
            "suggestions": suggestions,
            "total": len(suggestions),
            "bucket_counts": {
                "quick_wins": len(quick_wins),
                "high_value_gaps": len(high_value_gaps),
                "untapped": len(untapped),
                "long_tail": len(long_tail),
                "defend": len(defend),
            },
        }
