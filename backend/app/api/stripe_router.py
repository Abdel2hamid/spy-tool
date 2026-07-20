"""
Stripe billing endpoints:
  POST /stripe/create-checkout   → create Checkout session, return URL
  POST /stripe/webhook           → handle Stripe webhook events
  POST /stripe/billing-portal    → redirect to Stripe billing portal
  GET  /stripe/config            → return publishable key for frontend
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, get_auth_context
from app.config import settings
from app.database import get_db
from app.services.billing import get_billing_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stripe", tags=["billing"])


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
    """Return the client-safe publishable key for the frontend."""
    return StripeConfigResponse(publishable_key=get_billing_provider().publishable_key())


@router.post("/create-checkout", response_model=CheckoutResponse)
def create_checkout(
    body: CheckoutRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Create a checkout session for the authenticated user (active gateway)."""
    provider = get_billing_provider()
    if not provider.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Billing not configured.")

    success_url = f"{settings.frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.frontend_url}/signup"

    try:
        checkout_url = provider.create_checkout(
            db=db,
            workspace_id=ctx.workspace.id,
            plan_code=body.plan_code,
            customer_email=ctx.user.email,
            customer_name=ctx.user.full_name,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:
        logger.error("Checkout creation failed: %s", e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Failed to create checkout session.")

    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle incoming billing webhook events for the active gateway."""
    provider = get_billing_provider()
    payload = await request.body()

    try:
        event = provider.verify_webhook(payload=payload, headers=request.headers)
    except Exception as e:
        logger.error("Webhook signature verification failed: %s", e)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature.")

    try:
        # Handlers do sync gateway/DB I/O — keep them off the event loop.
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(provider.handle_webhook_event, event, db)
    except Exception as e:
        logger.error("Webhook handler failed: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Webhook processing failed.")

    return {"status": "ok"}


@router.post("/billing-portal", response_model=PortalResponse)
def billing_portal(
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Create a customer billing-management portal session (active gateway)."""
    provider = get_billing_provider()
    if not provider.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Billing not configured.")

    try:
        portal_url = provider.create_billing_portal(
            db=db,
            workspace_id=ctx.workspace.id,
            return_url=f"{settings.frontend_url}/settings",
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:
        logger.error("Billing portal creation failed: %s", e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Failed to open billing portal. Please try again.")

    return PortalResponse(portal_url=portal_url)
