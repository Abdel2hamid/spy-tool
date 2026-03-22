"""
Revenue Estimation Engine
==========================
Estimates monthly revenue for each app based on install estimates and
monetisation model (free + IAP, paid, subscription).

Model:
  Free + IAP/Subscription:
    monthly_revenue = monthly_installs × conversion_rate × ARPU
  Paid app:
    monthly_revenue = monthly_installs × price
  Mix (free with paid upgrades):
    weighted blend

ARPU and conversion rates are now sourced from category_arpu_profiles.py
for per-category richness. The old flat _CATEGORY_ARPU dict is kept for
backward compatibility with any direct callers, but the _compute_from_installs
path uses the profile system.
"""

import logging
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.models import App
from app.config.category_arpu_profiles import get_arpu_profile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backward-compat constants (kept for external callers that import these directly)
# ---------------------------------------------------------------------------

_CATEGORY_ARPU: Dict[str, float] = {
    "productivity": 2.50,
    "business": 3.00,
    "finance": 4.00,
    "health & fitness": 3.50,
    "health": 3.50,
    "fitness": 3.50,
    "photo & video": 3.20,
    "photo": 3.20,
    "music": 2.80,
    "education": 2.20,
    "utilities": 1.80,
    "lifestyle": 2.10,
    "travel": 2.50,
    "food & drink": 1.60,
    "food": 1.60,
    "navigation": 1.80,
    "news": 1.50,
    "sports": 1.80,
    "social networking": 1.20,
    "social": 1.20,
    "entertainment": 1.20,
    "games": 1.50,
    "shopping": 0.80,
    "books": 1.50,
    "reference": 1.20,
    "medical": 2.00,
    "weather": 0.80,
    "graphics & design": 3.00,
    "developer tools": 3.50,
}
_DEFAULT_ARPU = 2.00
_ACTIVE_FRACTION = 0.15
_IAP_CONVERSION = 0.03
_APPLE_CUT = 0.30
_MIN_MONTHLY_INSTALLS_FOR_AD_REVENUE = 100  # below this, ad revenue rounds to $0


def _get_arpu(category: Optional[str]) -> float:
    profile = get_arpu_profile(category)
    return profile["arpu_medium"]


class RevenueEstimator:
    def __init__(self, db: Session):
        self.db = db

    def estimate(self, app_id: int) -> Dict:
        """Return revenue estimate for a single app by DB integer ID."""
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return self._empty()
        return self._compute(app)

    def compute_and_save(self, app: App, installs_min: int, installs_max: int) -> Tuple[float, float]:
        """Compute and write revenue back to app record. Returns (min, max)."""
        result = self._compute_from_installs(app, installs_min, installs_max)
        app.estimated_revenue_monthly_min = result["estimated_revenue_monthly_min"]
        app.estimated_revenue_monthly_max = result["estimated_revenue_monthly_max"]
        return result["estimated_revenue_monthly_min"], result["estimated_revenue_monthly_max"]

    def compute_all(self) -> int:
        """Compute and save revenue estimates for all tracked apps. Returns count updated."""
        apps = self.db.query(App).filter(
            App.estimated_installs_min > 0
        ).all()
        count = 0
        for app in apps:
            try:
                self.compute_and_save(
                    app,
                    int(app.estimated_installs_min or 0),
                    int(app.estimated_installs_max or 0),
                )
                count += 1
            except Exception as exc:
                logger.warning(f"Revenue estimate failed for app {app.app_id}: {exc}")
        self.db.commit()
        logger.info(f"[revenue_estimator] Updated estimates for {count} apps")
        return count

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    def _compute(self, app: App) -> Dict:
        installs_min = int(app.estimated_installs_min or 0)
        installs_max = int(app.estimated_installs_max or 0)
        if installs_min == 0 and installs_max == 0:
            # Derive rough install estimate on-the-fly
            from app.services.install_estimator import InstallEstimator
            est = InstallEstimator(self.db)
            r = est._compute(app)
            installs_min = r["estimated_installs_min"]
            installs_max = r["estimated_installs_max"]
        return self._compute_from_installs(app, installs_min, installs_max)

    def _compute_from_installs(self, app: App, installs_min: int, installs_max: int) -> Dict:
        category = app.primary_category or ""

        # Use rich ARPU profile for per-category conversion rates
        profile = get_arpu_profile(category)
        arpu = profile["arpu_medium"]
        active_fraction = profile["active_fraction"]
        iap_conversion = profile["iap_conversion_rate"]
        monetization_hint = profile["monetization_hint"]

        price = app.price or 0.0
        is_free = app.is_free if app.is_free is not None else (price == 0)
        has_iap = bool(app.in_app_purchases)

        if not is_free and price > 0:
            # Paid app: revenue = installs × price × (1 - apple_cut)
            net_price = price * (1 - _APPLE_CUT)
            rev_min = installs_min * net_price
            rev_max = installs_max * net_price
            model = f"paid_${price:.2f}"
            monetization_hint = "paid"
        elif has_iap:
            # Free + IAP/subscription: revenue from active paying users
            # Active base = installs × active_fraction (per-category)
            # Paying users = active_base × iap_conversion (per-category)
            # Revenue = paying_users × arpu
            paying_min = installs_min * active_fraction * iap_conversion
            paying_max = installs_max * active_fraction * iap_conversion
            rev_min = paying_min * arpu
            rev_max = paying_max * arpu * 1.5  # wider range for subscription variance
            model = f"free+iap_arpu_${arpu:.2f}"
        else:
            # Truly free, no visible IAP — ad revenue estimate
            ad_rev_per_1k_mau = 0.50  # $0.50 CPM
            mau_min = installs_min * active_fraction
            mau_max = installs_max * active_fraction
            # Guard: too few installs → ad revenue rounds to $0 (not meaningful)
            rev_min = (
                (mau_min / 1000) * ad_rev_per_1k_mau * 30
                if installs_min >= _MIN_MONTHLY_INSTALLS_FOR_AD_REVENUE
                else 0.0
            )
            rev_max = (
                (mau_max / 1000) * ad_rev_per_1k_mau * 30
                if installs_max >= _MIN_MONTHLY_INSTALLS_FOR_AD_REVENUE
                else 0.0
            )
            model = "free_ads_only"

        rev_min = max(rev_min, 0)
        rev_max = max(rev_max, 0)

        return {
            "estimated_revenue_monthly_min": round(rev_min, 2),
            "estimated_revenue_monthly_max": round(rev_max, 2),
            "revenue_range_low": round(rev_min, 2),
            "revenue_range_high": round(rev_max, 2),
            "model": model,
            "arpu": arpu,
            "category": category,
            "monetization_model_hint": monetization_hint,
        }

    @staticmethod
    def _empty() -> Dict:
        return {
            "estimated_revenue_monthly_min": 0.0,
            "estimated_revenue_monthly_max": 0.0,
            "revenue_range_low": 0.0,
            "revenue_range_high": 0.0,
            "model": "no data",
            "arpu": 0.0,
            "category": "",
            "monetization_model_hint": "unknown",
        }
