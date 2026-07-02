from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from vendorverdict.verdict import render_response

load_dotenv()

AGENT_NAME = os.getenv("AGENT_NAME", "vendorverdict")
AGENT_SEED = os.getenv("AGENT_SEED", "vendorverdict-dev-seed-change-me-before-demo")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))

agent = Agent(
    name=AGENT_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=True,
    publish_agent_details=True,
)

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


@agent.on_event("startup")
async def startup(ctx: Context) -> None:
    ctx.logger.info(f"VendorVerdict started. Agent name={agent.name} address={agent.address}")


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id),
    )

    text_chunks: list[str] = []
    for item in msg.content:
        if isinstance(item, TextContent):
            text_chunks.append(item.text)
    user_text = "\n".join(text_chunks).strip()

    try:
        response = render_response(user_text)
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

if __name__ == "__main__":
    agent.run()
