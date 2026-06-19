"""
FastAPI dependency functions for authentication.

Usage in route handlers:
    @router.get("/protected")
    def my_route(current_user: User = Depends(get_current_user)):
        ...

    @router.get("/workspace-scoped")
    def my_route(
        ctx: AuthContext = Depends(get_auth_context),
    ):
        # ctx.user, ctx.workspace, ctx.membership, ctx.subscription
        ...
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from sqlalchemy import and_

from app.database import get_db
from app.models.models import Membership, Subscription, User, Workspace
from app.services.auth_service import decode_access_token

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass
class AuthContext:
    user: User
    workspace: Workspace
    membership: Membership
    subscription: Optional[Subscription]


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the Bearer JWT; return the User row."""
    if not credentials:
        logger.warning("[AUTH] 401 — no Bearer token in request")
        raise _UNAUTHORIZED

    payload = decode_access_token(credentials.credentials)
    if not payload:
        logger.warning("[AUTH] 401 — token decode failed (expired or invalid)")
        raise _UNAUTHORIZED

    user_id = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        logger.warning(f"[AUTH] 401 — user_id={user_id} not found or inactive")
        raise _UNAUTHORIZED

    return user


def get_auth_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    """
    Richer dependency that resolves user + workspace + membership + subscription
    from the JWT in a single pass.
    """
    if not credentials:
        raise _UNAUTHORIZED

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise _UNAUTHORIZED

    user_id = int(payload.get("sub", 0))
    workspace_id = int(payload.get("workspace_id", 0))

    # Single JOIN query instead of 4 separate queries
    row = (
        db.query(User, Workspace, Membership, Subscription)
        .join(Membership, and_(
            Membership.user_id == User.id,
            Membership.workspace_id == workspace_id,
        ))
        .join(Workspace, Workspace.id == workspace_id)
        .outerjoin(Subscription, Subscription.workspace_id == workspace_id)
        .filter(User.id == user_id, User.is_active == True)
        .first()
    )
    if not row:
        raise _UNAUTHORIZED

    user, workspace, membership, subscription = row
    return AuthContext(
        user=user,
        workspace=workspace,
        membership=membership,
        subscription=subscription,
    )


def get_superadmin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Require a superadmin user. Returns the User or raises 403."""
    if not credentials:
        raise _UNAUTHORIZED
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise _UNAUTHORIZED
    user_id = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise _UNAUTHORIZED
    if not user.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user
