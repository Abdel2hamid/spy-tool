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

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise _UNAUTHORIZED

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise _UNAUTHORIZED

    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user_id, Membership.workspace_id == workspace_id)
        .first()
    )
    if not membership:
        raise _UNAUTHORIZED

    subscription = (
        db.query(Subscription).filter(Subscription.workspace_id == workspace_id).first()
    )

    return AuthContext(
        user=user,
        workspace=workspace,
        membership=membership,
        subscription=subscription,
    )
