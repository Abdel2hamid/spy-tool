"""
Install Estimation Engine
=========================
Estimates monthly app downloads using a calibrated proxy model.

Methodology:
  1. Base installs = current_reviews × category_install_review_ratio
     (each category has a known ratio of installs-per-review, derived from
      public developer case studies and Apple's "most downloaded" lists)
  2. Chart rank boost multiplies the base for apps in top charts
  3. Review velocity (new reviews / 30 days) provides the monthly signal
  4. Confidence degrades when key inputs are missing

Outputs:
  estimated_installs_min  — conservative estimate
  estimated_installs_max  — optimistic estimate
  install_confidence      — 0.0–1.0 (how reliable the estimate is)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.models import App, Ranking, Review

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Calibration constants
# ---------------------------------------------------------------------------

# How many installs correspond to 1 review on average, by category.
# Source: developer case studies, Apple public data, academic estimates.
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

# Chart rank → install multiplier  (rank 1 gets ~50% more installs than rank 100)
_RANK_BOOST: Dict[str, float] = {
    "top_1": 1.50,
    "top_5": 1.35,
    "top_10": 1.25,
    "top_25": 1.12,
    "top_50": 1.06,
    "top_100": 1.00,
    "top_200": 0.85,
    "not_ranked": 0.70,
}

# Confidence factors
_CONFIDENCE_FULL = 0.85     # when all signals present
_CONFIDENCE_NO_RANK = 0.60
_CONFIDENCE_NO_VELOCITY = 0.55
_CONFIDENCE_MINIMAL = 0.35  # only review count available


def _get_ir_ratio(category: Optional[str]) -> float:
    if not category:
        return _DEFAULT_IR_RATIO
    cat_lower = category.lower().strip()
    for key, ratio in _CATEGORY_IR_RATIO.items():
        if key in cat_lower or cat_lower in key:
            return ratio
    return _DEFAULT_IR_RATIO


def _rank_bucket(rank: Optional[int]) -> str:
    if rank is None:
        return "not_ranked"
    if rank == 1:
        return "top_1"
    if rank <= 5:
        return "top_5"
    if rank <= 10:
        return "top_10"
    if rank <= 25:
        return "top_25"
    if rank <= 50:
        return "top_50"
    if rank <= 100:
        return "top_100"
    if rank <= 200:
        return "top_200"
    return "not_ranked"


class InstallEstimator:
    def __init__(self, db: Session):
        self.db = db

    def estimate(self, app_id: int) -> Dict:
        """
        Return install estimate for a single app by its DB integer ID.

        Returns:
            {
                "estimated_installs_min": int,
                "estimated_installs_max": int,
                "install_confidence": float,
                "methodology": str
            }
        """
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return self._empty()

        return self._compute(app)

    def estimate_by_app_id(self, app_id_str: str) -> Dict:
        app = self.db.query(App).filter(App.app_id == app_id_str).first()
        if not app:
            return self._empty()
        return self._compute(app)

    def compute_and_save(self, app: App) -> Tuple[int, int, float]:
        """Compute estimate and write back to app record. Returns (min, max, confidence)."""
        result = self._compute(app)
        app.estimated_installs_min = result["estimated_installs_min"]
        app.estimated_installs_max = result["estimated_installs_max"]
        app.install_confidence = result["install_confidence"]
        return (
            result["estimated_installs_min"],
            result["estimated_installs_max"],
            result["install_confidence"],
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
                    logger.warning(f"Install estimate failed for app {app.app_id}: {exc}")
            self.db.commit()
            self.db.expire_all()
        logger.info(f"[install_estimator] Updated estimates for {count} apps")
        return count

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    def _compute(self, app: App) -> Dict:
        review_count = app.current_reviews or 0
        category = app.primary_category or ""
        rank = app.current_rank
        ir_ratio = _get_ir_ratio(category)

        # Step 1: Base lifetime installs from review count
        base_installs = review_count * ir_ratio

        # Step 2: Rank boost
        rank_bucket = _rank_bucket(rank)
        rank_boost = _RANK_BOOST[rank_bucket]

        # Step 3: Adjusted lifetime installs
        lifetime_installs = base_installs * rank_boost

        # Step 4: Monthly estimate = lifetime / app_age_months (capped at 60)
        app_age_months = self._app_age_months(app)
        monthly_base = lifetime_installs / max(app_age_months, 1)

        # Step 5: Velocity adjustment (recent review rate signals current momentum)
        velocity = self._review_velocity(app.id)
        velocity_monthly = velocity * ir_ratio * 30  # new_reviews_per_day × ratio × 30

        # Blend: 60% velocity-based (if available), 40% historical average
        has_velocity = velocity > 0
        if has_velocity:
            monthly_estimate = 0.4 * monthly_base + 0.6 * velocity_monthly
        else:
            monthly_estimate = monthly_base

        monthly_estimate = max(monthly_estimate, 100)  # floor at 100

        # Step 6: Min/Max range (±40% around estimate)
        estimate_min = int(monthly_estimate * 0.6)
        estimate_max = int(monthly_estimate * 1.6)

        # Round to clean numbers
        estimate_min = self._round_to_significant(estimate_min)
        estimate_max = self._round_to_significant(estimate_max)

        # Step 7: Confidence
        if has_velocity and rank is not None and review_count > 50:
            confidence = _CONFIDENCE_FULL
        elif has_velocity and review_count > 10:
            confidence = _CONFIDENCE_NO_RANK if rank is None else _CONFIDENCE_FULL * 0.9
        elif review_count > 0:
            confidence = _CONFIDENCE_NO_VELOCITY
        else:
            confidence = _CONFIDENCE_MINIMAL

        methodology = (
            f"review_count={review_count}, ir_ratio={ir_ratio:.0f}, "
            f"rank={rank}, boost={rank_boost:.2f}, "
            f"velocity={velocity:.3f}/day, age={app_age_months:.0f}mo"
        )

        return {
            "estimated_installs_min": estimate_min,
            "estimated_installs_max": estimate_max,
            "install_confidence": round(confidence, 2),
            "methodology": methodology,
        }

    def _review_velocity(self, app_db_id: int) -> float:
        """Average new reviews per day over the last 30 days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        count = (
            self.db.query(Review)
            .filter(Review.app_id == app_db_id, Review.date >= cutoff)
            .count()
        )
        return count / 30.0

    def _app_age_months(self, app: App) -> float:
        if not app.release_date:
            return 24.0  # assume 2 years if unknown
        now = datetime.now(timezone.utc)
        release = app.release_date
        if release.tzinfo is None:
            release = release.replace(tzinfo=timezone.utc)
        delta_days = (now - release).days
        return max(delta_days / 30.0, 1.0)

    @staticmethod
    def _round_to_significant(n: int) -> int:
        """Round to 2 significant figures for cleaner display."""
        if n <= 0:
            return 0
        if n < 1000:
            return round(n, -1)   # nearest 10
        if n < 10_000:
            return round(n, -2)   # nearest 100
        if n < 100_000:
            return round(n, -3)   # nearest 1K
        if n < 1_000_000:
            return round(n, -4)   # nearest 10K
        return round(n, -5)       # nearest 100K

    @staticmethod
    def _empty() -> Dict:
        return {
            "estimated_installs_min": 0,
            "estimated_installs_max": 0,
            "install_confidence": 0.0,
            "methodology": "no data",
        }
