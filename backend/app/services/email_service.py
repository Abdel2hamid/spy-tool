"""
Email service — sends transactional emails via Resend.

Supports:
  - Email verification on signup
  - Trial ending reminder (3 days before)
  - Subscription cancellation confirmation
  - Payment failure notification
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


# ---------------------------------------------------------------------------
# Billing notification emails
# ---------------------------------------------------------------------------

PLAN_PRICES: dict[str, str] = {
    "starter": "$19.99",
    "pro": "$49.99",
}


def _send_email(to: str, subject: str, html: str) -> bool:
    """Low-level helper to send an email via Resend."""
    if not is_configured():
        logger.warning("Resend not configured — skipping email to %s", to)
        return False
    try:
        import resend
        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": settings.resend_from_email,
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc, exc_info=True)
        return False


def _email_wrapper(body: str) -> str:
    """Wrap email body in consistent template."""
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #4F46E5; font-size: 24px; margin: 0;">RankSpy</h1>
        </div>
        {body}
        <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 24px 0;" />
        <p style="color: #9CA3AF; font-size: 12px; text-align: center;">
            You&rsquo;re receiving this because you have an account at RankSpy.<br>
            <a href="{settings.frontend_url}/settings" style="color: #4F46E5;">Manage your subscription</a>
        </p>
    </div>
    """


def send_trial_ending_email(
    email: str,
    plan_code: str,
    trial_end_date: str,
    full_name: str | None = None,
) -> bool:
    """Notify user their trial is ending in 3 days and they'll be charged."""
    display_name = full_name or email.split("@")[0]
    price = PLAN_PRICES.get(plan_code, plan_code)
    plan_name = plan_code.capitalize()

    return _send_email(
        to=email,
        subject=f"Your RankSpy trial ends on {trial_end_date}",
        html=_email_wrapper(f"""
            <h2 style="color: #111827; font-size: 20px; margin-bottom: 8px;">Your free trial is ending soon</h2>
            <p style="color: #6B7280; font-size: 15px; line-height: 1.6;">
                Hi {display_name},<br><br>
                Your 7-day free trial of the <strong>{plan_name}</strong> plan ends on <strong>{trial_end_date}</strong>.
            </p>
            <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 16px; margin: 20px 0;">
                <p style="color: #111827; font-size: 14px; margin: 0 0 4px 0;"><strong>What happens next:</strong></p>
                <p style="color: #6B7280; font-size: 14px; margin: 0; line-height: 1.6;">
                    Your subscription will automatically renew at <strong>{price}/month</strong>.
                    If you don&rsquo;t want to continue, you can cancel anytime before your trial ends.
                </p>
            </div>
            <div style="text-align: center; margin: 24px 0;">
                <a href="{settings.frontend_url}/settings"
                   style="display: inline-block; background: #4F46E5; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
                    Manage Subscription
                </a>
            </div>
            <p style="color: #9CA3AF; font-size: 13px; line-height: 1.5;">
                To cancel, go to Settings &rarr; Billing &rarr; Manage Subscription.
            </p>
        """),
    )


def send_cancellation_email(
    email: str,
    plan_code: str,
    full_name: str | None = None,
) -> bool:
    """Confirm subscription cancellation to user."""
    display_name = full_name or email.split("@")[0]
    plan_name = plan_code.capitalize()

    return _send_email(
        to=email,
        subject="Your RankSpy subscription has been cancelled",
        html=_email_wrapper(f"""
            <h2 style="color: #111827; font-size: 20px; margin-bottom: 8px;">Subscription cancelled</h2>
            <p style="color: #6B7280; font-size: 15px; line-height: 1.6;">
                Hi {display_name},<br><br>
                Your <strong>{plan_name}</strong> plan has been cancelled. You won&rsquo;t be charged again.
            </p>
            <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 16px; margin: 20px 0;">
                <p style="color: #6B7280; font-size: 14px; margin: 0; line-height: 1.6;">
                    You can resubscribe anytime from your Settings page to regain full access.
                </p>
            </div>
            <div style="text-align: center; margin: 24px 0;">
                <a href="{settings.frontend_url}/settings"
                   style="display: inline-block; background: #4F46E5; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
                    Resubscribe
                </a>
            </div>
        """),
    )


def send_payment_failed_email(
    email: str,
    full_name: str | None = None,
) -> bool:
    """Notify user their payment failed."""
    display_name = full_name or email.split("@")[0]

    return _send_email(
        to=email,
        subject="RankSpy: Payment failed — action required",
        html=_email_wrapper(f"""
            <h2 style="color: #DC2626; font-size: 20px; margin-bottom: 8px;">Payment failed</h2>
            <p style="color: #6B7280; font-size: 15px; line-height: 1.6;">
                Hi {display_name},<br><br>
                We were unable to process your latest payment. Please update your payment method to avoid losing access to your account.
            </p>
            <div style="text-align: center; margin: 24px 0;">
                <a href="{settings.frontend_url}/settings"
                   style="display: inline-block; background: #DC2626; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
                    Update Payment Method
                </a>
            </div>
            <p style="color: #9CA3AF; font-size: 13px; line-height: 1.5;">
                If you believe this is a mistake, please contact us at
                <a href="mailto:billing@rankspy.app" style="color: #4F46E5;">billing@rankspy.app</a>.
            </p>
        """),
    )
