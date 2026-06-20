"""
Auth endpoints:
  POST /auth/register            → create user + workspace + trial
  POST /auth/login               → verify credentials, return token
  GET  /auth/me                  → return current user + workspace info
  GET  /auth/verify-email        → verify email from link
  POST /auth/resend-verification → resend verification email
  POST /auth/create-checkout-after-verify → create Stripe checkout after email verified
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
    EmailNotVerified,
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


_COMMON_PASSWORDS = frozenset([
    "password", "12345678", "123456789", "1234567890", "qwerty123",
    "password1", "iloveyou", "sunshine1", "princess1", "football1",
    "abc12345", "abcdefgh", "admin123", "letmein12", "welcome1",
    "monkey123", "master12", "dragon12", "login123", "qwertyui",
])


def _validate_password(v: str) -> str:
    """Enforce strong password: 8-72 chars, mixed character types, not common."""
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v) > 72:
        raise ValueError("Password must be at most 72 characters")  # bcrypt limit
    has_upper = any(c.isupper() for c in v)
    has_lower = any(c.islower() for c in v)
    has_digit = any(c.isdigit() for c in v)
    if not (has_upper and has_lower and has_digit):
        raise ValueError(
            "Password must contain at least one uppercase letter, "
            "one lowercase letter, and one digit"
        )
    if v.lower() in _COMMON_PASSWORDS:
        raise ValueError("This password is too common. Please choose a stronger one.")
    return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    plan_code: str = "starter"

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("plan_code")
    @classmethod
    def valid_plan(cls, v: str) -> str:
        if v not in ("starter", "pro"):
            raise ValueError("Please select a paid plan (starter or pro)")
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
    trial_expired: bool = False


class WorkspaceInfo(BaseModel):
    id: int
    name: str
    slug: str
    role: str
    subscription: Optional[SubscriptionInfo]


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class UserInfo(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_superadmin: bool = False
    email_verified: bool = False
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo
    workspace: WorkspaceInfo
    checkout_url: Optional[str] = None
    requires_email_verification: bool = False


class MeResponse(BaseModel):
    user: UserInfo
    workspace: WorkspaceInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _subscription_info(sub, membership_role: str) -> Optional[SubscriptionInfo]:
    if not sub:
        return SubscriptionInfo(
            plan_code="expired",
            status="expired",
            trial_ends_at=None,
            is_trialing=False,
            trial_days_left=None,
            trial_expired=True,
        )
    now = datetime.now(timezone.utc)
    trial_days_left = None
    is_trialing = sub.status == "trialing"
    trial_expired = False
    if is_trialing and sub.trial_ends_at:
        trial_end = sub.trial_ends_at
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        remaining = (trial_end - now).days
        trial_days_left = max(0, remaining)
        trial_expired = trial_end < now
    elif sub.status not in ("active", "pending_payment", "trialing"):
        # canceled, past_due, etc. — treat as expired
        trial_expired = True
    return SubscriptionInfo(
        plan_code=sub.plan_code,
        status=sub.status,
        trial_ends_at=sub.trial_ends_at,
        is_trialing=is_trialing,
        trial_days_left=trial_days_left,
        trial_expired=trial_expired,
    )


def _build_auth_response(user, workspace, membership, subscription, token: str) -> AuthResponse:
    return AuthResponse(
        access_token=token,
        user=UserInfo(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_superadmin=user.is_superadmin,
            email_verified=user.email_verified,
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

    Flow:
    1. Create user + workspace + subscription
    2. If Resend configured → send verification email, return requires_email_verification=True
    3. If Resend not configured → create Stripe checkout immediately

    If email already exists but never completed verification/payment, allow retry.
    """
    from app.models.models import Membership, Subscription, User, Workspace
    from app.services.stripe_service import is_configured as stripe_configured
    from app.services.email_service import is_configured as email_configured, send_verification_email
    from app.services.auth_service import verify_password, create_access_token

    is_retry = False
    try:
        user, workspace, token = register_user(
            db,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            plan_code=body.plan_code,
        )
    except EmailAlreadyRegistered:
        # Check if this is a retry — user exists but never completed signup
        existing_user = db.query(User).filter(User.email == body.email.lower().strip()).first()
        if not existing_user or not verify_password(body.password, existing_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unable to create account. Please try a different email or sign in.",
            )
        mem = db.query(Membership).filter(Membership.user_id == existing_user.id).first()
        if not mem:
            raise HTTPException(status.HTTP_409_CONFLICT, "Account exists. Please sign in.")
        sub = db.query(Subscription).filter(Subscription.workspace_id == mem.workspace_id).first()
        if not sub or sub.status not in ("pending_payment", "trialing"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unable to create account. Please try a different email or sign in.",
            )
        user = existing_user
        workspace = db.query(Workspace).filter(Workspace.id == mem.workspace_id).first()
        token = create_access_token(user.id, workspace.id)
        is_retry = True

    membership = db.query(Membership).filter(
        Membership.user_id == user.id, Membership.workspace_id == workspace.id
    ).first()
    subscription = db.query(Subscription).filter(
        Subscription.workspace_id == workspace.id
    ).first()

    # Step 1: Email verification (if Resend configured and email not yet verified)
    if email_configured() and not user.email_verified:
        send_verification_email(user.email, user.id, user.full_name)
        resp = _build_auth_response(user, workspace, membership, subscription, token)
        resp.requires_email_verification = True
        return resp

    # Step 2: Stripe checkout (if email already verified or Resend not configured)
    checkout_url = None
    if stripe_configured() and subscription:
        try:
            from app.services import stripe_service
            from app.config import settings as _s

            if not subscription.stripe_customer_id:
                customer = stripe_service.create_customer(
                    email=user.email, name=user.full_name,
                )
                subscription.stripe_customer_id = customer.id
            subscription.status = "pending_payment"
            if not is_retry:
                subscription.plan_code = body.plan_code
            db.commit()

            session = stripe_service.create_checkout_session(
                customer_id=subscription.stripe_customer_id,
                plan_code=body.plan_code,
                success_url=f"{_s.frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{_s.frontend_url}/signup",
            )
            checkout_url = session.url
        except Exception as exc:
            import logging as _log
            _log.getLogger(__name__).error("Stripe setup failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Payment setup failed: {type(exc).__name__}: {exc}",
            )

    resp = _build_auth_response(user, workspace, membership, subscription, token)
    resp.checkout_url = checkout_url
    return resp


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
    except EmailNotVerified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before signing in. Check your inbox for the verification link.",
        )

    from app.services.user_activity import log_user_action
    log_user_action(db, user.id, "auth.login")
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
            email_verified=ctx.user.email_verified,
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
            email_verified=ctx.user.email_verified,
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


