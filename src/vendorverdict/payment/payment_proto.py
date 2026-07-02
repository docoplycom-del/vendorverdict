from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

from vendorverdict.payment.fet_verifier import verify_fet_payment_to_agent
from vendorverdict.payment.premium_report import render_payment_offer, render_premium_dossier
from vendorverdict.payment.pricing import PREMIUM_VENDOR_DOSSIER

try:  # Keep CLI/unit tests import-safe even without uAgents installed.
    from uagents import Context, Protocol
    from uagents_core.contrib.protocols.chat import ChatMessage, EndSessionContent, TextContent
    from uagents_core.contrib.protocols.payment import (
        CancelPayment,
        CommitPayment,
        CompletePayment,
        Funds,
        RejectPayment,
        RequestPayment,
        payment_protocol_spec,
    )
except Exception:  # pragma: no cover - exercised only in the Agentverse runtime
    Context = object  # type: ignore[assignment]
    Protocol = None  # type: ignore[assignment]
    ChatMessage = None  # type: ignore[assignment]
    TextContent = None  # type: ignore[assignment]
    EndSessionContent = None  # type: ignore[assignment]
    CancelPayment = CommitPayment = CompletePayment = Funds = RejectPayment = RequestPayment = None  # type: ignore[assignment]
    payment_protocol_spec = None  # type: ignore[assignment]


def payment_protocol_available() -> bool:
    return Protocol is not None and payment_protocol_spec is not None


payment_protocol = Protocol(spec=payment_protocol_spec, role="seller") if payment_protocol_available() else None
_agent_wallet = None


def set_agent_wallet(wallet) -> None:
    global _agent_wallet
    _agent_wallet = wallet


def payment_enabled() -> bool:
    return os.getenv("VENDORVERDICT_PAYMENT_ENABLED", "1").lower() in {"1", "true", "yes", "on"}


def _payment_storage_key(sender: str, reference: str, suffix: str) -> str:
    return f"payment:{sender}:{reference}:{suffix}"


def _chat_response(text: str):
    return ChatMessage(
        timestamp=datetime.now(UTC),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text), EndSessionContent(type="end-session")],
    )


def _agent_recipient() -> str:
    if _agent_wallet is not None:
        try:
            return str(_agent_wallet.address())
        except Exception:
            pass
    return os.getenv("VENDORVERDICT_PAYMENT_RECIPIENT", "fetch1-demo-recipient-set-agent-wallet")


async def request_premium_payment(ctx: Context, sender: str, prompt: str) -> str:
    """Send a Payment Protocol request for the Premium Vendor Dossier."""

    reference = str(uuid4())
    amount = os.getenv("VENDORVERDICT_PREMIUM_PRICE_FET", PREMIUM_VENDOR_DOSSIER.price_fet)

    ctx.storage.set(_payment_storage_key(sender, reference, "prompt"), prompt)
    ctx.storage.set(_payment_storage_key(sender, reference, "sku"), PREMIUM_VENDOR_DOSSIER.sku)
    ctx.storage.set(_payment_storage_key(sender, "latest", "reference"), reference)

    funds = Funds(currency="FET", amount=amount, payment_method="fet_direct")
    request = RequestPayment(
        accepted_funds=[funds],
        recipient=_agent_recipient(),
        deadline_seconds=300,
        reference=reference,
        description=PREMIUM_VENDOR_DOSSIER.description,
        metadata={
            "product": PREMIUM_VENDOR_DOSSIER.sku,
            "agent": "vendorverdict",
            "mode": "premium_dossier",
            "network": "stable-testnet" if os.getenv("FET_USE_TESTNET", "true").lower() in {"1", "true", "yes", "on"} else "mainnet",
        },
    )
    await ctx.send(sender, request)
    return reference


if payment_protocol is not None:

    @payment_protocol.on_message(CommitPayment)
    async def handle_commit_payment(ctx: Context, sender: str, msg: CommitPayment) -> None:
        reference = msg.reference or ctx.storage.get(_payment_storage_key(sender, "latest", "reference"))
        if not reference:
            await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id, reason="Missing payment reference."))
            return

        prompt = ctx.storage.get(_payment_storage_key(sender, reference, "prompt"))
        if not prompt:
            await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id, reason="Could not find the premium report prompt."))
            return

        metadata = msg.metadata or {}
        buyer_wallet = None
        if isinstance(metadata, dict):
            buyer_wallet = metadata.get("buyer_fet_wallet") or metadata.get("buyer_fet_address") or metadata.get("sender")

        verified = verify_fet_payment_to_agent(
            transaction_id=msg.transaction_id,
            expected_amount_fet=str(msg.funds.amount),
            sender_fet_address=buyer_wallet,
            recipient_wallet=_agent_wallet,
            logger=ctx.logger,
        )
        if not verified:
            await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id, reason="Payment verification failed."))
            return

        ctx.storage.set(_payment_storage_key(sender, reference, "verified"), "true")
        ctx.storage.set(_payment_storage_key(sender, reference, "tx"), msg.transaction_id)
        await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))
        await ctx.send(sender, _chat_response("Payment verified. Generating your Premium Vendor Dossier now..."))
        report = render_premium_dossier(prompt, use_live_evidence=True)
        await ctx.send(sender, _chat_response(report))

    @payment_protocol.on_message(RejectPayment)
    async def handle_reject_payment(ctx: Context, sender: str, msg: RejectPayment) -> None:
        reason = f" Reason: {msg.reason}" if msg.reason else ""
        await ctx.send(sender, _chat_response(f"Payment was declined.{reason} The free VendorVerdict review remains available."))
