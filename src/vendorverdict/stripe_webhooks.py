from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping

from vendorverdict.proposals import ProposalStore


@dataclass(frozen=True)
class StripeWebhookSettings:
    """Configuration for optional Stripe webhook reconciliation.

    The signing secret stays in environment variables. When enabled, VendorVerdict can receive
    Stripe Checkout events and mark the matching proposal as paid after Stripe confirms payment.
    """

    enabled: bool
    webhook_secret: str
    tolerance_seconds: int

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.webhook_secret)

    @property
    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.enabled:
            missing.append("VENDORVERDICT_STRIPE_WEBHOOK_ENABLED")
        if not self.webhook_secret:
            missing.append("VENDORVERDICT_STRIPE_WEBHOOK_SECRET")
        return missing


@dataclass(frozen=True)
class StripeWebhookResult:
    processed: bool
    proposal_id: str = ""
    event_type: str = ""
    event_id: str = ""
    detail: str = ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


def get_stripe_webhook_settings() -> StripeWebhookSettings:
    return StripeWebhookSettings(
        enabled=_env_bool("VENDORVERDICT_STRIPE_WEBHOOK_ENABLED", default=False),
        webhook_secret=os.getenv("VENDORVERDICT_STRIPE_WEBHOOK_SECRET", "").strip(),
        tolerance_seconds=_int_env("VENDORVERDICT_STRIPE_WEBHOOK_TOLERANCE_SECONDS", default=300, minimum=30, maximum=3600),
    )


def verify_stripe_signature(
    payload: bytes,
    signature_header: str,
    secret: str,
    *,
    tolerance_seconds: int = 300,
    now: int | None = None,
) -> bool:
    """Verify the Stripe-Signature header using HMAC SHA-256.

    Stripe signs the exact payload as: HMAC_SHA256("<timestamp>.<payload>", webhook_secret).
    The function accepts any matching v1 signature in the header and rejects stale timestamps.
    """

    if not payload or not signature_header or not secret:
        return False
    parts = _parse_signature_header(signature_header)
    timestamp_values = parts.get("t", [])
    signatures = parts.get("v1", [])
    if not timestamp_values or not signatures:
        return False
    try:
        timestamp = int(timestamp_values[0])
    except ValueError:
        return False

    current = int(time.time()) if now is None else now
    if tolerance_seconds > 0 and abs(current - timestamp) > tolerance_seconds:
        return False

    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, candidate) for candidate in signatures)


def load_stripe_event(payload: bytes) -> dict[str, Any]:
    try:
        decoded = payload.decode("utf-8")
        data = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid Stripe webhook JSON payload.") from exc
    if not isinstance(data, dict):
        raise ValueError("Invalid Stripe webhook event structure.")
    return data


def process_stripe_webhook_event(event: Mapping[str, Any], store: ProposalStore) -> StripeWebhookResult:
    event_id = str(event.get("id") or "").strip()
    event_type = str(event.get("type") or "").strip()
    obj = _event_object(event)
    proposal_id = _proposal_id_from_object(obj)
    reference = str(obj.get("id") or event_id or "").strip()

    if not event_type:
        return StripeWebhookResult(processed=False, event_id=event_id, detail="Stripe event type missing.")
    if not proposal_id:
        store.add_payment_event(
            proposal_id="",
            event_id=event_id,
            event_type=event_type,
            status="ignored",
            detail="No proposal_id found in Stripe metadata or client_reference_id.",
        )
        return StripeWebhookResult(processed=False, event_type=event_type, event_id=event_id, detail="No proposal_id found.")

    proposal = store.get_proposal(proposal_id)
    if proposal is None:
        store.add_payment_event(
            proposal_id=proposal_id,
            event_id=event_id,
            event_type=event_type,
            status="not_found",
            detail="Proposal referenced by Stripe event was not found.",
        )
        return StripeWebhookResult(
            processed=False,
            proposal_id=proposal_id,
            event_type=event_type,
            event_id=event_id,
            detail="Proposal not found.",
        )

    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded", "payment_intent.succeeded"}:
        if event_type == "checkout.session.completed" and str(obj.get("payment_status") or "").lower() not in {"", "paid"}:
            store.add_payment_event(
                proposal_id=proposal_id,
                event_id=event_id,
                event_type=event_type,
                status="received",
                detail="Checkout session completed but payment_status was not paid yet.",
            )
            return StripeWebhookResult(
                processed=False,
                proposal_id=proposal_id,
                event_type=event_type,
                event_id=event_id,
                detail="Checkout completed but not paid yet.",
            )
        store.mark_paid(proposal_id, invoice_reference=reference)
        store.add_payment_event(
            proposal_id=proposal_id,
            event_id=event_id,
            event_type=event_type,
            status="paid",
            detail="Stripe confirmed payment and proposal was marked paid.",
        )
        return StripeWebhookResult(
            processed=True,
            proposal_id=proposal_id,
            event_type=event_type,
            event_id=event_id,
            detail="Proposal marked paid.",
        )

    if event_type in {"checkout.session.expired", "payment_intent.payment_failed"}:
        store.add_payment_event(
            proposal_id=proposal_id,
            event_id=event_id,
            event_type=event_type,
            status="attention",
            detail="Stripe payment did not complete; follow up or create a new payment link.",
        )
        return StripeWebhookResult(
            processed=True,
            proposal_id=proposal_id,
            event_type=event_type,
            event_id=event_id,
            detail="Payment event recorded for follow-up.",
        )

    store.add_payment_event(
        proposal_id=proposal_id,
        event_id=event_id,
        event_type=event_type,
        status="ignored",
        detail="Stripe event type does not require VendorVerdict action.",
    )
    return StripeWebhookResult(
        processed=False,
        proposal_id=proposal_id,
        event_type=event_type,
        event_id=event_id,
        detail="Event ignored.",
    )


def _event_object(event: Mapping[str, Any]) -> Mapping[str, Any]:
    data = event.get("data")
    if isinstance(data, Mapping):
        obj = data.get("object")
        if isinstance(obj, Mapping):
            return obj
    return {}


def _proposal_id_from_object(obj: Mapping[str, Any]) -> str:
    metadata = obj.get("metadata")
    if isinstance(metadata, Mapping):
        proposal_id = str(metadata.get("proposal_id") or "").strip()
        if proposal_id:
            return proposal_id
    return str(obj.get("client_reference_id") or "").strip()


def _parse_signature_header(header: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key and value:
            result.setdefault(key, []).append(value)
    return result


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
