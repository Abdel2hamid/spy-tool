"""
opportunity_of_day_service.py
==============================
get_or_generate() — same-day caching pattern:
  1. Check daily_opportunities table for today's date.
  2. If found, return immediately (read-only, <1ms).
  3. If not found, run _generate_and_store() which:
     a. Calls ScoringEngine.generate_opportunity_of_day() for the best app.
     b. Enriches with _get_related_apps() (5–10 same-niche apps, weak competitors first).
     c. Generates _build_ai_summary() (rule-based, no LLM).
     d. Persists to daily_opportunities via pg_insert ON CONFLICT DO UPDATE.
  4. Returns the enriched dict.

Also writes to DailyReport (legacy) so existing endpoint is unaffected.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.models import App, AppBlowingUpScore, Category, DailyOpportunity, DailyReport
from app.scoring.engine import ScoringEngine

logger = logging.getLogger(__name__)


class OpportunityOfDayService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_generate(self) -> Optional[dict]:
        """
        Return today's Opportunity of the Day.
        Reads from DB if already computed today; otherwise generates, stores, and returns.
        """
        today = date.today()

        # Fast path: already computed today
        existing = (
            self.db.query(DailyOpportunity)
            .filter(DailyOpportunity.date == today)
            .first()
        )
        if existing and existing.full_data:
            logger.debug("[opp-of-day] cache hit for %s", today)
            return existing.full_data

        # Slow path: generate and persist
        logger.info("[opp-of-day] generating for %s", today)
        result = self._generate_and_store(today)
        return result

    # ------------------------------------------------------------------
    # Internal: generate + persist
    # ------------------------------------------------------------------

    def _generate_and_store(self, today: date) -> Optional[dict]:
        engine = ScoringEngine(self.db)
        opportunity = engine.generate_opportunity_of_day()
        if not opportunity:
            logger.warning("[opp-of-day] ScoringEngine returned no opportunity")
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
    # Related apps: same niche, prefer weaker competitors
    # ------------------------------------------------------------------

    def _get_related_apps(
        self,
        niche: str,
        exclude_app_id: Optional[int],
        limit: int = 8,
    ) -> list:
        """
        Return up to `limit` apps in the same category as the opportunity app.
        Preference order:
          1. Apps with low rating (< 3.8) — quality gap
          2. Apps with low review count — early-mover opportunity
          3. Apps currently ranked (has chart presence)
        Excludes the opportunity app itself.
        """
        if not niche:
            return []

        try:
            # Find category by name (case-insensitive prefix match)
            category = (
                self.db.query(Category)
                .filter(Category.name.ilike(f"{niche}%"))
                .first()
            )
            if not category:
                return []

            query = (
                self.db.query(App)
                .filter(
                    App.category_id == category.id,
                    App.current_rank.isnot(None),
                )
            )
            if exclude_app_id:
                query = query.filter(App.id != exclude_app_id)

            # Sort: low rating first (weaker competitors), then by low review count
            apps = (
                query
                .order_by(
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
    # Rule-based AI summary (no LLM dependency)
    # ------------------------------------------------------------------

    def _build_ai_summary(self, opportunity: dict) -> str:
        """
        Generate a concise, actionable 2–3 sentence summary of the opportunity.
        Uses the structured fields from ScoringEngine.generate_opportunity_of_day().
        """
        keyword = opportunity.get("primary_keyword") or "this niche"
        category = opportunity.get("category") or "apps"
        competition = opportunity.get("competition_score", 50.0)
        feasibility = opportunity.get("feasibility_score", 50.0)
        attractiveness = opportunity.get("attractiveness_score", 50.0)
        success_prob = opportunity.get("success_probability", 0.0)
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
        if competition < 35:
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
