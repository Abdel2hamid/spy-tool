"""
Plan enforcement service.

Usage in route handlers:
    from app.services.plan_enforcement import PlanEnforcer

    # Optional auth — returns NoOpEnforcer if unauthenticated (backward-compat)
    enforcer = PlanEnforcer.from_token(credentials, db)
    enforcer.check("app_imports")   # raises HTTP 402 if over limit
    # ... perform the action ...
    enforcer.increment("app_imports")   # commit usage increment

    # Or check + increment in one call:
    enforcer.check_and_increment("app_imports")

    # Usage summary for GET /usage:
    summary = enforcer.get_summary()
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config.plans import (
    _ACTION_LABELS,
    _UPGRADE_MESSAGES,
    PLAN_LIMITS,
    get_effective_plan,
    get_limit,
)
from app.models.models import Subscription, WorkspaceUsage
from app.services.auth_service import decode_access_token

logger = logging.getLogger(__name__)

_TRACKED_ACTIONS = ("app_imports", "keyword_refreshes", "ai_requests", "exports")


# ---------------------------------------------------------------------------
# Main enforcer
# ---------------------------------------------------------------------------

class PlanEnforcer:
    """Stateful enforcer bound to a specific workspace + calendar month."""

    def __init__(
        self,
        db: Session,
        workspace_id: int,
        subscription: Optional[Subscription],
    ):
        self.db = db
        self.workspace_id = workspace_id
        self.plan_code = get_effective_plan(subscription)
        self._month = datetime.now(timezone.utc).strftime("%Y-%m")

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_token(
        cls,
        credentials,  # Optional[HTTPAuthorizationCredentials]
        db: Session,
    ) -> "PlanEnforcer | _NoOpEnforcer":
        """
        Build a PlanEnforcer from optional HTTPBearer credentials.
        Returns a _NoOpEnforcer if credentials are absent or invalid — this
        preserves backward-compatibility with unauthenticated route callers.
        """
        if not credentials:
            return _NoOpEnforcer()
        try:
            payload = decode_access_token(credentials.credentials)
        except Exception:
            return _NoOpEnforcer()
        if not payload:
            return _NoOpEnforcer()
        workspace_id = int(payload.get("workspace_id", 0))
        if not workspace_id:
            return _NoOpEnforcer()
        subscription = (
            db.query(Subscription)
            .filter(Subscription.workspace_id == workspace_id)
            .first()
        )
        return cls(db, workspace_id, subscription)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_usage(self) -> WorkspaceUsage:
        row = (
            self.db.query(WorkspaceUsage)
            .filter(
                WorkspaceUsage.workspace_id == self.workspace_id,
                WorkspaceUsage.month == self._month,
            )
            .first()
        )
        if not row:
            row = WorkspaceUsage(
                workspace_id=self.workspace_id,
                month=self._month,
            )
            self.db.add(row)
            self.db.flush()
        return row

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, action: str) -> None:
        """
        Raise HTTP 402 if the workspace has reached its plan limit for action.
        No-op if the plan has unlimited access (limit=None).
        """
        limit = get_limit(self.plan_code, action)
        if limit is None:
            return  # unlimited plan

        usage = self._get_or_create_usage()
        current = getattr(usage, action, 0) or 0

        if current >= limit:
            label = _ACTION_LABELS.get(action, action.replace("_", " "))
            upgrade_msg = _UPGRADE_MESSAGES.get(
                self.plan_code, "Upgrade to unlock higher limits."
            )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "code": "PLAN_LIMIT_EXCEEDED",
                    "action": action,
                    "message": f"You've reached your monthly {label} limit ({limit}/{limit}).",
                    "current_usage": current,
                    "limit": limit,
                    "plan": self.plan_code,
                    "upgrade_message": upgrade_msg,
                },
            )

    def increment(self, action: str) -> None:
        """
        Increment the usage counter for action by 1 and commit.
        Safe to call even if action is not tracked.
        """
        if action not in _TRACKED_ACTIONS:
            return
        try:
            usage = self._get_or_create_usage()
            current = getattr(usage, action, 0) or 0
            setattr(usage, action, current + 1)
            self.db.commit()
        except Exception as exc:
            logger.warning("plan_enforcement.increment failed: %s", exc)
            self.db.rollback()

    def check_and_increment(self, action: str) -> None:
        """Check limit then immediately increment. Use for single-step operations."""
        self.check(action)
        self.increment(action)

    def get_summary(self) -> dict:
        """
        Return the current month's usage + limits for this workspace.
        """
        usage = self._get_or_create_usage()
        plan = PLAN_LIMITS.get(self.plan_code, PLAN_LIMITS["free"])
        result: dict = {
            "plan": self.plan_code,
            "month": self._month,
            "usage": {},
            "limits": {},
        }
        for action in _TRACKED_ACTIONS:
            result["usage"][action] = getattr(usage, action, 0) or 0
            result["limits"][action] = plan.get(action)
        return result


# ---------------------------------------------------------------------------
# No-op fallback (unauthenticated callers)
# ---------------------------------------------------------------------------

class _NoOpEnforcer:
    """All operations are no-ops. Returned when no valid auth token is present."""

    def check(self, action: str) -> None:
        pass

    def increment(self, action: str) -> None:
        pass

    def check_and_increment(self, action: str) -> None:
        pass

    def get_summary(self) -> dict:
        return {
            "plan": "unknown",
            "month": "",
            "usage": {a: 0 for a in _TRACKED_ACTIONS},
            "limits": {a: None for a in _TRACKED_ACTIONS},
        }
