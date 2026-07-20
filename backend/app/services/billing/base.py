"""Gateway-agnostic billing interface.

The application talks to a `BillingProvider`, never to a specific payment
gateway's SDK. One implementation exists per gateway (Stripe today; Airwallex
next). Swapping gateways is therefore: implement this interface + flip
`settings.payment_provider` — no changes to routers or business logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session


class BillingProvider(ABC):
    """Contract every payment gateway implementation must satisfy."""

    #: short lowercase identifier stored in `subscriptions.provider`
    name: str = "base"

    @abstractmethod
    def is_configured(self) -> bool:
        """True when the gateway has the credentials it needs to operate."""

    @abstractmethod
    def publishable_key(self) -> str:
        """Client-safe key the frontend needs (may be '' if not applicable)."""

    @abstractmethod
    def create_checkout(
        self,
        *,
        db: Session,
        workspace_id: int,
        plan_code: str,
        customer_email: str,
        customer_name: Optional[str],
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Return a hosted checkout URL for `plan_code`.

        Raises `ValueError` for caller-fixable problems (unknown plan, missing
        subscription record) and lets gateway errors propagate.
        """

    @abstractmethod
    def create_billing_portal(
        self, *, db: Session, workspace_id: int, return_url: str
    ) -> str:
        """Return a customer billing-management portal URL."""

    @abstractmethod
    def cancel_subscription(self, provider_subscription_id: str) -> None:
        """Cancel the subscription at the gateway (used on account deletion)."""

    @abstractmethod
    def verify_webhook(self, *, payload: bytes, headers: Mapping[str, str]) -> Any:
        """Verify the signature and return the parsed provider event.

        Must raise if the signature is invalid.
        """

    @abstractmethod
    def handle_webhook_event(self, event: Any, db: Session) -> None:
        """Apply a verified webhook event to local subscription state."""
