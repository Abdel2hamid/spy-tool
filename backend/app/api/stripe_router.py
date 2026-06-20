"""
Stripe billing endpoints:
  POST /stripe/create-checkout   → create Checkout session, return URL
  POST /stripe/webhook           → handle Stripe webhook events
  POST /stripe/billing-portal    → redirect to Stripe billing portal
  GET  /stripe/config            → return publishable key for frontend
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, get_auth_context
from app.config import settings
from app.database import get_db
from app.models.models import Subscription
from app.services import stripe_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stripe", tags=["stripe"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    plan_code: str  # starter | pro


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class StripeConfigResponse(BaseModel):
    publishable_key: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/config", response_model=StripeConfigResponse)
def get_stripe_config():
    """Return Stripe publishable key for the frontend."""
    return StripeConfigResponse(publishable_key=settings.stripe_publishable_key)



@router.post("/create-checkout", response_model=CheckoutResponse)
def create_checkout(
    body: CheckoutRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout session for the authenticated user."""
    if not stripe_service.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Billing not configured.")

    sub = db.query(Subscription).filter(
        Subscription.workspace_id == ctx.workspace.id,
    ).first()

    if not sub:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No subscription record found.")

    # Create Stripe customer if needed
    if not sub.stripe_customer_id:
        customer = stripe_service.create_customer(
            email=ctx.user.email,
            name=ctx.user.full_name,
        )
        sub.stripe_customer_id = customer.id
        db.commit()

    success_url = f"{settings.frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.frontend_url}/signup"

    try:
        session = stripe_service.create_checkout_session(
            customer_id=sub.stripe_customer_id,
            plan_code=body.plan_code,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:
        logger.error("Stripe checkout creation failed: %s", e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Failed to create checkout session.")

    return CheckoutResponse(checkout_url=session.url)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle incoming Stripe webhook events."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe_service.construct_event(payload, sig)
    except Exception as e:
        logger.error("Stripe webhook signature failed: %s", e)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature.")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    try:
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
    except Exception as e:
        logger.error("Webhook handler failed for %s: %s", event_type, e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Webhook processing failed.")

    return {"status": "ok"}


@router.post("/billing-portal", response_model=PortalResponse)
def billing_portal(
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Create a Stripe Customer Portal session for subscription management."""
    if not stripe_service.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Billing not configured.")

    sub = db.query(Subscription).filter(
        Subscription.workspace_id == ctx.workspace.id,
    ).first()

    if not sub or not sub.stripe_customer_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No billing account found.")

    try:
        session = stripe_service.create_billing_portal_session(
            customer_id=sub.stripe_customer_id,
            return_url=f"{settings.frontend_url}/settings",
        )
    except Exception as e:
        logger.error("Stripe billing portal creation failed: %s", e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Failed to open billing portal. Please try again.")

    return PortalResponse(portal_url=session.url)