@router.post(
    "/password",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit(5, 60))],
)
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


# ---------------------------------------------------------------------------
# Email verification endpoints
# ---------------------------------------------------------------------------

@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify email address from the link sent during registration."""
    from app.services.email_service import decode_email_verification_token
    from app.models.models import User

    payload = decode_email_verification_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link.",
        )

    user_id = int(payload["sub"])
    email = payload["email"]

    user = db.query(User).filter(User.id == user_id, User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not user.email_verified:
        user.email_verified = True
        db.commit()

    return {"ok": True, "message": "Email verified successfully."}


@router.post(
    "/resend-verification",
    dependencies=[Depends(rate_limit(2, 120))],
)
def resend_verification(body: ResendVerificationRequest, db: Session = Depends(get_db)):
    """Resend the email verification link."""
    from app.services.email_service import send_verification_email
    from app.models.models import User

    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if user and not user.email_verified:
        send_verification_email(user.email, user.id, user.full_name)

    # Always return success to prevent email enumeration
    return {"ok": True, "message": "If the email is registered, a new verification link has been sent."}


@router.post("/create-checkout-after-verify")
def create_checkout_after_verify(
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Create a Stripe checkout session after email has been verified."""
    if not ctx.user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email first.",
        )

    from app.services.stripe_service import is_configured
    if not is_configured():
        return {"checkout_url": None}

    subscription = ctx.subscription
    if not subscription:
        raise HTTPException(status_code=400, detail="No subscription found.")

    from app.services import stripe_service
    from app.config import settings as _s

    if not subscription.stripe_customer_id:
        customer = stripe_service.create_customer(
            email=ctx.user.email, name=ctx.user.full_name,
        )
        subscription.stripe_customer_id = customer.id

    subscription.status = "pending_payment"
    db.commit()

    try:
        session = stripe_service.create_checkout_session(
            customer_id=subscription.stripe_customer_id,
            plan_code=subscription.plan_code,
            success_url=f"{_s.frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{_s.frontend_url}/signup",
        )
        return {"checkout_url": session.url}
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).error("Stripe checkout failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment setup failed: {type(exc).__name__}: {exc}",
        )
