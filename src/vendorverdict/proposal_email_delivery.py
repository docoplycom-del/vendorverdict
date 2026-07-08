from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from vendorverdict.proposals import ProposalEmail, ProposalRecord, build_proposal_email


@dataclass(frozen=True)
class ProposalEmailSettings:
    """Environment-backed SMTP settings for sending proposal emails.

    Secrets intentionally stay in the VM environment file rather than in the admin
    settings database. This keeps the dashboard useful for non-secret defaults
    while avoiding accidental secret exposure in backups or exported data.
    """

    enabled: bool = False
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = ""
    from_name: str = "VendorVerdict"
    starttls: bool = True
    timeout_seconds: int = 15

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.host and self.from_email)

    @property
    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.enabled:
            missing.append("VENDORVERDICT_EMAIL_SEND_ENABLED")
        if not self.host:
            missing.append("VENDORVERDICT_SMTP_HOST")
        if not self.from_email:
            missing.append("VENDORVERDICT_SMTP_FROM")
        return missing


@dataclass(frozen=True)
class ProposalEmailSendResult:
    sent: bool
    detail: str
    message_id: str = ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


def get_proposal_email_settings() -> ProposalEmailSettings:
    return ProposalEmailSettings(
        enabled=_env_bool("VENDORVERDICT_EMAIL_SEND_ENABLED", default=False),
        host=os.getenv("VENDORVERDICT_SMTP_HOST", "").strip(),
        port=_env_int("VENDORVERDICT_SMTP_PORT", default=587),
        username=os.getenv("VENDORVERDICT_SMTP_USERNAME", "").strip(),
        password=os.getenv("VENDORVERDICT_SMTP_PASSWORD", ""),
        from_email=os.getenv("VENDORVERDICT_SMTP_FROM", "").strip(),
        from_name=os.getenv("VENDORVERDICT_SMTP_FROM_NAME", "VendorVerdict").strip() or "VendorVerdict",
        starttls=_env_bool("VENDORVERDICT_SMTP_STARTTLS", default=True),
        timeout_seconds=_env_int("VENDORVERDICT_SMTP_TIMEOUT_SECONDS", default=15),
    )


def build_customer_proposal_email(
    proposal: ProposalRecord,
    *,
    share_url: str = "",
    include_attachment_note: bool = True,
) -> ProposalEmail:
    """Return a send-ready customer email for a commercial proposal.

    This reuses the existing proposal email draft and appends either the secure
    customer share link, a note about the attached PDF, or both.
    """

    base = build_proposal_email(proposal)
    additions: list[str] = []
    if share_url:
        additions.append(f"You can also view the proposal here: {share_url}")
    if include_attachment_note:
        additions.append("I have attached the customer proposal PDF for reference.")

    if not additions:
        return base

    body = base.body.rstrip() + "\n\n" + "\n".join(additions)
    return ProposalEmail(subject=base.subject, body=body)


def send_customer_proposal_email(
    proposal: ProposalRecord,
    *,
    pdf_path: str | Path | None = None,
    share_url: str = "",
    settings: ProposalEmailSettings | None = None,
) -> ProposalEmailSendResult:
    """Send a proposal email using SMTP.

    The function performs no persistence. Callers should mark the proposal as sent
    only after this returns sent=True.
    """

    resolved = settings or get_proposal_email_settings()
    if not resolved.is_configured:
        return ProposalEmailSendResult(
            sent=False,
            detail="Proposal email sending is not configured.",
        )

    recipient = (proposal.contact_email or "").strip()
    if "@" not in recipient:
        return ProposalEmailSendResult(sent=False, detail="Proposal contact email is missing or invalid.")

    attachment_path = Path(pdf_path) if pdf_path else None
    email = build_customer_proposal_email(
        proposal,
        share_url=share_url,
        include_attachment_note=attachment_path is not None,
    )
    message = EmailMessage()
    message["Subject"] = email.subject
    message["From"] = _format_from_header(resolved.from_name, resolved.from_email)
    message["To"] = recipient
    message.set_content(email.body)

    if attachment_path is not None and attachment_path.exists():
        message.add_attachment(
            attachment_path.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=attachment_path.name,
        )

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
    return ProposalEmailSendResult(sent=True, detail="Proposal email sent.", message_id=str(message.get("Message-ID") or ""))


def _format_from_header(name: str, email: str) -> str:
    clean_name = (name or "VendorVerdict").replace("\n", " ").replace("\r", " ").strip()
    clean_email = (email or "").replace("\n", "").replace("\r", "").strip()
    return f"{clean_name} <{clean_email}>" if clean_name else clean_email


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, *, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
