"""
Auth service — password hashing, JWT, registration, login.

Registration flow:
  1. Create User (hashed password)
  2. Create Workspace  (slug = email prefix + random suffix)
  3. Create Membership  (role = 'owner')
  4. Create Subscription (plan = 'trial', 14-day trial)
  → returns (user, workspace, token)
"""

from __future__ import annotations

import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import Membership, Subscription, User, Workspace

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

TRIAL_DAYS = 14


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(user_id: int, workspace_id: int) -> str:
    """Create a JWT encoding user_id + workspace_id."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "workspace_id": workspace_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT. Returns payload dict or None on failure."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Workspace slug
# ---------------------------------------------------------------------------

def _slug_from_email(email: str) -> str:
    """Derive a URL-safe slug from the email local part + 4-char suffix."""
    local = email.split("@")[0]
    safe = re.sub(r"[^a-z0-9]+", "-", local.lower()).strip("-")[:30]
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"{safe}-{suffix}"


def _ensure_unique_slug(db: Session, base: str) -> str:
    slug = base
    while db.query(Workspace).filter(Workspace.slug == slug).first():
        suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
        slug = f"{base}-{suffix}"
    return slug


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class EmailAlreadyRegistered(Exception):
    pass


def register_user(
    db: Session,
    email: str,
    password: str,
    full_name: Optional[str] = None,
) -> tuple[User, Workspace, str]:
    """
    Create user + workspace + membership(owner) + trial subscription.
    Returns (user, workspace, access_token).
    Raises EmailAlreadyRegistered if email is taken.
    """
    email = email.lower().strip()

    if db.query(User).filter(User.email == email).first():
        raise EmailAlreadyRegistered(f"Email already registered: {email}")

    # 1. User
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        is_active=True,
    )
    db.add(user)
    db.flush()  # get user.id without commit

    # 2. Workspace
    base_slug = _slug_from_email(email)
    slug = _ensure_unique_slug(db, base_slug)
    workspace_name = (full_name or email.split("@")[0]).title() + "'s Workspace"
    workspace = Workspace(name=workspace_name, slug=slug)
    db.add(workspace)
    db.flush()  # get workspace.id

    # 3. Membership — owner
    membership = Membership(user_id=user.id, workspace_id=workspace.id, role="owner")
    db.add(membership)

    # 4. Subscription — 14-day trial
    trial_end = datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)
    subscription = Subscription(
        workspace_id=workspace.id,
        plan_code="trial",
        status="trialing",
        trial_ends_at=trial_end,
    )
    db.add(subscription)

    db.commit()
    db.refresh(user)
    db.refresh(workspace)

    token = create_access_token(user.id, workspace.id)
    return user, workspace, token


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class InvalidCredentials(Exception):
    pass


def login_user(db: Session, email: str, password: str) -> tuple[User, Workspace, str]:
    """
    Verify credentials and return (user, workspace, access_token).
    Uses the user's first owned workspace (or first membership if no owner role).
    Raises InvalidCredentials on failure.
    """
    email = email.lower().strip()

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user or not verify_password(password, user.password_hash):
        raise InvalidCredentials("Invalid email or password")

    # Prefer owner workspace; fall back to first membership
    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.role == "owner")
        .first()
        or db.query(Membership).filter(Membership.user_id == user.id).first()
    )
    if not membership:
        raise InvalidCredentials("No workspace found for this user")

    workspace = db.query(Workspace).filter(Workspace.id == membership.workspace_id).first()
    token = create_access_token(user.id, workspace.id)
    return user, workspace, token
