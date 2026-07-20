"""Stripe implementation of the BillingProvider interface.

This encapsulates the orchestration that used to live in `stripe_router` and
delegates the actual Stripe SDK calls to `app.services.stripe_service`. It reads
and writes the provider-agnostic `provider_*` columns, keeping the legacy
`stripe_*` columns in sync so existing webhook lookups keep working.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import Subscription
from app.services import stripe_service
from app.services.billing.base import BillingProvider

logger = logging.getLogger(__name__)


class StripeBillingProvider(BillingProvider):
    name = "stripe"

    def is_configured(self) -> bool:
        return stripe_service.is_configured()

    def publishable_key(self) -> str:
        return settings.stripe_publishable_key

    # ------------------------------------------------------------------
    def _get_sub(self, db: Session, workspace_id: int) -> Optional[Subscription]:
        return (
            db.query(Subscription)
            .filter(Subscription.workspace_id == workspace_id)
            .first()
        )

    def create_checkout(
        self,
        *,
        db: Session,
        workspace_id: int,
        plan_code: str,
        customer_email: str,
        customer_name: Optional[str],
        success_url: str,
        cancel_url: str,
    ) -> str:
        sub = self._get_sub(db, workspace_id)
        if not sub:
            raise ValueError("No subscription record found.")

        customer_id = sub.provider_customer_id or sub.stripe_customer_id
        if not customer_id:
            customer = stripe_service.create_customer(
                email=customer_email, name=customer_name
            )
            customer_id = customer.id
            sub.provider = self.name
            sub.provider_customer_id = customer_id
            sub.stripe_customer_id = customer_id  # keep legacy column in sync
            db.commit()

        session = stripe_service.create_checkout_session(
            customer_id=customer_id,
            plan_code=plan_code,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return session.url

    def create_billing_portal(
        self, *, db: Session, workspace_id: int, return_url: str
    ) -> str:
        sub = self._get_sub(db, workspace_id)
        customer_id = (sub.provider_customer_id or sub.stripe_customer_id) if sub else None
        if not customer_id:
            raise ValueError("No billing account found.")
        session = stripe_service.create_billing_portal_session(
            customer_id=customer_id, return_url=return_url
        )
        return session.url

    def cancel_subscription(self, provider_subscription_id: str) -> None:
        if not provider_subscription_id:
            return
        import stripe  # noqa: PLC0415 — api_key configured by stripe_service

        stripe.Subscription.delete(provider_subscription_id)

    def verify_webhook(self, *, payload: bytes, headers: Mapping[str, str]) -> Any:
        sig = headers.get("stripe-signature", "")
        return stripe_service.construct_event(payload, sig)

    def handle_webhook_event(self, event: Any, db: Session) -> None:
        event_type = event.get("type", "")
        data = event.get("data", {}).get("object", {})
        if event_type == "checkout.session.completed":
            stripe_service.handle_checkout_completed(data, db)
        elif event_type == "customer.subscription.updated":
            stripe_service.handle_subscription_updated(data, db)
        elif event_type == "customer.subscription.deleted":
            stripe_service.handle_subscription_deleted(data, db)
        elif event_type == "invoice.payment_succeeded":
            stripe_service.handle_invoice_payment_succeeded(data, db)
        elif event_type == "invoice.payment_failed":
            stripe_service.handle_invoice_payment_failed(data, db)
        elif event_type == "customer.subscription.trial_will_end":
            stripe_service.handle_trial_will_end(data, db)
        else:
            logger.debug("Unhandled Stripe event: %s", event_type)
