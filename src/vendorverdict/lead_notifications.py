from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol

import requests


class LeadLike(Protocol):
    lead_id: str
    created_at: str
    name: str
    email: str
    company: str
    use_case: str
    vendors: str
    message: str
    source: str
    status: str


@dataclass(frozen=True)
class LeadNotificationSettings:
    enabled: bool
    name: str
    webhook_url: str
    webhook_format: str
    email_to: str
    email_from: str
    timeout_seconds: float


@dataclass(frozen=True)
class LeadNotificationResult:
    status: str
    message: str

    @property
    def sent(self) -> bool:
        return self.status == "sent"


def get_lead_notification_settings() -> LeadNotificationSettings:
    """Read lead-notification settings from environment variables.

    Lead notifications can use their own webhook settings, or fall back to the
    production-monitor alert webhook already configured for the VM.
    """

    webhook_url = os.getenv("VENDORVERDICT_LEAD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        webhook_url = os.getenv("VENDORVERDICT_ALERT_WEBHOOK_URL", "").strip()

    webhook_format = os.getenv("VENDORVERDICT_LEAD_WEBHOOK_FORMAT", "").strip()
    if not webhook_format:
        webhook_format = os.getenv("VENDORVERDICT_ALERT_WEBHOOK_FORMAT", "generic").strip()

    enabled = _env_bool("VENDORVERDICT_LEAD_NOTIFY_ENABLED", default=False)
    timeout = _env_float("VENDORVERDICT_LEAD_NOTIFY_TIMEOUT_SECONDS", default=10.0)

    return LeadNotificationSettings(
        enabled=enabled,
        name=os.getenv("VENDORVERDICT_LEAD_NOTIFY_NAME", "VendorVerdict lead capture").strip()
        or "VendorVerdict lead capture",
        webhook_url=webhook_url,
        webhook_format=(webhook_format or "generic").lower(),
        email_to=os.getenv("VENDORVERDICT_LEAD_EMAIL_TO", "").strip(),
        email_from=os.getenv("VENDORVERDICT_LEAD_EMAIL_FROM", "vendorverdict@docoply.com").strip(),
        timeout_seconds=timeout,
    )


def send_lead_notification(
    lead: LeadLike,
    *,
    app_base_url: str = "",
    settings: LeadNotificationSettings | None = None,
) -> LeadNotificationResult:
    """Send a best-effort notification for a new lead.

    The lead is always saved before this runs. Failures are returned to the caller
    so they can be recorded, but they should not block the public form.
    """

    settings = settings or get_lead_notification_settings()
    if not settings.enabled:
        return LeadNotificationResult(status="skipped", message="Lead notifications are disabled.")
    if not settings.webhook_url and not settings.email_to:
        return LeadNotificationResult(status="skipped", message="No lead notification destination is configured.")

    subject = f"New VendorVerdict pilot request: {lead.name}"
    body = format_lead_notification(lead, app_base_url=app_base_url, settings=settings)
    results: list[str] = []
    failures: list[str] = []

    if settings.webhook_url:
        try:
            _send_webhook(settings.webhook_url, body, settings=settings)
            results.append("webhook")
        except Exception as exc:  # pragma: no cover - exact requests exceptions vary by platform.
            failures.append(f"webhook failed: {exc}")

    if settings.email_to:
        try:
            _send_email(settings.email_to, subject, body, from_address=settings.email_from)
            results.append("email")
        except Exception as exc:  # pragma: no cover - local mail availability varies by VM.
            failures.append(f"email failed: {exc}")

    if results:
        suffix = f"; {'; '.join(failures)}" if failures else ""
        return LeadNotificationResult(status="sent", message=f"Lead notification sent via {', '.join(results)}{suffix}.")
    return LeadNotificationResult(status="failed", message="; ".join(failures) or "Notification failed.")


def format_lead_notification(
    lead: LeadLike,
    *,
    app_base_url: str = "",
    settings: LeadNotificationSettings | None = None,
) -> str:
    settings = settings or get_lead_notification_settings()
    admin_url = ""
    if app_base_url:
        admin_url = f"{app_base_url.rstrip('/')}/dashboard/leads"

    lines = [
        f"{settings.name}: new pilot request",
        "",
        f"Name: {lead.name}",
        f"Email: {lead.email}",
        f"Company: {lead.company or '—'}",
        f"Vendors: {lead.vendors or '—'}",
        f"Use case: {lead.use_case or '—'}",
        f"Source: {lead.source or 'demo'}",
        f"Lead ID: {lead.lead_id}",
    ]
    if lead.message:
        lines.extend(["", "Message:", lead.message])
    if admin_url:
        lines.extend(["", f"Open lead inbox: {admin_url}"])
    return "\n".join(lines)


def _send_webhook(url: str, body: str, *, settings: LeadNotificationSettings) -> None:
    payload = _webhook_payload(body, settings=settings)
    response = requests.post(url, json=payload, timeout=settings.timeout_seconds)
    response.raise_for_status()


def _webhook_payload(body: str, *, settings: LeadNotificationSettings) -> dict[str, object]:
    if settings.webhook_format == "discord":
        return {"content": body[:1900]}
    # Slack-compatible and most generic webhooks accept a text field.
    return {"text": body}


def _send_email(to_address: str, subject: str, body: str, *, from_address: str = "") -> None:
    mail_bin = shutil.which("mail") or shutil.which("mailx")
    if mail_bin:
        cmd = [mail_bin, "-s", subject]
        if from_address:
            cmd.extend(["-r", from_address])
        cmd.append(to_address)
        subprocess.run(cmd, input=body, text=True, check=True, timeout=10)
        return

    sendmail_bin = shutil.which("sendmail")
    if sendmail_bin:
        message = _format_sendmail_message(to_address, subject, body, from_address=from_address)
        subprocess.run([sendmail_bin, "-t"], input=message, text=True, check=True, timeout=10)
        return

    raise RuntimeError("No local mail command found. Configure a webhook or install mail/sendmail.")


def _format_sendmail_message(to_address: str, subject: str, body: str, *, from_address: str = "") -> str:
    headers = [f"To: {to_address}", f"Subject: {subject}"]
    if from_address:
        headers.append(f"From: {from_address}")
    return "\n".join(headers) + "\n\n" + body


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, *, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default
