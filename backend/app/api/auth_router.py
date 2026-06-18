"""
Auth endpoints:
  POST /auth/register   → create user + workspace + trial
  POST /auth/login      → verify credentials, return token
  GET  /auth/me         → return current user + workspace info
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, get_auth_context
from app.database import get_db
from app.utils.rate_limiter import rate_limit
from app.services.auth_service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    login_user,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas  (local — don't pollute global schemas.py)
# ---------------------------------------------------------------------------

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    workspace_name: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SubscriptionInfo(BaseModel):
    plan_code: str
    status: str
    trial_ends_at: Optional[datetime]
    is_trialing: bool
    trial_days_left: Optional[int]


class WorkspaceInfo(BaseModel):
    id: int
    name: str
    slug: str
    role: str
    subscription: Optional[SubscriptionInfo]


class UserInfo(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_superadmin: bool = False
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo
    workspace: WorkspaceInfo


class MeResponse(BaseModel):
    user: UserInfo
    workspace: WorkspaceInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _subscription_info(sub, membership_role: str) -> Optional[SubscriptionInfo]:
    if not sub:
        return None
    now = datetime.now(timezone.utc)
    trial_days_left = None
    is_trialing = sub.status == "trialing"
    if is_trialing and sub.trial_ends_at:
        trial_end = sub.trial_ends_at
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        remaining = (trial_end - now).days
        trial_days_left = max(0, remaining)
    return SubscriptionInfo(
        plan_code=sub.plan_code,
        status=sub.status,
        trial_ends_at=sub.trial_ends_at,
        is_trialing=is_trialing,
        trial_days_left=trial_days_left,
    )


def _build_auth_response(user, workspace, membership, subscription, token: str) -> AuthResponse:
    return AuthResponse(
        access_token=token,
        user=UserInfo(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at,
        ),
        workspace=WorkspaceInfo(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            role=membership.role,
            subscription=_subscription_info(subscription, membership.role),
        ),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(3, 60))],
)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new user account.

    Side effects:
    - Creates a personal Workspace
    - Assigns owner role
    - Starts a 14-day trial subscription
    """
    try:
        user, workspace, token = register_user(
            db, email=body.email, password=body.password, full_name=body.full_name
        )
    except EmailAlreadyRegistered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    from app.models.models import Membership, Subscription
    membership = db.query(Membership).filter(
        Membership.user_id == user.id, Membership.workspace_id == workspace.id
    ).first()
    subscription = db.query(Subscription).filter(
        Subscription.workspace_id == workspace.id
    ).first()

    return _build_auth_response(user, workspace, membership, subscription, token)


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit(5, 60))],
)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email + password. Returns JWT access token."""
    try:
        user, workspace, membership, subscription, token = login_user(
            db, email=body.email, password=body.password
        )
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    return _build_auth_response(user, workspace, membership, subscription, token)


@router.get("/me", response_model=MeResponse)
def get_me(ctx: AuthContext = Depends(get_auth_context)):
    """Return current authenticated user and workspace details."""
    return MeResponse(
        user=UserInfo(
            id=ctx.user.id,
            email=ctx.user.email,
            full_name=ctx.user.full_name,
            is_superadmin=ctx.user.is_superadmin,
            created_at=ctx.user.created_at,
        ),
        workspace=WorkspaceInfo(
            id=ctx.workspace.id,
            name=ctx.workspace.name,
            slug=ctx.workspace.slug,
            role=ctx.membership.role,
            subscription=_subscription_info(ctx.subscription, ctx.membership.role),
        ),
    )


@router.patch("/profile", response_model=MeResponse)
def update_profile(
    body: UpdateProfileRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Update display name and/or workspace name."""
    if body.full_name is not None:
        ctx.user.full_name = body.full_name.strip() or None
    if body.workspace_name is not None:
        name = body.workspace_name.strip()
        if name:
            ctx.workspace.name = name
    db.commit()
    db.refresh(ctx.user)
    db.refresh(ctx.workspace)
    return MeResponse(
        user=UserInfo(
            id=ctx.user.id,
            email=ctx.user.email,
            full_name=ctx.user.full_name,
            is_superadmin=ctx.user.is_superadmin,
            created_at=ctx.user.created_at,
        ),
        workspace=WorkspaceInfo(
            id=ctx.workspace.id,
            name=ctx.workspace.name,
            slug=ctx.workspace.slug,
            role=ctx.membership.role,
            subscription=_subscription_info(ctx.subscription, ctx.membership.role),
        ),
    )


@router.post("/password", status_code=status.HTTP_200_OK)
def change_password(
    body: ChangePasswordRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Change account password. Requires correct current password."""
    from app.services.auth_service import hash_password, verify_password
    if not verify_password(body.current_password, ctx.user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    ctx.user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}
