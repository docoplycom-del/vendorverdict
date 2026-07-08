from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable, Mapping

import requests

from vendorverdict.proposals import ProposalRecord


STRIPE_CHECKOUT_ENDPOINT = "https://api.stripe.com/v1/checkout/sessions"


@dataclass(frozen=True)
class StripeCheckoutSettings:
    """Configuration for optional Stripe Checkout session creation.

    Secret keys deliberately come only from environment variables. Non-secret defaults such as
    currency and success/cancel URLs can be set in the production env file. If this is not configured,
    VendorVerdict keeps the existing manual payment-link workflow.
    """

    enabled: bool
    secret_key: str
    currency: str
    success_url: str
    cancel_url: str
    timeout_seconds: int

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.secret_key)

    @property
    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.enabled:
            missing.append("VENDORVERDICT_STRIPE_CHECKOUT_ENABLED")
        if not self.secret_key:
            missing.append("VENDORVERDICT_STRIPE_SECRET_KEY")
        return missing


@dataclass(frozen=True)
class StripeCheckoutResult:
    created: bool
    url: str = ""
    session_id: str = ""
    detail: str = ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


def get_stripe_checkout_settings() -> StripeCheckoutSettings:
    return StripeCheckoutSettings(
        enabled=_env_bool("VENDORVERDICT_STRIPE_CHECKOUT_ENABLED", default=False),
        secret_key=os.getenv("VENDORVERDICT_STRIPE_SECRET_KEY", "").strip(),
        currency=_currency(os.getenv("VENDORVERDICT_STRIPE_CURRENCY", "gbp")),
        success_url=os.getenv("VENDORVERDICT_STRIPE_SUCCESS_URL", "").strip(),
        cancel_url=os.getenv("VENDORVERDICT_STRIPE_CANCEL_URL", "").strip(),
        timeout_seconds=_int_env("VENDORVERDICT_STRIPE_TIMEOUT_SECONDS", default=15, minimum=3, maximum=60),
    )


def amount_to_minor_units(amount: str) -> int:
    """Convert a human amount such as '1500' or '1,500.00' to minor units.

    The dashboard labels this as an amount in the configured currency. For GBP this returns pence.
    """

    cleaned = (amount or "").strip().replace(",", "").replace("£", "").replace("$", "").replace("€", "")
    if not cleaned:
        raise ValueError("Enter a payment amount.")
    try:
        decimal = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError("Enter a valid payment amount.") from exc
    if decimal <= 0:
        raise ValueError("Payment amount must be greater than zero.")
    minor = int((decimal * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if minor < 50:
        raise ValueError("Payment amount is too small for checkout.")
    return minor


def amount_from_price_text(price: str, *, fallback: str = "1500") -> str:
    """Best-effort default for the checkout form from proposal price text.

    Examples: 'From £1,000/month after pilot' -> '1000'. Returns fallback when there is no
    obvious number, because many proposals use 'Custom'.
    """

    digits: list[str] = []
    started = False
    for char in price or "":
        if char.isdigit() or (started and char in {",", "."}):
            digits.append(char)
            started = True
        elif started:
            break
    candidate = "".join(digits).replace(",", "").strip(".")
    return candidate or fallback


def create_stripe_checkout_session(
    proposal: ProposalRecord,
    *,
    amount: str,
    settings: StripeCheckoutSettings | None = None,
    success_url: str = "",
    cancel_url: str = "",
    post: Callable[..., Any] = requests.post,
) -> StripeCheckoutResult:
    resolved = settings or get_stripe_checkout_settings()
    if not resolved.is_configured:
        return StripeCheckoutResult(created=False, detail="Stripe Checkout is not configured.")

    try:
        amount_minor = amount_to_minor_units(amount)
    except ValueError as exc:
        return StripeCheckoutResult(created=False, detail=str(exc))

    resolved_success = success_url or resolved.success_url
    resolved_cancel = cancel_url or resolved.cancel_url
    if not resolved_success or not resolved_cancel:
        return StripeCheckoutResult(created=False, detail="Stripe success and cancel URLs are required.")

    product_name = f"VendorVerdict {proposal.package_label}"
    description = _checkout_description(proposal)
    payload: dict[str, str | int] = {
        "mode": "payment",
        "payment_method_types[]": "card",
        "success_url": resolved_success,
        "cancel_url": resolved_cancel,
        "client_reference_id": proposal.proposal_id,
        "customer_email": proposal.contact_email,
        "line_items[0][quantity]": 1,
        "line_items[0][price_data][currency]": resolved.currency,
        "line_items[0][price_data][unit_amount]": amount_minor,
        "line_items[0][price_data][product_data][name]": product_name,
        "line_items[0][price_data][product_data][description]": description,
        "metadata[proposal_id]": proposal.proposal_id,
        "metadata[company]": proposal.company,
        "metadata[pilot_id]": proposal.pilot_id,
    }
    headers = {"Authorization": f"Bearer {resolved.secret_key}"}

    try:
        response = post(STRIPE_CHECKOUT_ENDPOINT, data=payload, headers=headers, timeout=resolved.timeout_seconds)
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        data = response.json() if hasattr(response, "json") else {}
    except Exception as exc:  # pragma: no cover - network errors are tested through fake responses
        return StripeCheckoutResult(created=False, detail=f"Stripe Checkout request failed: {exc}")

    checkout_url = str(data.get("url", "") or "").strip()
    session_id = str(data.get("id", "") or "").strip()
    if not checkout_url or not session_id:
        return StripeCheckoutResult(created=False, detail="Stripe did not return a checkout URL and session ID.")
    return StripeCheckoutResult(created=True, url=checkout_url, session_id=session_id, detail="Stripe Checkout session created.")


def _checkout_description(proposal: ProposalRecord) -> str:
    company = proposal.company or "customer"
    return f"VendorVerdict proposal payment for {company}. {proposal.proposed_price or proposal.package_label}"[:500]


def _currency(value: str) -> str:
    cleaned = (value or "gbp").strip().lower()
    return cleaned if cleaned.isalpha() and len(cleaned) == 3 else "gbp"


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))
