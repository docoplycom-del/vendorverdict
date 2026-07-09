from __future__ import annotations

import os
import smtplib
import sqlite3
import ssl
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote

from vendorverdict.operator_briefing import BriefingSnapshot, render_operator_briefing_markdown
from vendorverdict.proposal_email_delivery import ProposalEmailSettings, get_proposal_email_settings
from vendorverdict.storage import default_db_path


@dataclass(frozen=True)
class BriefingEmail:
    subject: str
    body: str
    recipient: str

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @property
    def mailto_url(self) -> str:
        return f"mailto:{quote(self.recipient)}?subject={quote(self.subject)}&body={quote(self.body)}"


@dataclass(frozen=True)
class BriefingEmailResult:
    sent: bool
    detail: str
    message_id: str = ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class BriefingDeliveryRecord:
    delivery_id: str
    created_at: str
    status: str
    recipient: str
    subject: str
    detail: str
    action_count: int
    urgent_count: int

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class BriefingEmailSettingsSummary:
    enabled: bool
    smtp_configured: bool
    recipient: str
    missing_fields: tuple[str, ...]

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


class BriefingDeliveryStore:
    """SQLite-backed history of operator briefing delivery attempts."""

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        self.db_path = os.fspath(db_path or default_db_path())
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._ensure_schema()

    def record_delivery(
        self,
        *,
        status: str,
        recipient: str,
        subject: str,
        detail: str,
        action_count: int,
        urgent_count: int,
    ) -> str:
        delivery_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO operator_briefing_deliveries (
                    delivery_id, created_at, status, recipient, subject, detail, action_count, urgent_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delivery_id,
                    created_at,
                    _clean_status(status),
                    recipient.strip(),
                    subject.strip(),
                    detail.strip(),
                    int(action_count),
                    int(urgent_count),
                ),
            )
            conn.commit()
        return delivery_id

    def list_deliveries(self, *, limit: int = 20) -> list[BriefingDeliveryRecord]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT delivery_id, created_at, status, recipient, subject, detail, action_count, urgent_count
                FROM operator_briefing_deliveries
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(int(limit), 200)),),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operator_briefing_deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    recipient TEXT NOT NULL DEFAULT '',
                    subject TEXT NOT NULL DEFAULT '',
                    detail TEXT NOT NULL DEFAULT '',
                    action_count INTEGER NOT NULL DEFAULT 0,
                    urgent_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> BriefingDeliveryRecord:
        return BriefingDeliveryRecord(
            delivery_id=str(row["delivery_id"]),
            created_at=str(row["created_at"]),
            status=str(row["status"]),
            recipient=str(row["recipient"] or ""),
            subject=str(row["subject"] or ""),
            detail=str(row["detail"] or ""),
            action_count=int(row["action_count"] or 0),
            urgent_count=int(row["urgent_count"] or 0),
        )


def briefing_email_enabled() -> bool:
    return _env_bool("VENDORVERDICT_BRIEFING_EMAIL_ENABLED", default=False)


def resolve_briefing_recipient(*, operator_email: str = "") -> str:
    return (os.getenv("VENDORVERDICT_BRIEFING_EMAIL_TO", "").strip() or (operator_email or "").strip())


def briefing_email_summary(*, operator_email: str = "", smtp_settings: ProposalEmailSettings | None = None) -> BriefingEmailSettingsSummary:
    settings = smtp_settings or get_proposal_email_settings()
    recipient = resolve_briefing_recipient(operator_email=operator_email)
    missing: list[str] = []
    if not briefing_email_enabled():
        missing.append("VENDORVERDICT_BRIEFING_EMAIL_ENABLED")
    missing.extend(settings.missing_fields)
    if not recipient:
        missing.append("VENDORVERDICT_BRIEFING_EMAIL_TO or operator_email setting")
    return BriefingEmailSettingsSummary(
        enabled=briefing_email_enabled(),
        smtp_configured=settings.is_configured,
        recipient=recipient,
        missing_fields=tuple(dict.fromkeys(missing)),
    )


def build_operator_briefing_email(snapshot: BriefingSnapshot, *, recipient: str, public_url: str = "") -> BriefingEmail:
    subject = _subject(snapshot)
    lines = [
        f"{snapshot.headline}",
        "",
        f"Health: {snapshot.health_label}",
        f"Urgent actions: {snapshot.urgent_count}",
    ]
    if public_url:
        lines.extend(["", f"Open the live briefing: {public_url.rstrip('/')}/dashboard/briefing"])
    lines.extend(["", render_operator_briefing_markdown(snapshot).strip()])
    return BriefingEmail(subject=subject, body="\n".join(lines).strip(), recipient=recipient.strip())


def send_operator_briefing_email(
    snapshot: BriefingSnapshot,
    *,
    recipient: str,
    public_url: str = "",
    settings: ProposalEmailSettings | None = None,
) -> BriefingEmailResult:
    resolved = settings or get_proposal_email_settings()
    if not briefing_email_enabled():
        return BriefingEmailResult(sent=False, detail="Operator briefing email sending is not enabled.")
    if not resolved.is_configured:
        return BriefingEmailResult(sent=False, detail="SMTP email sending is not configured.")
    if "@" not in (recipient or ""):
        return BriefingEmailResult(sent=False, detail="Briefing recipient email is missing or invalid.")

    email = build_operator_briefing_email(snapshot, recipient=recipient, public_url=public_url)
    message = EmailMessage()
    message["Subject"] = email.subject
    message["From"] = _format_from_header(resolved.from_name, resolved.from_email)
    message["To"] = email.recipient
    message.set_content(email.body)

    try:
        with smtplib.SMTP(resolved.host, resolved.port, timeout=resolved.timeout_seconds) as smtp:
            if resolved.starttls:
                smtp.starttls(context=ssl.create_default_context())
            if resolved.username:
                smtp.login(resolved.username, resolved.password)
            response = smtp.send_message(message)
    except Exception as exc:  # pragma: no cover - exact SMTP/provider errors vary
        return BriefingEmailResult(sent=False, detail=f"SMTP send failed: {exc.__class__.__name__}")

    if response:
        return BriefingEmailResult(sent=False, detail="SMTP server rejected one or more recipients.")
    return BriefingEmailResult(sent=True, detail="Operator briefing email sent.", message_id=str(message.get("Message-ID") or ""))


def _subject(snapshot: BriefingSnapshot) -> str:
    date = snapshot.generated_date or datetime.now(UTC).date().isoformat()
    return f"VendorVerdict operator briefing — {snapshot.health_label} — {date}"


def _format_from_header(name: str, email: str) -> str:
    clean_name = (name or "VendorVerdict").replace("\n", " ").replace("\r", " ").strip()
    clean_email = (email or "").replace("\n", "").replace("\r", "").strip()
    return f"{clean_name} <{clean_email}>" if clean_name else clean_email


def _clean_status(status: str) -> str:
    value = (status or "").strip().lower()
    return value if value in {"sent", "skipped", "error"} else "skipped"


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
