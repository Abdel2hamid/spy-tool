"""
Stripe integration service for RankSpy billing.

Handles customer creation, checkout sessions, webhook processing,
and billing portal sessions.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import stripe
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import Subscription

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

stripe.api_key = settings.stripe_secret_key

PLAN_TO_PRICE: dict[str, str] = {
    "starter": settings.stripe_price_starter,
    "pro": settings.stripe_price_pro,
    "enterprise": settings.stripe_price_enterprise,
}


def is_configured() -> bool:
    """Return True if Stripe keys are set."""
    return bool(settings.stripe_secret_key and settings.stripe_publishable_key)


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

def create_customer(email: str, name: Optional[str] = None) -> stripe.Customer:
    return stripe.Customer.create(
        email=email,
        name=name or email,
        metadata={"source": "rankspy"},
    )


# ---------------------------------------------------------------------------
# Checkout sessions
# ---------------------------------------------------------------------------

def create_checkout_session(
    customer_id: str,
    plan_code: str,
    success_url: str,
    cancel_url: str,
) -> stripe.checkout.Session:
    """
    Create a Stripe Checkout session for a paid plan with 7-day trial.
    """
    price_id = PLAN_TO_PRICE.get(plan_code)
    if not price_id:
        raise ValueError(f"No Stripe price configured for plan: {plan_code}")

    return stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        payment_method_types=["card", "paypal"],
        line_items=[{"price": price_id, "quantity": 1}],
        subscription_data={"trial_period_days": 7},
        success_url=success_url,
        cancel_url=cancel_url,
    )


# ---------------------------------------------------------------------------
# Billing portal
# ---------------------------------------------------------------------------

def create_billing_portal_session(
    customer_id: str,
    return_url: str,
) -> stripe.billing_portal.Session:
    return stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )


# ---------------------------------------------------------------------------
# Webhook processing
# ---------------------------------------------------------------------------

def construct_event(payload: bytes, sig: str) -> stripe.Event:
    if not settings.stripe_webhook_secret:
        raise ValueError("Stripe webhook secret is not configured")
    return stripe.Webhook.construct_event(
        payload, sig, settings.stripe_webhook_secret,
    )


def handle_checkout_completed(session_data: dict, db: Session) -> None:
    """Process checkout.session.completed event."""
    customer_id = session_data.get("customer")
    if not customer_id:
        return

    sub = db.query(Subscription).filter(
        Subscription.stripe_customer_id == customer_id,
    ).first()
    if not sub:
        logger.warning("No subscription found for Stripe customer %s", customer_id)
        return

    mode = session_data.get("mode")
    if mode == "setup":
        # Free plan — card saved, activate
        sub.status = "active"
        sub.plan_code = "free"
    elif mode == "subscription":
        # Paid plan — Stripe created subscription with trial
        stripe_sub_id = session_data.get("subscription")
        if stripe_sub_id:
            sub.stripe_subscription_id = stripe_sub_id
        sub.status = "trialing"
    db.commit()
    logger.info("Checkout completed for customer %s → plan=%s", customer_id, sub.plan_code)


def handle_subscription_updated(stripe_sub: dict, db: Session) -> None:
    """Process customer.subscription.updated event."""
    customer_id = stripe_sub.get("customer")
    sub = db.query(Subscription).filter(
        Subscription.stripe_customer_id == customer_id,
    ).first()
    if not sub:
        return

    sub.stripe_subscription_id = stripe_sub.get("id")
    status_map = {
        "trialing": "trialing",
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
    }
    new_status = status_map.get(stripe_sub.get("status", ""), None)
    if new_status:
        sub.status = new_status

    period_end = stripe_sub.get("current_period_end")
    if period_end:
        sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

    db.commit()
    logger.info("Subscription updated for customer %s → status=%s", customer_id, sub.status)


def handle_subscription_deleted(stripe_sub: dict, db: Session) -> None:
    """Process customer.subscription.deleted event."""
    customer_id = stripe_sub.get("customer")
    sub = db.query(Subscription).filter(
        Subscription.stripe_customer_id == customer_id,
    ).first()
    if not sub:
        return

    sub.status = "canceled"
    sub.plan_code = "free"
    sub.stripe_subscription_id = None
    db.commit()
    logger.info("Subscription cancelled for customer %s", customer_id)
