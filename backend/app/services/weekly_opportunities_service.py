"""
weekly_opportunities_service.py
================================
Top-5 Opportunities This Week — TTL-based caching (12-hour refresh within the same week).

Caching strategy:
  - Week key = Monday's date (ISO week start).
  - If 5 rows already exist for this week_start_date AND none is older than
    _WEEKLY_TTL_HOURS, return them immediately (cache hit).
  - Otherwise call _generate_and_store() which:
      1. Fetches all scored candidates from ScoringEngine.get_all_scored_opportunities().
      2. Applies the weekly scoring formula:
             opportunity_score = trend_score * 0.5
                               + (100 - competition_score) * 0.3
                               + success_probability * 0.2
      3. Re-sorts by opportunity_score, takes top 5, deduplicating by niche (best
         per niche so the list is diverse).
      4. Assigns ranks 1–5.
      5. For each enriches with related_apps + ai_summary.
      6. Upserts all 5 rows via pg_insert ON CONFLICT DO UPDATE.

Related apps: improved _get_related_apps() — no current_rank requirement,
primary_category fallback when Category lookup fails.

AI summary: _build_weekly_ai_summary() frames the opportunity in a "this week" context.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.models import App, Category, WeeklyOpportunity
from app.scoring.engine import ScoringEngine

logger = logging.getLogger(__name__)

# Weekly scoring formula weights
_W_TREND = 0.5
_W_COMPETITION = 0.3
_W_SUCCESS = 0.2

# Cache TTL: regenerate within the same week if rows are older than this
_WEEKLY_TTL_HOURS = 12


def _week_start(d: date) -> date:
    """Return the Monday of the ISO week containing date d."""
    return d - timedelta(days=d.weekday())


def _opportunity_score(candidate: dict) -> float:
    trend = candidate.get("trend_score") or 0.0
    comp = candidate.get("competition_score")
    if comp is None:
        comp = 50.0
    success = candidate.get("success_probability") or 0.0
    return round(trend * _W_TREND + (100.0 - comp) * _W_COMPETITION + success * _W_SUCCESS, 2)


class WeeklyOpportunitiesService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_generate(self) -> list[dict]:
        """
        Return this week's top-5 opportunities.
        Reads from DB if already computed within _WEEKLY_TTL_HOURS for this ISO week;
        generates + stores otherwise.
        """
        week_start = _week_start(date.today())

        existing = (
            self.db.query(WeeklyOpportunity)
            .filter(WeeklyOpportunity.week_start_date == week_start)
            .order_by(WeeklyOpportunity.rank)
            .all()
        )
        if len(existing) >= 5:
            # Check TTL against the oldest generated_at among the 5 rows
            stale = True
            try:
                gen_ats = [
                    r.generated_at for r in existing
                    if r.generated_at is not None
                ]
                if gen_ats:
                    oldest = min(gen_ats)
                    if oldest.tzinfo is None:
                        oldest = oldest.replace(tzinfo=timezone.utc)
                    age_hours = (datetime.now(timezone.utc) - oldest).total_seconds() / 3600
                    stale = age_hours >= _WEEKLY_TTL_HOURS
            except (TypeError, AttributeError):
                stale = True  # treat as stale if timestamps are invalid

            if not stale:
                logger.debug("[weekly-opp] cache hit for week %s", week_start)
                return [row.full_data for row in existing if row.full_data]
            logger.info("[weekly-opp] cache stale for week %s, regenerating", week_start)

        logger.info("[weekly-opp] generating for week %s", week_start)
        return self._generate_and_store(week_start)

    # ------------------------------------------------------------------
    # Internal: generate + persist
    # ------------------------------------------------------------------

    def _generate_and_store(self, week_start: date) -> list[dict]:
        engine = ScoringEngine(self.db)
        candidates = engine.get_all_scored_opportunities()

        if not candidates:
            logger.warning("[weekly-opp] no candidates from ScoringEngine")
            return []

        # Apply weekly formula and re-rank
        for c in candidates:
            c["opportunity_score"] = _opportunity_score(c)

        candidates.sort(key=lambda x: x["opportunity_score"], reverse=True)

        # Diversity: at most one entry per niche in the top-5
        top5 = self._pick_diverse_top5(candidates)

        if not top5:
            return []

        results: list[dict] = []
        now = datetime.now(timezone.utc)

        for rank, candidate in enumerate(top5, start=1):
            related_apps = self._get_related_apps(
                niche=candidate.get("category", ""),
                exclude_app_id=candidate.get("app_id"),
                limit=6,
            )
            ai_summary = self._build_weekly_ai_summary(candidate, rank)

            full_data = {
                **candidate,
                "rank": rank,
                "week_start_date": week_start.isoformat(),
                "ai_summary": ai_summary,
                "related_apps": related_apps,
            }

            stmt = pg_insert(WeeklyOpportunity).values(
                week_start_date=week_start,
                rank=rank,
                keyword=candidate.get("primary_keyword"),
                niche=candidate.get("category"),
                competition_score=candidate.get("competition_score"),
                trend_score=candidate.get("trend_score"),
                success_probability=candidate.get("success_probability"),
                opportunity_score=candidate.get("opportunity_score"),
                ai_summary=ai_summary,
                related_apps=related_apps,
                full_data=full_data,
                generated_at=now,
            ).on_conflict_do_update(
                index_elements=["week_start_date", "rank"],
                set_={
                    "keyword": candidate.get("primary_keyword"),
                    "niche": candidate.get("category"),
                    "competition_score": candidate.get("competition_score"),
                    "trend_score": candidate.get("trend_score"),
                    "success_probability": candidate.get("success_probability"),
                    "opportunity_score": candidate.get("opportunity_score"),
                    "ai_summary": ai_summary,
                    "related_apps": related_apps,
                    "full_data": full_data,
                    "generated_at": now,
                },
            )
            self.db.execute(stmt)
            results.append(full_data)

        self.db.commit()
        logger.info("[weekly-opp] stored %d opportunities for week %s", len(results), week_start)
        return results

    # ------------------------------------------------------------------
    # Diversity: one opportunity per niche
    # ------------------------------------------------------------------

    def _pick_diverse_top5(self, candidates: list[dict]) -> list[dict]:
        """
        Select the top-5 by opportunity_score with at most one per niche.
        Falls back to duplicating niches only when < 5 unique niches available.
        """
        seen_niches: set[str] = set()
        diverse: list[dict] = []

        # First pass: one per niche
        for c in candidates:
            niche = (c.get("category") or "general").lower()
            if niche not in seen_niches:
                seen_niches.add(niche)
                diverse.append(c)
            if len(diverse) == 5:
                return diverse

        # Second pass: fill remaining slots with best duplicates if needed
        for c in candidates:
            if len(diverse) == 5:
                break
            if c not in diverse:
                diverse.append(c)

        return diverse[:5]

    # ------------------------------------------------------------------
    # Related apps: same niche, prefer weaker competitors
    # No current_rank requirement — falls back to primary_category text match
    # ------------------------------------------------------------------

    def _get_related_apps(
        self,
        niche: str,
        exclude_app_id: Optional[int],
        limit: int = 6,
    ) -> list:
        """
        Return up to `limit` apps in the same category as the opportunity.

        Lookup strategy:
          1. Category.name prefix match (case-insensitive)
          2. Category.name contains match (if prefix fails)
          3. App.primary_category text match (if no Category row found)

        Ranking: ranked apps first (nullslast), then low rating, then low reviews.
        Does NOT require current_rank to be non-null.
        """
        if not niche:
            return []
        try:
            # Step 1: prefix match
            category = (
                self.db.query(Category)
                .filter(Category.name.ilike(f"{niche}%"))
                .first()
            )
            # Step 2: broader contains match
            if not category:
                category = (
                    self.db.query(Category)
                    .filter(Category.name.ilike(f"%{niche}%"))
                    .first()
                )

            # Step 3: build base query
            if category:
                query = self.db.query(App).filter(App.category_id == category.id)
            else:
                query = self.db.query(App).filter(
                    App.primary_category.ilike(f"%{niche}%")
                )

            if exclude_app_id:
                query = query.filter(App.id != exclude_app_id)

            apps = (
                query
                .order_by(
                    App.current_rank.asc().nullslast(),
                    App.current_rating.asc().nullslast(),
                    App.current_reviews.asc().nullslast(),
                )
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": app.id,
                    "name": app.name,
                    "rating": app.current_rating,
                    "reviews": app.current_reviews,
                    "rank": app.current_rank,
                    "icon_url": app.icon_url,
                    "category": niche,
                }
                for app in apps
            ]
        except Exception as exc:
            logger.warning("[weekly-opp] _get_related_apps error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Rule-based weekly AI summary
    # ------------------------------------------------------------------

    def _build_weekly_ai_summary(self, candidate: dict, rank: int) -> str:
        keyword = candidate.get("primary_keyword") or "this niche"
        category = candidate.get("category") or "apps"
        competition = candidate.get("competition_score", 50.0) or 50.0
        feasibility = candidate.get("feasibility_score", 50.0) or 50.0
        success_prob = candidate.get("success_probability", 0.0) or 0.0
        opp_score = candidate.get("opportunity_score", 0.0) or 0.0
        trend = candidate.get("trend_score", 0.0) or 0.0
        gap_count = (candidate.get("feasibility_details") or {}).get("gap_count", 0)
        ai_potential = candidate.get("ai_integration_potential", 0.0) or 0.0

        parts: list[str] = []

        # Rank context
        ordinals = {1: "top", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}
        rank_label = ordinals.get(rank, f"#{rank}")

        # Lead: rank + keyword + category
        if opp_score >= 65:
            parts.append(
                f"This week's {rank_label} opportunity: the '{keyword}' niche in {category} "
                f"shows exceptional potential (opportunity score {opp_score:.0f}/100)."
            )
        elif opp_score >= 45:
            parts.append(
                f"Ranked {rank_label} this week: '{keyword}' in {category} "
                f"is a solid opportunity with a score of {opp_score:.0f}/100."
            )
        else:
            parts.append(
                f"This week's {rank_label} pick: '{keyword}' in {category} "
                f"offers an early-mover advantage (score {opp_score:.0f}/100)."
            )

        # Middle: competition + feasibility
        if competition < 35:
            comp_phrase = "very low keyword competition"
        elif competition < 55:
            comp_phrase = "moderate competition"
        else:
            comp_phrase = "high competition — focus on a sub-niche"

        if feasibility >= 65:
            parts.append(
                f"With {comp_phrase} and high feasibility ({feasibility:.0f}/100), "
                "this is realistically winnable for an indie developer."
            )
        elif gap_count >= 2:
            parts.append(
                f"Despite {comp_phrase}, {gap_count} user-reported feature gaps create "
                "a clear differentiation path for a quality-focused entrant."
            )
        else:
            parts.append(
                f"The space has {comp_phrase} and a feasibility of {feasibility:.0f}/100 — "
                "a focused, differentiated product is the recommended approach."
            )

        # Closing: trend or AI angle
        if trend >= 60:
            parts.append(
                f"Trending momentum is strong ({trend:.0f}/100) — now is the right time to enter."
            )
        elif ai_potential >= 70:
            parts.append(
                f"High AI integration potential ({ai_potential:.0f}/100) could be a key differentiator."
            )
        elif success_prob >= 65:
            parts.append(
                f"Success probability stands at {success_prob:.0f}% — above average for this category."
            )

        return " ".join(parts)
