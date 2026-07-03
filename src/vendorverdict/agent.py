from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

from dotenv import load_dotenv
from uagents import Agent, Context, Model, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from vendorverdict.payment import render_payment_offer, render_upgrade_cta, wants_premium_report
from vendorverdict.payment.premium_report import render_premium_dossier
from vendorverdict.payment.payment_proto import (
    payment_enabled,
    payment_protocol,
    payment_protocol_available,
    request_premium_payment,
    set_agent_wallet,
)
from vendorverdict.verdict import render_response

load_dotenv()

AGENT_NAME = os.getenv("AGENT_NAME", "vendorverdict")
AGENT_SEED = os.getenv("AGENT_SEED", "vendorverdict-dev-seed-change-me-before-demo")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))

class HealthResponse(Model):
    status: str
    agent: str
    address: str


class InfoResponse(Model):
    name: str
    protocol: str
    status: str
    message: str


agent = Agent(
    name=AGENT_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=True,
    publish_agent_details=True,
)
set_agent_wallet(agent.wallet)

protocol = Protocol(spec=chat_protocol_spec)


def _chat_response(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(UTC),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=text),
            EndSessionContent(type="end-session"),
        ],
    )



@agent.on_rest_get("/health", HealthResponse)
async def health(ctx: Context) -> HealthResponse:
    return HealthResponse(status="ok", agent=agent.name, address=str(agent.address))


@agent.on_rest_get("/", InfoResponse)
async def root(ctx: Context) -> InfoResponse:
    return InfoResponse(
        name=agent.name,
        protocol="Agent Chat Protocol",
        status="running",
        message="VendorVerdict is live. Use Agentverse / ASI:One chat to interact with the agent.",
    )


@agent.on_event("startup")
async def startup(ctx: Context) -> None:
    ctx.logger.info(f"VendorVerdict started. Agent name={agent.name} address={agent.address}")


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(UTC), acknowledged_msg_id=msg.msg_id),
    )

    text_chunks: list[str] = []
    for item in msg.content:
        if isinstance(item, TextContent):
            text_chunks.append(item.text)
    user_text = "\n".join(text_chunks).strip()

    try:
        if wants_premium_report(user_text):
            base_prompt = ctx.storage.get(f"last_review_prompt:{sender}") or user_text

            if os.getenv("VENDORVERDICT_PAYMENT_DEMO_MODE", "1").lower() in {"1", "true", "yes"}:
                await ctx.send(
                    sender,
                    _chat_response(
                        "Demo Premium Vendor Dossier generated. "
                        "In production, this upgrade is designed to be gated by a 0.05 FET Fetch.ai Payment Protocol request.\n\n"
                        + render_premium_dossier(base_prompt)
                    ),
                )
                return

            if payment_enabled() and payment_protocol_available():
                reference = await request_premium_payment(ctx, sender, base_prompt)
                await ctx.send(sender, _chat_response(render_payment_offer(reference)))
                return

            await ctx.send(
                sender,
                _chat_response(
                    "Payment Protocol is not enabled in this runtime, but this is the paid product flow:\n\n"
                    + render_payment_offer()
                ),
            )
            return

        pending_key = f"pending_review_prompt:{sender}"
        pending_prompt = ctx.storage.get(pending_key) or ""

        effective_user_text = user_text

        # ASI:One sends clarification answers as separate messages.
        # If the previous turn was missing vendors/use case, combine the short follow-up
        # with the earlier partial request so the parser has the full context.
        if pending_prompt and user_text and len(user_text.split()) <= 12:
            effective_user_text = pending_prompt + "\nAdditional answer: " + user_text

        response = render_response(effective_user_text)

        if response.startswith("Which vendors") or response.startswith("What will"):
            ctx.storage.set(pending_key, effective_user_text)
        else:
            ctx.storage.set(pending_key, "")
            if effective_user_text:
                ctx.storage.set(f"last_review_prompt:{sender}", effective_user_text)
            response = response + "\n\n" + render_upgrade_cta()
    except Exception:
        ctx.logger.exception("VendorVerdict failed while building response")
        response = (
            "I hit an internal error while preparing the vendor review. "
            "Please try again with 2–5 vendor names and a clear use case."
        )

    await ctx.send(sender, _chat_response(response))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.info(f"Acknowledgement received from {sender}: {msg.acknowledged_msg_id}")


agent.include(protocol, publish_manifest=True)
if payment_protocol is not None:
    agent.include(payment_protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
