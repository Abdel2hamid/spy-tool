"""
Central plan definitions for RankSpy.

Plans:
  free       - unauthenticated / downgraded users
  trial      - 7-day trial (generous limits)
  starter    - entry paid tier
  pro        - full power
  enterprise - unlimited

Add new plans here; enforcement reads from PLAN_LIMITS[plan_code].
All per-month limits; None means unlimited.
"""
from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Plan limits — None means unlimited
# ---------------------------------------------------------------------------

PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "app_imports": 5,
        "keyword_refreshes": 10,
        "ai_requests": 5,
        "exports": 0,
        "access_premium": False,
    },
    "trial": {
        "app_imports": 50,
        "keyword_refreshes": 100,
        "ai_requests": 50,
        "exports": 20,
        "access_premium": True,
    },
    "starter": {
        "app_imports": 100,
        "keyword_refreshes": 200,
        "ai_requests": 100,
        "exports": 50,
        "access_premium": True,
    },
    "pro": {
        "app_imports": None,
        "keyword_refreshes": None,
        "ai_requests": None,
        "exports": None,
        "access_premium": True,
    },
    "enterprise": {
        "app_imports": None,
        "keyword_refreshes": None,
        "ai_requests": None,
        "exports": None,
        "access_premium": True,
    },
}

_UPGRADE_MESSAGES: dict[str, str] = {
    "free": "Start your free trial or upgrade to Pro for higher limits.",
    "trial": "Upgrade to Pro for unlimited access after your trial.",
    "starter": "Upgrade to Pro for unlimited access.",
    "pro": "You're on the Pro plan with unlimited access.",
    "enterprise": "You're on the Enterprise plan with unlimited access.",
}

_ACTION_LABELS: dict[str, str] = {
    "app_imports": "app imports",
    "keyword_refreshes": "keyword refreshes",
    "ai_requests": "AI requests",
    "exports": "exports",
}

# Human-readable display names for the plan
PLAN_DISPLAY_NAMES: dict[str, str] = {
    "free": "Free",
    "trial": "Trial",
    "starter": "Starter",
    "pro": "Pro",
    "enterprise": "Enterprise",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_effective_plan(subscription) -> str:
    """
    Resolve the plan code whose limits apply to this workspace.
    - trialing + not expired → 'trial'
    - trialing + expired     → 'free'  (auto-downgrade)
    - active                 → subscription.plan_code  (or 'free' if unknown code)
    - else                   → 'free'   (expired / cancelled / missing)
    """
    if subscription is None:
        return "free"
    if subscription.status == "pending_payment":
        return "free"
    if subscription.status == "trialing":
        # Check if trial has actually expired
        from datetime import datetime, timezone
        if subscription.trial_ends_at and subscription.trial_ends_at.replace(
            tzinfo=timezone.utc
        ) < datetime.now(timezone.utc):
            return "free"
        return "trial"
    if subscription.status == "active":
        code = subscription.plan_code or "free"
        return code if code in PLAN_LIMITS else "free"
    return "free"


def get_limit(plan_code: str, action: str) -> Optional[int]:
    """Return the monthly numeric limit for an action, or None (unlimited)."""
    plan = PLAN_LIMITS.get(plan_code, PLAN_LIMITS["free"])
    return plan.get(action)


def can_access_premium(plan_code: str) -> bool:
    """Return True if this plan has access to premium pages/features."""
    plan = PLAN_LIMITS.get(plan_code, PLAN_LIMITS["free"])
    return bool(plan.get("access_premium", False))
