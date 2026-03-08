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

ARPU (Average Revenue Per User / month) varies by category and monetisation type.
Values are calibrated against publicly reported developer revenue data.
"""

import logging
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.models import App

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Calibration constants
# ---------------------------------------------------------------------------

# Monthly ARPU (revenue per active user) by category for subscription/IAP apps.
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

# Fraction of monthly installs that are "active" (using the app regularly)
# and thus generate recurring revenue from subscriptions/IAP.
_ACTIVE_FRACTION = 0.15  # 15% of install base is active and paying in a given month

# For free apps with IAP: fraction of actives that make a purchase
_IAP_CONVERSION = 0.03  # 3%

# For paid one-time purchase apps: effective price after Apple's 30% cut
_APPLE_CUT = 0.30


def _get_arpu(category: Optional[str]) -> float:
    if not category:
        return _DEFAULT_ARPU
    cat_lower = category.lower().strip()
    for key, arpu in _CATEGORY_ARPU.items():
        if key in cat_lower or cat_lower in key:
            return arpu
    return _DEFAULT_ARPU


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
        arpu = _get_arpu(category)
        price = app.price or 0.0
        is_free = app.is_free if app.is_free is not None else (price == 0)
        has_iap = bool(app.in_app_purchases)

        if not is_free and price > 0:
            # Paid app: revenue = installs × price × (1 - apple_cut)
            net_price = price * (1 - _APPLE_CUT)
            rev_min = installs_min * net_price
            rev_max = installs_max * net_price
            model = f"paid_${price:.2f}"
        elif has_iap:
            # Free + IAP/subscription: revenue from active paying users
            # Active base = installs × active_fraction
            # Paying users = active_base × iap_conversion
            # Revenue = paying_users × arpu
            paying_min = installs_min * _ACTIVE_FRACTION * _IAP_CONVERSION
            paying_max = installs_max * _ACTIVE_FRACTION * _IAP_CONVERSION
            # Also estimate subscription revenue separately at 3× IAP ARPU
            rev_min = paying_min * arpu
            rev_max = paying_max * arpu * 1.5  # wider range for subscription variance
            model = f"free+iap_arpu_${arpu:.2f}"
        else:
            # Truly free, no visible IAP - assume some % still generates revenue via ads
            ad_rev_per_1k_mau = 0.50  # $0.50 CPM
            mau_min = installs_min * _ACTIVE_FRACTION
            mau_max = installs_max * _ACTIVE_FRACTION
            rev_min = (mau_min / 1000) * ad_rev_per_1k_mau * 30  # per day → monthly
            rev_max = (mau_max / 1000) * ad_rev_per_1k_mau * 30
            model = "free_ads_only"

        # Apply category premium/discount
        cat_lower = category.lower()
        if any(k in cat_lower for k in ["productivity", "business", "finance"]):
            rev_min *= 1.15
            rev_max *= 1.15
        elif any(k in cat_lower for k in ["games", "entertainment"]):
            rev_min *= 0.9
            rev_max *= 0.9

        rev_min = max(rev_min, 0)
        rev_max = max(rev_max, 0)

        return {
            "estimated_revenue_monthly_min": round(rev_min, 2),
            "estimated_revenue_monthly_max": round(rev_max, 2),
            "model": model,
            "arpu": arpu,
            "category": category,
        }

    @staticmethod
    def _empty() -> Dict:
        return {
            "estimated_revenue_monthly_min": 0.0,
            "estimated_revenue_monthly_max": 0.0,
            "model": "no data",
            "arpu": 0.0,
            "category": "",
        }
