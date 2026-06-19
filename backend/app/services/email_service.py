"""
Email service — sends transactional emails via Resend.

Currently supports:
  - Email verification on signup
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def create_email_verification_token(user_id: int, email: str) -> str:
    """Create a short-lived JWT for email verification."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "purpose": "email_verify",
        "iat": now,
        "exp": now + timedelta(minutes=settings.email_verification_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_email_verification_token(token: str) -> dict | None:
    """Decode and validate an email verification JWT. Returns payload or None."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require_exp": True, "require_sub": True},
        )
        if payload.get("purpose") != "email_verify":
            return None
        return payload
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Email sending via Resend
# ---------------------------------------------------------------------------

def is_configured() -> bool:
    return bool(settings.resend_api_key)


def send_verification_email(email: str, user_id: int, full_name: str | None = None) -> bool:
    """Send email verification link via Resend. Returns True on success."""
    if not is_configured():
        logger.warning("Resend not configured — skipping verification email for %s", email)
        return False

    import resend
    resend.api_key = settings.resend_api_key

    token = create_email_verification_token(user_id, email)
    verify_url = f"{settings.frontend_url}/verify-email?token={token}"
    display_name = full_name or email.split("@")[0]

    try:
        resend.Emails.send({
            "from": settings.resend_from_email,
            "to": [email],
            "subject": "Verify your RankSpy account",
            "html": f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
                <div style="text-align: center; margin-bottom: 32px;">
                    <h1 style="color: #4F46E5; font-size: 24px; margin: 0;">RankSpy</h1>
                </div>
                <h2 style="color: #111827; font-size: 20px; margin-bottom: 8px;">Verify your email address</h2>
                <p style="color: #6B7280; font-size: 15px; line-height: 1.6;">
                    Hi {display_name},<br><br>
                    Thanks for signing up! Please verify your email address by clicking the button below.
                </p>
                <div style="text-align: center; margin: 32px 0;">
                    <a href="{verify_url}"
                       style="display: inline-block; background: #4F46E5; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
                        Verify Email Address
                    </a>
                </div>
                <p style="color: #9CA3AF; font-size: 13px; line-height: 1.5;">
                    This link expires in {settings.email_verification_token_expire_minutes} minutes.<br>
                    If you didn't create an account, you can safely ignore this email.
                </p>
                <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 24px 0;" />
                <p style="color: #9CA3AF; font-size: 12px;">
                    Can't click the button? Copy and paste this URL:<br>
                    <a href="{verify_url}" style="color: #4F46E5; word-break: break-all;">{verify_url}</a>
                </p>
            </div>
            """,
        })
        logger.info("Verification email sent to %s", email)
        return True
    except Exception as exc:
        logger.error("Failed to send verification email to %s: %s", email, exc, exc_info=True)
        return False
