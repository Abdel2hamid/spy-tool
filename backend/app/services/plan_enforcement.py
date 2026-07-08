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
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config.plans import (
    _ACTION_LABELS,
    _UPGRADE_MESSAGES,
    PLAN_LIMITS,
    can_access_premium,
    get_effective_plan,
    get_limit,
)
from app.models.models import Subscription, User, WorkspaceUsage
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
        is_superadmin: bool = False,
    ):
        self.db = db
        self.workspace_id = workspace_id
        self.plan_code = get_effective_plan(subscription)
        self.is_superadmin = is_superadmin
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
        # Check if user is superadmin — bypass plan restrictions
        user_id = int(payload.get("sub", 0))
        is_superadmin = False
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            is_superadmin = bool(user and user.is_superadmin)
        return cls(db, workspace_id, subscription, is_superadmin=is_superadmin)

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

    def _require_active_subscription(self) -> None:
        """Raise HTTP 403 if the user's trial has expired and they have no paid plan."""
        if self.plan_code in ("expired", "free"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "SUBSCRIPTION_REQUIRED",
                    "message": "Your free trial has ended. Please subscribe to continue using RankSpy.",
                    "plan": self.plan_code,
                    "upgrade_message": _UPGRADE_MESSAGES.get(self.plan_code, "Subscribe to a paid plan to continue."),
                },
            )

    def check_premium(self) -> None:
        """
        Raise HTTP 403 if the workspace plan does not include premium features.
        Expired users get SUBSCRIPTION_REQUIRED. Superadmins bypass.
        """
        if self.is_superadmin:
            return
        self._require_active_subscription()
        if not can_access_premium(self.plan_code):
            upgrade_msg = _UPGRADE_MESSAGES.get(
                self.plan_code, "Upgrade to unlock premium features."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PREMIUM_REQUIRED",
                    "message": "This feature requires a paid plan.",
                    "plan": self.plan_code,
                    "upgrade_message": upgrade_msg,
                },
            )

    def check(self, action: str) -> None:
        """
        Raise HTTP 402 if the workspace has reached its plan limit for action.
        Expired users get SUBSCRIPTION_REQUIRED. Superadmins bypass.
        """
        if self.is_superadmin:
            return
        self._require_active_subscription()
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

    # ------------------------------------------------------------------
    # Atomic usage accounting
    #
    # These run on a DEDICATED short-lived session (never the request session)
    # so a usage write/rollback can't discard the handler's other pending work,
    # and the increment is done at the SQL level (UPSERT / conditional UPDATE)
    # so concurrent requests can't lose updates and slip past a plan limit.
    # ------------------------------------------------------------------

    def _atomic_add(self, action: str, delta: int = 1) -> None:
        """Atomically upsert the month's usage row and add `delta` to `action`.

        `action` is always drawn from the fixed `_TRACKED_ACTIONS` whitelist, so
        using it as a column name is safe.
        """
        from app.database import SessionLocal  # noqa: PLC0415

        col = getattr(WorkspaceUsage, action)
        session = SessionLocal()
        try:
            stmt = (
                pg_insert(WorkspaceUsage)
                .values(workspace_id=self.workspace_id, month=self._month, **{action: delta})
                .on_conflict_do_update(
                    index_elements=["workspace_id", "month"],
                    set_={action: col + delta},
                )
            )
            session.execute(stmt)
            session.commit()
        except Exception as exc:  # infra error — log, don't penalise the user
            session.rollback()
            logger.warning("plan_enforcement._atomic_add(%s) failed: %s", action, exc)
        finally:
            session.close()

    def _atomic_add_if_below(self, action: str, limit: int) -> bool:
        """Atomically increment `action` only if it is currently `< limit`.

        Returns True if the increment happened (was under limit), False if the
        limit was already reached. Race-free: the guard and the write are one
        SQL statement, so two concurrent requests at the boundary can't both win.
        """
        from app.database import SessionLocal  # noqa: PLC0415

        col = getattr(WorkspaceUsage, action)
        session = SessionLocal()
        try:
            # Ensure the row exists (no-op if it already does).
            session.execute(
                pg_insert(WorkspaceUsage)
                .values(workspace_id=self.workspace_id, month=self._month)
                .on_conflict_do_nothing(index_elements=["workspace_id", "month"])
            )
            res = session.execute(
                update(WorkspaceUsage)
                .where(
                    WorkspaceUsage.workspace_id == self.workspace_id,
                    WorkspaceUsage.month == self._month,
                    col < limit,
                )
                .values({action: col + 1})
            )
            session.commit()
            return res.rowcount > 0
        except Exception as exc:  # infra error — fail open (don't block a paying user)
            session.rollback()
            logger.warning("plan_enforcement._atomic_add_if_below(%s) failed: %s", action, exc)
            return True
        finally:
            session.close()

    def increment(self, action: str) -> None:
        """
        Increment the usage counter for `action` by 1 (atomic, own session).
        Safe to call even if `action` is not tracked.

        Prefer `check_and_increment` for metered actions — it is race-free
        against the plan limit. Plain `increment` is for the
        check()-do-work-increment() pattern where a small over-count is
        tolerable.
        """
        if action not in _TRACKED_ACTIONS:
            return
        self._atomic_add(action, 1)

    def check_and_increment(self, action: str) -> None:
        """Atomically enforce the limit and increment. Race-free — use this for
        single-step metered operations."""
        if self.is_superadmin:
            return
        self._require_active_subscription()
        if action not in _TRACKED_ACTIONS:
            return
        limit = get_limit(self.plan_code, action)
        if limit is None:
            self._atomic_add(action, 1)  # unlimited plan — just count
            return
        if not self._atomic_add_if_below(action, limit):
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
                    "current_usage": limit,
                    "limit": limit,
                    "plan": self.plan_code,
                    "upgrade_message": upgrade_msg,
                },
            )

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
    """Returned when no valid auth token is present.

    Applies free-plan limits so unauthenticated callers are NOT granted
    unlimited access.  Previously this was a no-op (unlimited), which was
    more permissive than even the Pro plan.
    """

    def check_premium(self) -> None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PREMIUM_REQUIRED",
                "message": "This feature requires a paid plan. Please sign up or log in.",
                "plan": "free",
                "upgrade_message": "Start your free trial or upgrade to Pro for higher limits.",
            },
        )

    def check(self, action: str) -> None:
        limit = get_limit("free", action)
        if limit is not None and limit <= 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for this action.",
            )

    def increment(self, action: str) -> None:
        pass  # nothing to track without a workspace

    def check_and_increment(self, action: str) -> None:
        self.check(action)

    def get_summary(self) -> dict:
        free = PLAN_LIMITS["free"]
        return {
            "plan": "free",
            "month": "",
            "usage": {a: 0 for a in _TRACKED_ACTIONS},
            "limits": {a: free.get(a) for a in _TRACKED_ACTIONS},
        }
