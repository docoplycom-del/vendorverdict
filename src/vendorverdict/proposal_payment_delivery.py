from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote

from vendorverdict.proposal_email_delivery import (
    ProposalEmailSendResult,
    ProposalEmailSettings,
    get_proposal_email_settings,
)
from vendorverdict.proposals import ProposalEmail, ProposalRecord


@dataclass(frozen=True)
class PaymentEmailPair:
    """Customer-ready payment request and reminder drafts for a proposal."""

    request: ProposalEmail
    reminder: ProposalEmail

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


def build_payment_request_email(proposal: ProposalRecord, *, share_url: str = "") -> ProposalEmail:
    """Create a payment request email for a proposal.

    This email is deliberately separate from the commercial proposal email. It is used after the
    proposal terms are agreed or when the user wants to send a payment/checkout link for the paid
    pilot or rollout. It includes only customer-facing commercial details.
    """

    greeting_name = proposal.contact_name.split()[0] if proposal.contact_name else "there"
    subject = f"VendorVerdict payment details for {proposal.company or 'your team'}"
    body = (
        f"Hi {greeting_name},\n\n"
        f"Following the VendorVerdict proposal for {proposal.company or 'your team'}, I have prepared the payment details below.\n\n"
        f"Package: {proposal.package_label}\n"
        f"Commercial starting point: {proposal.proposed_price or 'To be agreed'}\n"
        f"Billing: {proposal.billing or 'To be agreed'}\n\n"
        f"{_payment_details_block(proposal)}"
        f"{_share_link_block(share_url)}"
        "Once payment is complete, I will confirm receipt and we can continue with the next VendorVerdict delivery step.\n\n"
        "Best,\n"
        "Vladimir"
    )
    return ProposalEmail(subject=subject, body=body)


def build_payment_reminder_email(proposal: ProposalRecord, *, share_url: str = "") -> ProposalEmail:
    """Create a polite payment reminder email for a proposal."""

    greeting_name = proposal.contact_name.split()[0] if proposal.contact_name else "there"
    subject = f"Reminder: VendorVerdict payment for {proposal.company or 'your team'}"
    due_sentence = f" due on {proposal.payment_due}" if proposal.payment_due else ""
    body = (
        f"Hi {greeting_name},\n\n"
        f"A quick reminder about the VendorVerdict payment{due_sentence}.\n\n"
        f"Package: {proposal.package_label}\n"
        f"Commercial starting point: {proposal.proposed_price or 'To be agreed'}\n"
        f"{_payment_details_block(proposal)}"
        f"{_share_link_block(share_url)}"
        "Could you confirm whether this has been processed, or whether anything else is needed from me?\n\n"
        "Best,\n"
        "Vladimir"
    )
    return ProposalEmail(subject=subject, body=body)


def build_payment_email_pair(proposal: ProposalRecord, *, share_url: str = "") -> PaymentEmailPair:
    return PaymentEmailPair(
        request=build_payment_request_email(proposal, share_url=share_url),
        reminder=build_payment_reminder_email(proposal, share_url=share_url),
    )


def build_payment_mailto(proposal: ProposalRecord, *, reminder: bool = False, share_url: str = "") -> str:
    email = build_payment_reminder_email(proposal, share_url=share_url) if reminder else build_payment_request_email(proposal, share_url=share_url)
    recipient = quote((proposal.contact_email or "").strip())
    return f"mailto:{recipient}?subject={quote(email.subject)}&body={quote(email.body)}"


def send_payment_email(
    proposal: ProposalRecord,
    *,
    reminder: bool = False,
    share_url: str = "",
    settings: ProposalEmailSettings | None = None,
) -> ProposalEmailSendResult:
    """Send payment request/reminder email through the existing SMTP configuration.

    Persistence is intentionally left to the caller. The dashboard route only marks invoice/payment
    link as sent after this function returns sent=True.
    """

    resolved = settings or get_proposal_email_settings()
    if not resolved.is_configured:
        return ProposalEmailSendResult(sent=False, detail="SMTP email sending is not configured.")

    recipient = (proposal.contact_email or "").strip()
    if "@" not in recipient:
        return ProposalEmailSendResult(sent=False, detail="Proposal contact email is missing or invalid.")

    email = build_payment_reminder_email(proposal, share_url=share_url) if reminder else build_payment_request_email(proposal, share_url=share_url)
    message = EmailMessage()
    message["Subject"] = email.subject
    message["From"] = _format_from_header(resolved.from_name, resolved.from_email)
    message["To"] = recipient
    message.set_content(email.body)

    try:
        with smtplib.SMTP(resolved.host, resolved.port, timeout=resolved.timeout_seconds) as smtp:
            if resolved.starttls:
                smtp.starttls(context=ssl.create_default_context())
            if resolved.username:
                smtp.login(resolved.username, resolved.password)
            response = smtp.send_message(message)
    except Exception as exc:  # pragma: no cover - exact SMTP exceptions vary by provider
        return ProposalEmailSendResult(sent=False, detail=f"SMTP send failed: {exc.__class__.__name__}")

    if response:
        return ProposalEmailSendResult(sent=False, detail="SMTP server rejected one or more recipients.")
    return ProposalEmailSendResult(sent=True, detail="Payment email sent.", message_id=str(message.get("Message-ID") or ""))


def _payment_details_block(proposal: ProposalRecord) -> str:
    lines: list[str] = ["Payment details:"]
    if proposal.invoice_reference:
        lines.append(f"Invoice / payment reference: {proposal.invoice_reference}")
    if proposal.payment_due:
        lines.append(f"Payment due: {proposal.payment_due}")
    if proposal.payment_url:
        lines.append(f"Payment link: {proposal.payment_url}")
    if len(lines) == 1:
        lines.append("Payment link or invoice details to follow.")
    return "\n".join(lines) + "\n\n"


def _share_link_block(share_url: str) -> str:
    clean = (share_url or "").strip()
    if not clean:
        return ""
    return f"Proposal link: {clean}\n\n"


def _format_from_header(name: str, email: str) -> str:
    clean_name = (name or "VendorVerdict").replace("\n", " ").replace("\r", " ").strip()
    clean_email = (email or "").replace("\n", "").replace("\r", "").strip()
    return f"{clean_name} <{clean_email}>" if clean_name else clean_email
