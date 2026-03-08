"""
Review Intelligence Service (LLM-powered)
==========================================
Uses Claude Haiku to batch-analyze negative reviews and extract:
  1. Unmet feature requests
  2. Competitor comparisons
  3. Pricing complaints
  4. Key pain points

Results are cached in AppAnalytics.common_complaints and a new
llm_insight field (stored in signals JSON on AppAnalytics if present,
otherwise returned directly).
"""
import json
import logging
import os
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import App, Review, AppAnalytics

logger = logging.getLogger(__name__)

_BATCH_SIZE = 80  # reviews per LLM call
_MAX_REVIEW_CHARS = 300  # truncate individual reviews
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _get_anthropic_client():
    """Lazy import Anthropic client to avoid import errors if not installed."""
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")


_ANALYSIS_PROMPT = """You are analyzing {n} negative App Store reviews for the app "{app_name}".

Reviews:
{reviews_text}

Extract and return a JSON object with these fields:
{{
  "feature_requests": ["list of distinct missing features users want"],
  "competitor_mentions": ["list of competitor apps/services mentioned"],
  "pricing_complaints": ["list of specific pricing complaints"],
  "pain_points": ["list of top recurring pain points"],
  "sentiment_summary": "one sentence summary of overall negative sentiment",
  "opportunity_score": 0-100 (how big is the opportunity to build a better alternative)
}}

Be specific and concise. Return only valid JSON."""


class ReviewIntelligenceService:
    def __init__(self, db: Session):
        self.db = db

    def analyze_app(self, app_id: int, force: bool = False) -> Dict:
        """
        Run LLM analysis on recent negative reviews for an app.
        Results are saved back to AppAnalytics.

        Returns the analysis dict.
        """
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return self._empty("App not found")

        # Check if cached (skip if analytics has recent llm data and not forced)
        analytics = (
            self.db.query(AppAnalytics)
            .filter(AppAnalytics.app_id == app_id)
            .order_by(AppAnalytics.computed_at.desc())
            .first()
        )

        if not force and analytics and analytics.common_complaints:
            # Check if it looks like LLM data (has 'feature_requests' key in a stored dict)
            existing = analytics.common_complaints
            if isinstance(existing, list) and len(existing) > 0 and isinstance(existing[0], dict):
                if "feature_requests" in existing[0]:
                    return existing[0]

        # Fetch negative reviews (rating <= 2)
        neg_reviews = (
            self.db.query(Review)
            .filter(
                Review.app_id == app_id,
                Review.rating <= 2,
                Review.content.isnot(None),
                Review.content != "",
            )
            .order_by(Review.date.desc())
            .limit(_BATCH_SIZE)
            .all()
        )

        if not neg_reviews:
            return self._empty("No negative reviews found")

        # Build review text block
        reviews_text = "\n---\n".join(
            f"[{r.rating}★] {(r.content or '')[:_MAX_REVIEW_CHARS]}"
            for r in neg_reviews
        )

        prompt = _ANALYSIS_PROMPT.format(
            n=len(neg_reviews),
            app_name=app.name,
            reviews_text=reviews_text,
        )

        try:
            client = _get_anthropic_client()
            message = client.messages.create(
                model=_DEFAULT_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()

            # Parse JSON from response
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw)
        except Exception as exc:
            logger.error(f"LLM review analysis failed for app {app_id}: {exc}")
            return self._empty(f"LLM error: {exc}")

        result["app_id"] = app_id
        result["app_name"] = app.name
        result["reviews_analyzed"] = len(neg_reviews)

        # Persist to AppAnalytics.common_complaints as [result]
        if analytics:
            analytics.common_complaints = [result]
            self.db.commit()
        else:
            new_analytics = AppAnalytics(
                app_id=app_id,
                common_complaints=[result],
            )
            self.db.add(new_analytics)
            self.db.commit()

        logger.info(
            f"Review intelligence computed for app {app_id}: "
            f"{len(result.get('feature_requests', []))} feature requests found"
        )
        return result

    def get_cached(self, app_id: int) -> Optional[Dict]:
        """Return cached LLM analysis without re-running."""
        analytics = (
            self.db.query(AppAnalytics)
            .filter(AppAnalytics.app_id == app_id)
            .order_by(AppAnalytics.computed_at.desc())
            .first()
        )
        if not analytics or not analytics.common_complaints:
            return None
        existing = analytics.common_complaints
        if isinstance(existing, list) and len(existing) > 0 and isinstance(existing[0], dict):
            if "feature_requests" in existing[0]:
                return existing[0]
        return None

    @staticmethod
    def _empty(reason: str) -> Dict:
        return {
            "feature_requests": [],
            "competitor_mentions": [],
            "pricing_complaints": [],
            "pain_points": [],
            "sentiment_summary": reason,
            "opportunity_score": 0,
            "reviews_analyzed": 0,
        }
