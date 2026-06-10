"""
Download Estimator — 4-Layer Ensemble
======================================
Replaces the single-formula InstallEstimator with a multi-signal ensemble.

Architecture:
    Signals gathered once from DB → all 4 layers receive same signals dict
    Layer outputs are DAILY download estimates
    Ensemble combines → daily estimate
    Confidence + uncertainty → daily range
    × 30 → monthly figures
    Revenue delegated to RevenueEstimator (via routes.py)

Layers:
  L1 — Rank Curve      : category rank bands → daily download range
  L2 — Review Velocity : recent review rate × IR ratio → daily signal
  L3 — Visibility      : keyword footprint → organic discovery floor
  L4 — Momentum        : trending score adjustment (multiplicative)

Weights (default): rank=0.45, review=0.25, visibility=0.20
Momentum is a multiplicative modifier on the weighted sum (not a separate layer in the blend).

Backward compatibility:
  compute_and_save() writes to app.estimated_installs_min/max/install_confidence
  (same columns as InstallEstimator)
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import App, Ranking, Review, AppKeywordIntelligence, AppTrendingScore
from app.config.rank_curves import interpolate_rank_downloads
from app.config.calibration_profiles import get_calibration
from app.services.confidence_engine import ConfidenceEngine

logger = logging.getLogger(__name__)

# Install-review ratio: how many installs per 1 review (used in Layer 2)
_CATEGORY_IR_RATIO: Dict[str, float] = {
    "games": 1500.0,
    "entertainment": 1200.0,
    "social networking": 1000.0,
    "social": 1000.0,
    "photo & video": 500.0,
    "photo": 500.0,
    "music": 800.0,
    "health & fitness": 400.0,
    "health": 400.0,
    "fitness": 400.0,
    "sports": 600.0,
    "education": 350.0,
    "lifestyle": 400.0,
    "travel": 300.0,
    "food & drink": 450.0,
    "food": 450.0,
    "navigation": 350.0,
    "news": 500.0,
    "finance": 250.0,
    "business": 200.0,
    "productivity": 300.0,
    "utilities": 200.0,
    "reference": 200.0,
    "shopping": 500.0,
    "books": 250.0,
    "medical": 150.0,
    "weather": 350.0,
    "catalogs": 200.0,
    "graphics & design": 250.0,
    "developer tools": 150.0,
}
_DEFAULT_IR_RATIO = 400.0

# Anti-manipulation cap per category: maximum plausible daily downloads
_MAX_DAILY_BY_CATEGORY: Dict[str, int] = {
    "games": 2_000_000,
    "social networking": 1_500_000,
    "social": 1_500_000,
    "entertainment": 1_000_000,
    "productivity": 300_000,
    "finance": 200_000,
    "photo & video": 500_000,
    "photo": 500_000,
    "utilities": 200_000,
    "health & fitness": 300_000,
    "health": 300_000,
    "default": 500_000,
}
_MAX_REVIEW_VELOCITY = 500.0  # reviews/day ceiling (anti-spam)

# Shrinkage / conservative-baseline constants
_VISIBILITY_FOOTPRINT_SCALE = 1.5      # daily downloads per unit of keyword footprint (no base boost)
_IR_SCALING_REVIEWS = 100              # review_count where IR ratio reaches full strength
_MIN_BLEND_WEIGHT_WITH_RANK = 0.35     # minimum shrinkage blend when a chart rank is available
_FLOOR_WITH_RANK = 5.0                 # minimum daily downloads when app has a chart rank
_FLOOR_NO_RANK = 1.0                   # minimum daily downloads when app has no chart rank
_RANK_BASELINE_FRACTION = 0.30         # fraction of lo_band used as conservative ranked baseline


def _get_ir_ratio(category: Optional[str]) -> float:
    if not category:
        return _DEFAULT_IR_RATIO
    cat_lower = category.lower().strip()
    for key, ratio in _CATEGORY_IR_RATIO.items():
        if key in cat_lower or cat_lower in key:
            return ratio
    return _DEFAULT_IR_RATIO


def _max_plausible_daily(category: Optional[str]) -> int:
    if not category:
        return _MAX_DAILY_BY_CATEGORY["default"]
    cat_lower = category.lower().strip()
    for key, cap in _MAX_DAILY_BY_CATEGORY.items():
        if key == "default":
            continue
        if key in cat_lower or cat_lower in key:
            return cap
    return _MAX_DAILY_BY_CATEGORY["default"]


class DownloadEstimator:
    """
    4-layer ensemble download estimator.

    Usage:
        est = DownloadEstimator(db)
        result = est.estimate(app_id)   # full rich dict
        min_dl, max_dl, conf = est.compute_and_save(app)   # write to App columns
    """

    def __init__(self, db: Session):
        self.db = db
        self._confidence = ConfidenceEngine()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate(self, app_id: int) -> Dict:
        """Return full rich download estimate for a single app by DB integer ID."""
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return self._empty(app_id)
        return self._compute(app)

    def compute_and_save(self, app: App) -> Tuple[int, int, float]:
        """
        Compute estimate and write back to app record.
        Returns (installs_min, installs_max, confidence) for backward compat.
        """
        result = self._compute(app)
        app.estimated_installs_min = result["downloads_range_low"]
        app.estimated_installs_max = result["downloads_range_high"]
        app.install_confidence = result["estimation_confidence"]
        return (
            result["downloads_range_low"],
            result["downloads_range_high"],
            result["estimation_confidence"],
        )

    def compute_all(self) -> int:
        """Compute and save estimates for all tracked apps. Returns count updated."""
        from app.utils.batch_utils import iter_batches
        _BATCH = 200
        base_q = self.db.query(App).order_by(App.id)
        count = 0
        for batch in iter_batches(base_q, _BATCH):
            for app in batch:
                try:
                    self.compute_and_save(app)
                    count += 1
                except Exception as exc:
                    logger.warning(f"[download_estimator] Failed for app {app.app_id}: {exc}")
            self.db.commit()
            self.db.expire_all()
        logger.info(f"[download_estimator] Updated estimates for {count} apps")
        return count

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    def _compute(self, app: App) -> Dict:
        signals = self._gather_signals(app)

        l1 = self._layer1_rank_curve(signals)
        l2 = self._layer2_review_velocity(signals)
        l3 = self._layer3_visibility(signals)
        l4 = self._layer4_momentum(signals)

        weights = self._compute_weights(signals)

        # Weighted blend of the three additive layers
        daily_raw = (
            weights["rank"] * l1
            + weights["review"] * l2
            + weights["visibility"] * l3
        )

        # Momentum as a multiplicative adjustment
        daily_raw = daily_raw * (1.0 + l4)

        # Apply calibration factor
        category = signals.get("category", "")
        calib = get_calibration(category)
        daily_raw *= calib["rank_curve_factor"]

        # Anti-manipulation cap
        max_daily = _max_plausible_daily(category)
        daily_raw = min(daily_raw, max_daily)

        # --- Confidence-weighted shrinkage ---
        # Confidence is computed BEFORE the final estimate so it numerically affects it.
        # Low confidence pulls the estimate toward a conservative baseline rather than
        # letting weak signals produce large numbers.
        confidence_result = self._confidence.compute(signals)
        conf_score = confidence_result["confidence_score"]

        has_rank = signals.get("has_rank", False)
        blend_weight = math.sqrt(conf_score)
        if has_rank:
            blend_weight = max(blend_weight, _MIN_BLEND_WEIGHT_WITH_RANK)

        conservative = self._conservative_daily_baseline(signals)
        daily_base = blend_weight * daily_raw + (1.0 - blend_weight) * conservative

        # Dynamic floor: ranked apps get a higher floor (more reliable signal)
        floor = _FLOOR_WITH_RANK if has_rank else _FLOOR_NO_RANK
        daily_base = max(daily_base, floor)

        uncertainty = self._confidence._uncertainty_factor(conf_score, signals)

        # If confidence < 20%, return NULL for all numeric estimates
        # (rule: unreliable estimates should show "Unavailable" in the UI)
        if conf_score < 0.20:
            return {
                "estimated_downloads_daily": None,
                "estimated_downloads_monthly": None,
                "downloads_range_low": None,
                "downloads_range_high": None,
                "estimation_confidence": conf_score,
                "confidence_label": confidence_result["confidence_label"],
                "factor_breakdown": {
                    "rank_baseline": round(l1),
                    "review_velocity_estimate": round(l2),
                    "visibility_estimate": round(l3),
                    "momentum_adjustment_pct": round(l4 * 100, 1),
                    "weights_used": weights,
                    "confidence_factors": confidence_result["factors"],
                },
                "estimation_notes": "Insufficient data for a reliable estimate. Ranking history is too stale or missing.",
                "estimated_revenue_monthly": None,
                "revenue_range_low": None,
                "revenue_range_high": None,
                "monetization_model_hint": None,
            }

        daily_rounded = round(daily_base)
        monthly = daily_rounded * 30
        range_low = max(1, round(monthly * (1.0 - uncertainty)))
        range_high = round(monthly * (1.0 + uncertainty))

        return {
            "estimated_downloads_daily": daily_rounded,
            "estimated_downloads_monthly": monthly,
            "downloads_range_low": range_low,
            "downloads_range_high": range_high,
            "estimation_confidence": conf_score,
            "confidence_label": confidence_result["confidence_label"],
            "factor_breakdown": {
                "rank_baseline": round(l1),
                "review_velocity_estimate": round(l2),
                "visibility_estimate": round(l3),
                "momentum_adjustment_pct": round(l4 * 100, 1),
                "weights_used": weights,
                "confidence_factors": confidence_result["factors"],
            },
            "estimation_notes": self._build_notes(signals, confidence_result, blend_weight),
            # Revenue fields — populated externally by RevenueEstimator via routes.py
            "estimated_revenue_monthly": None,
            "revenue_range_low": None,
            "revenue_range_high": None,
            "monetization_model_hint": None,
        }

    # ------------------------------------------------------------------
    # Signal gathering
    # ------------------------------------------------------------------

    def _gather_signals(self, app: App) -> Dict:
        """Collect all signals in a single pass. Returns flat dict."""
        try:
            category = (app.primary_category or "").lower().strip()
            if not isinstance(category, str):
                category = ""
        except Exception:
            category = ""
        try:
            review_count = int(app.current_reviews or 0)
        except Exception:
            review_count = 0
        try:
            rank = app.current_rank
            # Ensure rank is an int or None
            if rank is not None:
                rank = int(rank)
        except Exception:
            rank = None

        # --- Review velocity (last 30 days) ---
        cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)
        try:
            recent_reviews = int(
                self.db.query(func.count(Review.id))
                .filter(Review.app_id == app.id, Review.date >= cutoff_30d)
                .scalar() or 0
            )
        except Exception:
            recent_reviews = 0
        velocity = recent_reviews / 30.0  # reviews/day

        # --- Ranking history depth ---
        cutoff_14d = datetime.now(timezone.utc) - timedelta(days=14)
        try:
            ranking_days = int(
                self.db.query(
                    func.count(func.distinct(func.date_trunc("day", Ranking.recorded_at)))
                )
                .filter(Ranking.app_id == app.id, Ranking.recorded_at >= cutoff_14d)
                .scalar() or 0
            )
        except Exception:
            ranking_days = 0

        # --- Keyword intelligence ---
        try:
            kw_row = (
                self.db.query(
                    func.count(AppKeywordIntelligence.id).label("kw_count"),
                    func.avg(AppKeywordIntelligence.traffic_score).label("avg_traffic"),
                )
                .filter(AppKeywordIntelligence.app_id == app.id)
                .first()
            )
            keyword_count = int(kw_row.kw_count or 0) if kw_row else 0
            avg_traffic_score = float(kw_row.avg_traffic or 0.0) if kw_row else 0.0
        except Exception:
            keyword_count = 0
            avg_traffic_score = 0.0

        # --- Trending score / momentum ---
        try:
            trending = (
                self.db.query(AppTrendingScore)
                .filter(AppTrendingScore.app_id == app.id)
                .first()
            )
            momentum_3d = float(getattr(trending, "momentum_3d", 0.0) or 0.0)
            momentum_7d = float(getattr(trending, "momentum_7d", 0.0) or 0.0)
            has_momentum = isinstance(trending, AppTrendingScore)
        except Exception:
            momentum_3d = 0.0
            momentum_7d = 0.0
            has_momentum = False

        # --- Data freshness ---
        data_age_days = 999
        try:
            last_scrape = getattr(app, "last_scraped_at", None) or getattr(app, "updated_at", None)
            if last_scrape and isinstance(last_scrape, datetime):
                if last_scrape.tzinfo is None:
                    last_scrape = last_scrape.replace(tzinfo=timezone.utc)
                data_age_days = max((datetime.now(timezone.utc) - last_scrape).days, 0)
        except Exception:
            pass

        return {
            "app_id": app.id,
            "category": category,
            "review_count": review_count,
            "rank": rank,
            "velocity": velocity,
            "ranking_history_days": int(ranking_days),
            "keyword_count": keyword_count,
            "avg_traffic_score": avg_traffic_score,
            "momentum_3d": momentum_3d,
            "momentum_7d": momentum_7d,
            "has_rank": rank is not None,
            "has_velocity": velocity > 0,
            "has_keywords": keyword_count > 0,
            "has_momentum": has_momentum,
            "data_age_days": data_age_days,
            "ir_ratio": _get_ir_ratio(category),
        }

    # ------------------------------------------------------------------
    # Layers
    # ------------------------------------------------------------------

    def _layer1_rank_curve(self, signals: dict) -> float:
        """Rank-curve based daily estimate (returns 0 if no rank)."""
        rank = signals.get("rank")
        if rank is None:
            return 0.0

        category = signals.get("category", "")
        lo, hi = interpolate_rank_downloads(rank, category)
        if lo == 0 and hi == 0:
            return 0.0

        # Midpoint of the range
        return (lo + hi) / 2.0

    def _layer2_review_velocity(self, signals: dict) -> float:
        """Review velocity → daily download estimate."""
        velocity = signals.get("velocity", 0.0)
        if velocity <= 0:
            return 0.0

        # Cap velocity to prevent spam manipulation
        velocity = min(velocity, _MAX_REVIEW_VELOCITY)

        category = signals.get("category", "")
        ir_ratio = signals.get("ir_ratio", _DEFAULT_IR_RATIO)
        calib = get_calibration(category)
        review_factor = calib.get("review_ratio_factor", 1.0)

        # Scale IR ratio by total review count: apps with very few reviews produce
        # noisy velocity signals — a single review/month should not extrapolate to
        # hundreds of daily downloads.
        review_count = signals.get("review_count", 0)
        review_scale = min(1.0, math.log(review_count + 1) / math.log(_IR_SCALING_REVIEWS + 1))

        # velocity (reviews/day) × IR ratio × calibration × review_scale = daily downloads
        return velocity * ir_ratio * review_factor * review_scale

    def _layer3_visibility(self, signals: dict) -> float:
        """Keyword visibility → organic discovery estimate."""
        keyword_count = signals.get("keyword_count", 0)
        avg_traffic = signals.get("avg_traffic_score", 0.0)

        if keyword_count == 0:
            return 0.0

        # Organic footprint = keyword_count × avg_traffic_score / 100
        footprint = keyword_count * avg_traffic / 100.0

        # Each unit of footprint ≈ 1.5 daily organic downloads.
        # No additive base — zero footprint should produce zero output.
        return footprint * _VISIBILITY_FOOTPRINT_SCALE

    def _layer4_momentum(self, signals: dict) -> float:
        """
        Returns a multiplicative adjustment based on trending momentum.
        Positive momentum → up to +20% boost
        Negative momentum → down to -30% penalty
        """
        if not signals.get("has_momentum", False):
            return 0.0

        momentum_3d = signals.get("momentum_3d", 0.0)
        momentum_7d = signals.get("momentum_7d", 0.0)

        # Weight recent momentum more heavily
        combined = 0.6 * momentum_3d + 0.4 * momentum_7d

        # tanh scaling: maps combined momentum to (-1, +1), then scale to (-0.30, +0.20)
        # Combined momentum is typically in range [-1.0, 1.0] already from ScoringEngine
        scaled = math.tanh(combined)

        if scaled >= 0:
            return scaled * 0.20   # max +20%
        else:
            return scaled * 0.30   # max -30%

    # ------------------------------------------------------------------
    # Weights
    # ------------------------------------------------------------------

    def _compute_weights(self, signals: dict) -> dict:
        """
        Dynamic weight computation based on signal availability.
        Default: rank=0.45, review=0.25, visibility=0.20
        Always normalized to sum=1.0.
        """
        has_rank = signals.get("has_rank", False)
        has_velocity = signals.get("has_velocity", False)
        has_keywords = signals.get("has_keywords", False)

        w_rank = 0.45 if has_rank else 0.0
        w_review = 0.25 if has_velocity else 0.0
        w_visibility = 0.20 if has_keywords else 0.0

        total = w_rank + w_review + w_visibility

        # If all signals are absent, fall back to uniform distribution
        # (all layers return 0 anyway, so the floor of 10 will apply)
        if total == 0:
            return {"rank": 0.45, "review": 0.25, "visibility": 0.20}

        # Redistribute missing signal weight proportionally to present signals
        return {
            "rank": round(w_rank / total, 4),
            "review": round(w_review / total, 4),
            "visibility": round(w_visibility / total, 4),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _conservative_daily_baseline(self, signals: dict) -> float:
        """
        Conservative daily download baseline used for shrinkage.

        For ranked apps: fraction of the rank-curve lower band (so the baseline
        is anchored to real App Store data for that position).
        For unranked apps: log-scaled from total review count (more reviews = more
        evidence of actual usage, but grows slowly to stay conservative).
        """
        has_rank = signals.get("has_rank", False)
        review_count = signals.get("review_count", 0)

        if has_rank:
            rank = signals.get("rank")
            category = signals.get("category", "")
            lo, _ = interpolate_rank_downloads(rank, category)
            return max(lo * _RANK_BASELINE_FRACTION, _FLOOR_WITH_RANK)
        else:
            return min(0.5 + math.log(review_count + 1) * 0.8, 5.0)

    def _build_notes(self, signals: dict, confidence: dict, blend_weight: float = 1.0) -> str:
        """Human-readable explanation of key estimation drivers."""
        parts = []

        rank = signals.get("rank")
        if rank:
            parts.append(f"Rank #{rank} in charts")
        else:
            parts.append("No chart rank (using review/keyword signals only)")

        velocity = signals.get("velocity", 0.0)
        if velocity > 0:
            parts.append(f"Review velocity {velocity:.1f}/day")

        kw_count = signals.get("keyword_count", 0)
        if kw_count:
            parts.append(f"{kw_count} tracked keywords")

        label = confidence.get("confidence_label", "low")
        conf_score = confidence.get("confidence_score", 0.0)
        parts.append(f"Confidence: {label} ({conf_score:.0%})")

        if blend_weight < 0.50:
            parts.append(
                f"Shrinkage applied ({blend_weight:.0%} blend) — "
                "low-signal estimate pulled toward conservative baseline"
            )

        if signals.get("has_momentum"):
            adj = signals.get("momentum_3d", 0.0)
            direction = "rising" if adj > 0.05 else "falling" if adj < -0.05 else "stable"
            parts.append(f"Momentum: {direction}")

        return ". ".join(parts) + "."

    @staticmethod
    def _empty(app_id: int) -> Dict:
        return {
            "estimated_downloads_daily": 0,
            "estimated_downloads_monthly": 0,
            "downloads_range_low": 0,
            "downloads_range_high": 0,
            "estimation_confidence": 0.0,
            "confidence_label": "low",
            "factor_breakdown": {
                "rank_baseline": 0,
                "review_velocity_estimate": 0,
                "visibility_estimate": 0,
                "momentum_adjustment_pct": 0.0,
                "weights_used": {"rank": 0.45, "review": 0.25, "visibility": 0.20},
                "confidence_factors": {},
            },
            "estimation_notes": "No app data found.",
            "estimated_revenue_monthly": None,
            "revenue_range_low": None,
            "revenue_range_high": None,
            "monetization_model_hint": None,
        }
