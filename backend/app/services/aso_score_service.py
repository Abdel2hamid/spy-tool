"""
ASO Score Service
=================
Computes a 0–100 App Store Optimization score for an app based on
metadata quality, keyword coverage, ratings, and update freshness.

Sub-scores (each 0–100, weighted into a composite):
  • title_score      (20%) — keyword presence in name + subtitle length
  • description_score(15%) — length, keyword density, structure
  • visual_score     (15%) — screenshot count, icon presence
  • rating_score     (15%) — star rating + review count
  • keyword_score    (20%) — discovered keyword coverage + ranks
  • update_score     (15%) — recency of last update
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ASOScoreService:
    def __init__(self, db: Session):
        self.db = db

    def score(self, app_id: int) -> dict:
        from app.models.models import App, AppDiscoveredKeyword, AppKeywordIntelligence

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return {"error": "App not found"}

        tips: List[dict] = []

        # ── 1. Title & Subtitle Score (20%) ────────────────────────
        title_score = self._score_title(app, tips)

        # ── 2. Description Score (15%) ─────────────────────────────
        desc_score = self._score_description(app, tips)

        # ── 3. Visual Score (15%) ──────────────────────────────────
        visual_score = self._score_visuals(app, tips)

        # ── 4. Rating & Reviews Score (15%) ────────────────────────
        rating_score = self._score_ratings(app, tips)

        # ── 5. Keyword Coverage Score (20%) ────────────────────────
        keyword_score = self._score_keywords(app, tips)

        # ── 6. Update Freshness Score (15%) ────────────────────────
        update_score = self._score_updates(app, tips)

        # ── Composite ──────────────────────────────────────────────
        overall = round(
            title_score * 0.20
            + desc_score * 0.15
            + visual_score * 0.15
            + rating_score * 0.15
            + keyword_score * 0.20
            + update_score * 0.15
        )

        # Grade
        if overall >= 80:
            grade = "A"
        elif overall >= 60:
            grade = "B"
        elif overall >= 40:
            grade = "C"
        elif overall >= 20:
            grade = "D"
        else:
            grade = "F"

        # Sort tips: high impact first
        priority_order = {"high": 0, "medium": 1, "low": 2}
        tips.sort(key=lambda t: priority_order.get(t.get("impact", "low"), 3))

        return {
            "overall_score": overall,
            "grade": grade,
            "breakdown": {
                "title": {"score": title_score, "weight": 20, "label": "Title & Subtitle"},
                "description": {"score": desc_score, "weight": 15, "label": "Description"},
                "visuals": {"score": visual_score, "weight": 15, "label": "Visuals"},
                "ratings": {"score": rating_score, "weight": 15, "label": "Ratings & Reviews"},
                "keywords": {"score": keyword_score, "weight": 20, "label": "Keyword Coverage"},
                "updates": {"score": update_score, "weight": 15, "label": "Update Freshness"},
            },
            "tips": tips[:8],
            "app_id": app.id,
            "app_name": app.name,
        }

    # ── Sub-score methods ──────────────────────────────────────────────

    def _score_title(self, app, tips: list) -> int:
        score = 0
        name = app.name or ""
        subtitle = app.subtitle or ""

        # Name length: 20-30 chars is ideal for App Store
        name_len = len(name)
        if 15 <= name_len <= 30:
            score += 40
        elif 10 <= name_len <= 40:
            score += 25
        elif name_len > 0:
            score += 10

        if name_len < 15:
            tips.append({
                "category": "title",
                "text": f"Your app name is only {name_len} chars. Use up to 30 chars to include keywords.",
                "impact": "high",
            })
        elif name_len > 30:
            tips.append({
                "category": "title",
                "text": f"Your app name is {name_len} chars — keep it under 30 for best readability.",
                "impact": "medium",
            })

        # Subtitle presence and length (max 30 chars on App Store)
        sub_len = len(subtitle)
        if sub_len > 0:
            score += 30
            if 15 <= sub_len <= 30:
                score += 15
            elif sub_len < 15:
                tips.append({
                    "category": "title",
                    "text": f"Subtitle is only {sub_len} chars. Use all 30 chars to include more keywords.",
                    "impact": "medium",
                })
        else:
            tips.append({
                "category": "title",
                "text": "Add a subtitle — it's prime keyword real estate (30 chars).",
                "impact": "high",
            })

        # Has at least 2 words (not just a brand name)
        words = name.split()
        if len(words) >= 2:
            score += 15
        else:
            tips.append({
                "category": "title",
                "text": "Add a descriptive keyword after your brand name (e.g. 'MyApp - Meditation Timer').",
                "impact": "high",
            })

        return min(score, 100)

    def _score_description(self, app, tips: list) -> int:
        desc = app.description or ""
        desc_len = len(desc)
        score = 0

        if desc_len == 0:
            tips.append({
                "category": "description",
                "text": "Add a description — it's critical for ASO and user conversion.",
                "impact": "high",
            })
            return 0

        # Length: 2500-4000 chars ideal
        if desc_len >= 2500:
            score += 35
        elif desc_len >= 1500:
            score += 25
        elif desc_len >= 500:
            score += 15
        else:
            score += 5

        if desc_len < 1500:
            tips.append({
                "category": "description",
                "text": f"Description is {desc_len} chars. Aim for 2,500+ to improve keyword density.",
                "impact": "medium",
            })

        # Structure: has line breaks / paragraphs
        line_count = desc.count("\n")
        if line_count >= 5:
            score += 20
        elif line_count >= 2:
            score += 10
        else:
            tips.append({
                "category": "description",
                "text": "Break your description into paragraphs for better readability.",
                "impact": "low",
            })

        # Has feature bullets or list markers
        has_bullets = bool(re.search(r"[•\-\*]|^\d+\.", desc, re.MULTILINE))
        if has_bullets:
            score += 15
        else:
            tips.append({
                "category": "description",
                "text": "Add bullet points to highlight key features — improves scan-ability.",
                "impact": "low",
            })

        # Word count variety (proxy for keyword richness)
        words = desc.lower().split()
        unique_ratio = len(set(words)) / max(len(words), 1)
        if unique_ratio >= 0.4:
            score += 15
        elif unique_ratio >= 0.3:
            score += 10
        else:
            score += 5

        # Has a call-to-action
        cta_patterns = r"download|try|get started|start|join|sign up|subscribe"
        if re.search(cta_patterns, desc.lower()):
            score += 15

        return min(score, 100)

    def _score_visuals(self, app, tips: list) -> int:
        score = 0
        screenshots = app.screenshots or []
        ss_count = len(screenshots)

        # Icon present
        if app.icon_url:
            score += 20
        else:
            tips.append({
                "category": "visuals",
                "text": "App icon is missing — this drastically reduces conversion.",
                "impact": "high",
            })

        # Screenshots: Apple allows up to 10, 5+ is great
        if ss_count >= 8:
            score += 60
        elif ss_count >= 5:
            score += 45
        elif ss_count >= 3:
            score += 25
        elif ss_count >= 1:
            score += 10
        else:
            tips.append({
                "category": "visuals",
                "text": "Add screenshots — apps with 5+ screenshots convert significantly better.",
                "impact": "high",
            })

        if 1 <= ss_count < 5:
            tips.append({
                "category": "visuals",
                "text": f"You have {ss_count} screenshot(s). Add at least 5 for optimal conversion.",
                "impact": "medium",
            })

        # Bonus for having many screenshots
        if ss_count >= 5:
            score += 20

        return min(score, 100)

    def _score_ratings(self, app, tips: list) -> int:
        score = 0
        rating = app.current_rating
        reviews = app.current_reviews or 0

        # Rating quality
        if rating is not None:
            if rating >= 4.5:
                score += 45
            elif rating >= 4.0:
                score += 35
            elif rating >= 3.5:
                score += 20
            elif rating >= 3.0:
                score += 10
            else:
                score += 5

            if rating < 4.0:
                tips.append({
                    "category": "ratings",
                    "text": f"Rating is {rating:.1f}. Focus on fixing user complaints to reach 4.0+.",
                    "impact": "high",
                })
        else:
            tips.append({
                "category": "ratings",
                "text": "No rating yet — encourage users to rate your app.",
                "impact": "medium",
            })

        # Review volume
        if reviews >= 10000:
            score += 40
        elif reviews >= 1000:
            score += 30
        elif reviews >= 100:
            score += 20
        elif reviews >= 10:
            score += 10
        elif reviews > 0:
            score += 5

        if reviews < 100:
            tips.append({
                "category": "ratings",
                "text": f"Only {reviews} reviews. Add an in-app rating prompt at moments of delight.",
                "impact": "medium",
            })

        # Bonus for high rating + many reviews
        if rating and rating >= 4.5 and reviews >= 1000:
            score += 15

        return min(score, 100)

    def _score_keywords(self, app, tips: list) -> int:
        from app.models.models import AppDiscoveredKeyword, AppKeywordIntelligence

        score = 0

        # Count discovered keywords
        disc_count = (
            self.db.query(func.count(AppDiscoveredKeyword.id))
            .filter(AppDiscoveredKeyword.app_id == app.id)
            .scalar()
        ) or 0

        # Count intelligence keywords
        intel_count = (
            self.db.query(func.count(AppKeywordIntelligence.id))
            .filter(AppKeywordIntelligence.app_id == app.id)
            .scalar()
        ) or 0

        total_kw = disc_count + intel_count

        if total_kw >= 100:
            score += 35
        elif total_kw >= 50:
            score += 25
        elif total_kw >= 20:
            score += 15
        elif total_kw > 0:
            score += 5

        if total_kw < 50:
            tips.append({
                "category": "keywords",
                "text": f"Only {total_kw} keywords tracked. Run keyword discovery to expand coverage.",
                "impact": "high" if total_kw < 20 else "medium",
            })

        # Keywords with top-10 rank
        top10_count = (
            self.db.query(func.count(AppDiscoveredKeyword.id))
            .filter(
                AppDiscoveredKeyword.app_id == app.id,
                AppDiscoveredKeyword.app_rank.isnot(None),
                AppDiscoveredKeyword.app_rank <= 10,
            )
            .scalar()
        ) or 0

        if top10_count >= 20:
            score += 35
        elif top10_count >= 10:
            score += 25
        elif top10_count >= 5:
            score += 15
        elif top10_count > 0:
            score += 5

        if top10_count < 5:
            tips.append({
                "category": "keywords",
                "text": f"You rank top 10 for only {top10_count} keywords. Optimize title/subtitle for high-volume terms.",
                "impact": "high",
            })

        # Gap keywords (opportunities to pursue)
        gap_count = (
            self.db.query(func.count(AppDiscoveredKeyword.id))
            .filter(
                AppDiscoveredKeyword.app_id == app.id,
                AppDiscoveredKeyword.keyword_gap == True,
            )
            .scalar()
        ) or 0

        if gap_count == 0:
            score += 30
        elif gap_count <= 5:
            score += 20
        elif gap_count <= 15:
            score += 10

        if gap_count > 5:
            tips.append({
                "category": "keywords",
                "text": f"{gap_count} keyword gaps found — competitors rank for these but you don't.",
                "impact": "medium",
            })

        return min(score, 100)

    def _score_updates(self, app, tips: list) -> int:
        score = 0
        last_updated = app.last_updated

        if last_updated is None:
            tips.append({
                "category": "updates",
                "text": "No update date available — keep your app updated regularly.",
                "impact": "low",
            })
            return 30  # Unknown, give benefit of doubt

        now = datetime.now(timezone.utc)
        if last_updated.tzinfo is None:
            from datetime import timezone as tz
            last_updated = last_updated.replace(tzinfo=tz.utc)

        days_since = (now - last_updated).days

        if days_since <= 30:
            score = 100
        elif days_since <= 60:
            score = 80
        elif days_since <= 90:
            score = 60
        elif days_since <= 180:
            score = 40
        elif days_since <= 365:
            score = 20
        else:
            score = 5

        if days_since > 90:
            tips.append({
                "category": "updates",
                "text": f"Last update was {days_since} days ago. Apple favors recently updated apps.",
                "impact": "high" if days_since > 180 else "medium",
            })

        return score
