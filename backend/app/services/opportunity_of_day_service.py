"""
opportunity_of_day_service.py
==============================
get_or_generate() — TTL-based caching pattern (4-hour refresh):
  1. Check daily_opportunities table for today's date.
  2. If found AND generated_at is within _DAILY_TTL_HOURS, return immediately (cache hit).
  3. If not found OR stale, run _generate_and_store() which:
     a. Calls ScoringEngine.get_all_scored_opportunities(n=10) for the candidate pool.
     b. Uses _select_daily_pick() for controlled diversity (avoids repeating recent apps).
     c. Enriches with _get_related_apps() (same-niche apps; no current_rank requirement).
     d. Generates _build_ai_summary() (rule-based, no LLM).
     e. Persists to daily_opportunities via pg_insert ON CONFLICT DO UPDATE.
  4. Returns the enriched dict.

Also writes to DailyReport (legacy) so existing endpoint is unaffected.

Diversity logic:
  - Pool = top 5 candidates within 80% of the top success_probability score.
  - Exclude apps shown in the last 7 days (from daily_opportunities history).
  - Use day-ordinal % pool_size for deterministic rotation (same result within a day,
    different across days).
  - Falls back to full pool if all candidates were recently shown.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.models import App, AppBlowingUpScore, Category, DailyOpportunity, DailyReport
from app.scoring.engine import ScoringEngine

logger = logging.getLogger(__name__)

# Cache TTL: regenerate if the stored row is older than this many hours
_DAILY_TTL_HOURS = 4


class OpportunityOfDayService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_generate(self) -> Optional[dict]:
        """
        Return today's Opportunity of the Day.
        Reads from DB if computed within _DAILY_TTL_HOURS; otherwise regenerates.
        """
        today = date.today()

        existing = (
            self.db.query(DailyOpportunity)
            .filter(DailyOpportunity.date == today)
            .first()
        )
        if existing and existing.full_data:
            if not self._is_stale(existing.generated_at, _DAILY_TTL_HOURS):
                logger.debug("[opp-of-day] cache hit for %s", today)
                return existing.full_data
            logger.info("[opp-of-day] cache stale for %s, regenerating", today)

        logger.info("[opp-of-day] generating for %s", today)
        return self._generate_and_store(today)

    # ------------------------------------------------------------------
    # Internal: generate + persist
    # ------------------------------------------------------------------

    def _generate_and_store(self, today: date) -> Optional[dict]:
        engine = ScoringEngine(self.db)
        # Fetch top-N candidates for diversity selection
        scored = engine.get_all_scored_opportunities(n=10)
        if not scored:
            logger.warning("[opp-of-day] ScoringEngine returned no candidates")
            return None

        opportunity = self._select_daily_pick(scored, today)
        if not opportunity:
            return None

        related_apps = self._get_related_apps(
            niche=opportunity.get("category", ""),
            exclude_app_id=opportunity.get("app_id"),
            limit=8,
        )

        ai_summary = self._build_ai_summary(opportunity)

        full_data = {
            **opportunity,
            "ai_summary": ai_summary,
            "related_apps": related_apps,
        }

        # Persist to new daily_opportunities table
        stmt = pg_insert(DailyOpportunity).values(
            date=today,
            keyword=opportunity.get("primary_keyword"),
            niche=opportunity.get("category"),
            competition_score=opportunity.get("competition_score"),
            trend_score=opportunity.get("trend_score"),
            success_probability=opportunity.get("success_probability"),
            ai_summary=ai_summary,
            related_apps=related_apps,
            full_data=full_data,
            generated_at=datetime.now(timezone.utc),
        ).on_conflict_do_update(
            index_elements=["date"],
            set_={
                "keyword": opportunity.get("primary_keyword"),
                "niche": opportunity.get("category"),
                "competition_score": opportunity.get("competition_score"),
                "trend_score": opportunity.get("trend_score"),
                "success_probability": opportunity.get("success_probability"),
                "ai_summary": ai_summary,
                "related_apps": related_apps,
                "full_data": full_data,
                "generated_at": datetime.now(timezone.utc),
            },
        )
        self.db.execute(stmt)

        # Also keep legacy DailyReport in sync so existing endpoint still works
        legacy_stmt = pg_insert(DailyReport).values(
            date=today,
            opportunity_of_day=opportunity,
        ).on_conflict_do_update(
            index_elements=["date"],
            set_={"opportunity_of_day": opportunity},
        )
        self.db.execute(legacy_stmt)

        self.db.commit()
        logger.info("[opp-of-day] stored opportunity for %s (app_id=%s)", today, opportunity.get("app_id"))
        return full_data

    # ------------------------------------------------------------------
    # Diversity: rotate among top candidates, avoid repeating recent picks
    # ------------------------------------------------------------------

    def _select_daily_pick(self, scored: list, today: date) -> Optional[dict]:
        """
        Pick today's opportunity with controlled diversity.

        Pool = up to 5 candidates within 80% of the top success_probability score.
        - Exclude apps shown in daily_opportunities over the last 7 days.
        - If all pool candidates were recently shown, fall back to the full pool.
        - Use today.toordinal() % pool_size as a deterministic index so the same
          day always returns the same pick, but different days rotate through the pool.
        """
        if not scored:
            return None

        # Build pool: candidates within 80% of the top score, capped at 5
        top_score = scored[0]["success_probability"]
        min_score = top_score * 0.80
        pool = [c for c in scored[:10] if c["success_probability"] >= min_score][:5]

        # Fetch recent history to avoid repetition
        cutoff = today - timedelta(days=7)
        try:
            recent_rows = (
                self.db.query(DailyOpportunity)
                .filter(DailyOpportunity.date >= cutoff, DailyOpportunity.date < today)
                .all()
            )
            recent_app_ids = {
                row.full_data["app_id"]
                for row in recent_rows
                if row.full_data and row.full_data.get("app_id")
            }
        except Exception:
            recent_app_ids = set()

        fresh = [c for c in pool if c["app_id"] not in recent_app_ids]
        candidates = fresh if fresh else pool

        idx = today.toordinal() % len(candidates)
        return candidates[idx]

    # ------------------------------------------------------------------
    # Related apps: same niche, prefer weaker competitors
    # No current_rank requirement — fall back to primary_category if needed
    # ------------------------------------------------------------------

    def _get_related_apps(
        self,
        niche: str,
        exclude_app_id: Optional[int],
        limit: int = 8,
    ) -> list:
        """
        Return up to `limit` apps in the same category as the opportunity app.

        Lookup strategy:
          1. Category.name prefix match (case-insensitive)
          2. Category.name contains match (if prefix fails)
          3. App.primary_category text match (if no Category row found)

        Ranking: ranked apps first (nullslast), then low rating, then low review count.
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
                # Fallback: match against stored primary_category text
                query = self.db.query(App).filter(
                    App.primary_category.ilike(f"%{niche}%")
                )

            if exclude_app_id:
                query = query.filter(App.id != exclude_app_id)

            # Ranked apps first (nullslast), then weak competitors
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
            logger.warning("[opp-of-day] _get_related_apps error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Cache freshness check
    # ------------------------------------------------------------------

    @staticmethod
    def _is_stale(generated_at: Optional[datetime], ttl_hours: float) -> bool:
        """Return True if generated_at is None, unparseable, or older than ttl_hours."""
        if generated_at is None:
            return True
        try:
            if generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - generated_at).total_seconds() / 3600
            return age_hours >= ttl_hours
        except (TypeError, AttributeError):
            return True  # treat as stale if timestamp is invalid

    # ------------------------------------------------------------------
    # Rule-based AI summary (no LLM dependency)
    # ------------------------------------------------------------------

    def _build_ai_summary(self, opportunity: dict) -> str:
        """
        Generate a concise, actionable 2–3 sentence summary of the opportunity.
        Uses the structured fields from ScoringEngine.generate_opportunity_of_day().
        """
        keyword = opportunity.get("primary_keyword") or "this niche"
        category = opportunity.get("category") or "apps"
        competition = opportunity.get("competition_score")  # None if unavailable
        feasibility = opportunity.get("feasibility_score") or 0.0
        attractiveness = opportunity.get("attractiveness_score") or 0.0
        success_prob = opportunity.get("success_probability") or 0.0
        rank_velocity = opportunity.get("rank_velocity", 0.0)
        review_growth = opportunity.get("review_growth", 0.0)
        feasibility_details = opportunity.get("feasibility_details") or {}
        gap_count = feasibility_details.get("gap_count", 0)
        ai_potential = opportunity.get("ai_integration_potential", 0.0)

        parts: list[str] = []

        # Lead sentence: opportunity strength
        if success_prob >= 70:
            parts.append(
                f"Strong opportunity in the {category} space around '{keyword}' "
                f"— high success probability ({success_prob:.0f}%) signals an under-served niche."
            )
        elif success_prob >= 50:
            parts.append(
                f"Solid opportunity in {category} around '{keyword}' "
                f"with a {success_prob:.0f}% success probability and manageable competition."
            )
        else:
            parts.append(
                f"Emerging opportunity in {category} around '{keyword}' "
                f"— early-mover advantage is still available."
            )

        # Middle sentence: competition + feasibility signal
        if competition is None:
            comp_desc = "unknown competition level"
        elif competition < 35:
            comp_desc = "very low keyword competition"
        elif competition < 55:
            comp_desc = "moderate competition"
        else:
            comp_desc = "high competition"

        if feasibility >= 65:
            parts.append(
                f"With {comp_desc} and a high feasibility score ({feasibility:.0f}/100), "
                "indie developers can realistically rank here with quality execution."
            )
        elif gap_count >= 2:
            parts.append(
                f"Users are vocal about missing features ({gap_count} reported gaps), "
                f"giving a new entrant a clear differentiation path despite {comp_desc}."
            )
        else:
            parts.append(
                f"The space shows {comp_desc} and a feasibility of {feasibility:.0f}/100 "
                "— a focused niche strategy is recommended."
            )

        # Closing: momentum or AI angle
        if rank_velocity > 5 or review_growth > 10:
            parts.append(
                "Momentum signals are positive: rankings are improving and review volume is growing."
            )
        elif ai_potential >= 70:
            parts.append(
                f"AI integration potential is high ({ai_potential:.0f}/100) — "
                "building AI-powered features here could be a strong differentiator."
            )
        elif attractiveness >= 65:
            parts.append(
                f"Market attractiveness is strong ({attractiveness:.0f}/100), "
                "indicating healthy demand in this category."
            )

        return " ".join(parts)
