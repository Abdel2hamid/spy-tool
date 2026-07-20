"""Billing provider registry.

`get_billing_provider()` returns the active `BillingProvider` based on
`settings.payment_provider`. To add a gateway (e.g. Airwallex): implement the
`BillingProvider` interface, register the class here, and set
`PAYMENT_PROVIDER=airwallex` — nothing else in the app changes.
"""
from __future__ import annotations

from app.config import settings
from app.services.billing.base import BillingProvider
from app.services.billing.stripe_provider import StripeBillingProvider

# name -> provider class
_PROVIDERS = {
    StripeBillingProvider.name: StripeBillingProvider,
    # "airwallex": AirwallexBillingProvider,   # ← added in Phase 2b
}


def get_billing_provider() -> BillingProvider:
    name = (getattr(settings, "payment_provider", "stripe") or "stripe").lower()
    provider_cls = _PROVIDERS.get(name, StripeBillingProvider)
    return provider_cls()


__all__ = ["BillingProvider", "get_billing_provider"]
