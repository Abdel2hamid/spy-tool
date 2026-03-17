"""
Confidence Engine
=================
Bayesian confidence scorer for download estimates.

Pure functions — no DB access, no side effects.
Takes a signals dict, returns a structured confidence assessment.

Confidence factors (all multiplicative):
  snapshot_factor    = sqrt(min(ranking_history_days / 30, 1.0))
  completeness_factor= 0.5 + 0.125 × count of present signal flags
  freshness_factor   = 1.0 if <2d, 0.85 if <7d, 0.70 if <30d, 0.50 if older
  category_factor    = CATEGORY_CURVE_RELIABILITY[category]
  review_factor      = min(log(review_count+1) / log(1001), 1.0)

Final confidence = product of all factors, capped by calibration_ceiling.
"""

import math
from typing import Optional

from app.config.rank_curves import get_category_reliability
from app.config.calibration_profiles import get_calibration


class ConfidenceEngine:
    """
    Computes a structured confidence score from a signals dict.

    Example:
        engine = ConfidenceEngine()
        result = engine.compute(signals)
        # result["confidence_score"] → float 0–1
        # result["confidence_label"] → "low" | "medium" | "high"
        # result["factors"] → breakdown dict
    """

    def compute(self, signals: dict) -> dict:
        """
        Compute confidence score from signals.

        Signals keys consumed:
          ranking_history_days  — int (days of ranking data available; 0 if none)
          has_rank              — bool (app currently has a chart rank)
          has_velocity          — bool (review velocity > 0)
          has_keywords          — bool (keyword intelligence data exists)
          has_momentum          — bool (AppTrendingScore row exists)
          data_age_days         — int (days since last_scrape; 0 = fresh)
          review_count          — int (total review count)
          category              — str (primary category)

        Returns:
          {
            "confidence_score": float,    # 0–1
            "confidence_label": str,      # "low" | "medium" | "high"
            "factors": {
              "ranking_history": float,
              "signal_completeness": float,
              "data_freshness": float,
              "category_reliability": float,
              "review_coverage": float,
            }
          }
        """
        # --- Factor 1: Ranking history depth ---
        history_days = max(int(signals.get("ranking_history_days", 0)), 0)
        snapshot_factor = math.sqrt(min(history_days / 30.0, 1.0))

        # --- Factor 2: Signal completeness ---
        signal_flags = [
            bool(signals.get("has_rank", False)),
            bool(signals.get("has_velocity", False)),
            bool(signals.get("has_keywords", False)),
            bool(signals.get("has_momentum", False)),
        ]
        completeness_factor = 0.5 + 0.125 * sum(signal_flags)

        # --- Factor 3: Data freshness ---
        data_age = max(int(signals.get("data_age_days", 0)), 0)
        if data_age < 2:
            freshness_factor = 1.0
        elif data_age < 7:
            freshness_factor = 0.85
        elif data_age < 30:
            freshness_factor = 0.70
        else:
            freshness_factor = 0.50

        # --- Factor 4: Category reliability ---
        category = signals.get("category", "") or ""
        category_factor = get_category_reliability(category)

        # --- Factor 5: Review coverage ---
        review_count = max(int(signals.get("review_count", 0)), 0)
        if review_count == 0:
            review_factor = 0.50
        else:
            review_factor = min(
                math.log(review_count + 1) / math.log(1001),
                1.0,
            )

        # --- Multiply all factors ---
        raw_confidence = (
            snapshot_factor
            * completeness_factor
            * freshness_factor
            * category_factor
            * review_factor
        )

        # --- Apply calibration ceiling ---
        calibration = get_calibration(category)
        ceiling = calibration.get("confidence_ceiling", 0.82)
        confidence = min(raw_confidence, ceiling)
        confidence = max(confidence, 0.0)

        label = self._label(confidence)

        return {
            "confidence_score": round(confidence, 3),
            "confidence_label": label,
            "factors": {
                "ranking_history": round(snapshot_factor, 3),
                "signal_completeness": round(completeness_factor, 3),
                "data_freshness": round(freshness_factor, 3),
                "category_reliability": round(category_factor, 3),
                "review_coverage": round(review_factor, 3),
            },
        }

    def _uncertainty_factor(self, confidence: float, signals: Optional[dict] = None) -> float:
        """
        Returns uncertainty multiplier for the download range.

        confidence=1.0 → ±30% range around estimate
        confidence=0.3 → ±100% range around estimate

        Formula: uncertainty = 0.30 + (1 - confidence) × 0.70
        Bounded to [0.30, 1.00].
        """
        uncertainty = 0.30 + (1.0 - confidence) * 0.70
        return max(0.30, min(1.00, uncertainty))

    @staticmethod
    def _label(score: float) -> str:
        if score >= 0.65:
            return "high"
        if score >= 0.40:
            return "medium"
        return "low"
