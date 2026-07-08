from __future__ import annotations

import csv
import io
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from vendorverdict.pilot_outcomes import PilotOutcome
from vendorverdict.pilots import PilotRecord
from vendorverdict.storage import default_db_path


PROPOSAL_STATUSES = ("draft", "sent", "negotiation", "accepted", "lost")
PROPOSAL_PACKAGES = ("starter", "team", "advisor", "custom")
PAYMENT_STATUSES = ("not_requested", "invoice_sent", "paid", "overdue", "waived")


PACKAGE_DEFAULTS: dict[str, dict[str, str]] = {
    "starter": {
        "label": "Starter rollout",
        "price": "From £500/month after pilot",
        "billing": "Monthly subscription after the paid pilot; implementation or extended review blocks quoted separately.",
        "scope": "Up to 20 VendorVerdict SaaS reviews per month, saved PDF/Markdown reports, due-diligence question packs, and monthly review calibration.",
    },
    "team": {
        "label": "Team rollout",
        "price": "From £1,000/month after pilot",
        "billing": "Monthly or quarterly subscription after the paid pilot, depending on review volume and support needs.",
        "scope": "Multiple stakeholder users, 40+ VendorVerdict SaaS reviews per month, pilot-to-business reporting, and recurring procurement review support.",
    },
    "advisor": {
        "label": "Advisor / agency rollout",
        "price": "Custom",
        "billing": "Commercial terms depend on client-facing usage, volume, white-label needs, and support model.",
        "scope": "Client-facing VendorVerdict workflow, reusable vendor due-diligence packs, advisor-ready outcome summaries, and commercial model design.",
    },
    "custom": {
        "label": "Custom rollout",
        "price": "Custom",
        "billing": "Commercial terms to be agreed after the pilot close-out call.",
        "scope": "Custom SaaS vendor review workflow based on the customer’s risk, data, stakeholder, and evidence requirements.",
    },
}


def normalize_proposal_status(value: str) -> str:
    normalized = (value or "").strip().lower().replace(" ", "_")
    return normalized if normalized in PROPOSAL_STATUSES else "draft"


def normalize_proposal_package(value: str) -> str:
    normalized = (value or "").strip().lower().replace(" ", "_")
    return normalized if normalized in PROPOSAL_PACKAGES else "starter"


def normalize_payment_status(value: str) -> str:
    normalized = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
    return normalized if normalized in PAYMENT_STATUSES else "not_requested"


def package_from_pilot(pilot_package: str) -> str:
    package = (pilot_package or "").strip().lower()
    if package == "team":
        return "team"
    if package == "advisor":
        return "advisor"
    return "starter"


@dataclass(frozen=True)
class ProposalRecord:
    proposal_id: str
    created_at: str
    updated_at: str
    pilot_id: str
    company: str
    contact_name: str
    contact_email: str
    package: str
    status: str
    proposed_price: str
    billing: str
    scope: str
    success_criteria: str
    next_step: str
    notes: str = ""
    sent_at: str = ""
    follow_up_due: str = ""
    last_follow_up_at: str = ""
    payment_status: str = "not_requested"
    payment_due: str = ""
    payment_url: str = ""
    invoice_reference: str = ""
    paid_at: str = ""

    def __getitem__(self, key: str) -> Any:
        mapping = {
            "id": self.proposal_id,
            "proposal_id": self.proposal_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pilot_id": self.pilot_id,
            "company": self.company,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "package": self.package,
            "status": self.status,
            "proposed_price": self.proposed_price,
            "billing": self.billing,
            "scope": self.scope,
            "success_criteria": self.success_criteria,
            "next_step": self.next_step,
            "notes": self.notes,
            "sent_at": self.sent_at,
            "follow_up_due": self.follow_up_due,
            "last_follow_up_at": self.last_follow_up_at,
            "payment_status": self.payment_status,
            "payment_due": self.payment_due,
            "payment_url": self.payment_url,
            "invoice_reference": self.invoice_reference,
            "paid_at": self.paid_at,
            "package_label": self.package_label,
            "delivery_label": self.delivery_label,
            "is_follow_up_due": self.is_follow_up_due,
            "payment_label": self.payment_label,
            "is_payment_overdue": self.is_payment_overdue,
        }
        return mapping[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    @property
    def package_label(self) -> str:
        return PACKAGE_DEFAULTS.get(self.package, PACKAGE_DEFAULTS["custom"])["label"]

    @property
    def delivery_label(self) -> str:
        if self.status == "sent" and self.sent_at:
            if self.follow_up_due:
                return f"sent · follow-up due {self.follow_up_due}"
            return "sent · follow-up not scheduled"
        if self.last_follow_up_at:
            return f"followed up {self.last_follow_up_at[:10]}"
        if self.follow_up_due:
            return f"follow-up due {self.follow_up_due}"
        return "not sent"

    @property
    def is_follow_up_due(self) -> bool:
        if not self.follow_up_due or self.status in {"accepted", "lost"}:
            return False
        today = datetime.now(UTC).date().isoformat()
        return self.follow_up_due <= today

    @property
    def payment_label(self) -> str:
        status = normalize_payment_status(self.payment_status).replace("_", " ")
        if self.payment_status == "paid" and self.paid_at:
            return f"paid {self.paid_at[:10]}"
        if self.invoice_reference and self.payment_due:
            return f"{status} · {self.invoice_reference} · due {self.payment_due}"
        if self.invoice_reference:
            return f"{status} · {self.invoice_reference}"
        if self.payment_due:
            return f"{status} · due {self.payment_due}"
        return status

    @property
    def is_payment_overdue(self) -> bool:
        if self.payment_status in {"paid", "waived"} or not self.payment_due:
            return False
        today = datetime.now(UTC).date().isoformat()
        return self.payment_due < today


@dataclass(frozen=True)
class ProposalEmail:
    subject: str
    body: str

    def __getitem__(self, key: str) -> str:
        return getattr(self, key)


class ProposalStore:
    """SQLite-backed proposal tracker for closing pilots into recurring work."""

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        self.db_path = Path(db_path or default_db_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def create_from_pilot(self, pilot: PilotRecord, outcome: PilotOutcome | None = None, *, settings: Mapping[str, str] | Any | None = None) -> str:
        existing = self.get_by_pilot_id(pilot.pilot_id)
        if existing is not None:
            return existing.proposal_id

        proposal_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        package = package_from_pilot(pilot.package)
        defaults = _proposal_defaults(package, settings=settings)
        company = pilot.company or pilot.contact_name or "Prospect"
        success_criteria = _success_criteria_from_outcome(outcome, pilot)
        next_step = _next_step_from_outcome(outcome)

        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO proposals (
                    id, created_at, updated_at, pilot_id, company, contact_name, contact_email,
                    package, status, proposed_price, billing, scope, success_criteria, next_step, notes,
                    sent_at, follow_up_due, last_follow_up_at, payment_status, payment_due, payment_url,
                    invoice_reference, paid_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    now,
                    now,
                    pilot.pilot_id,
                    company,
                    pilot.contact_name,
                    pilot.contact_email,
                    package,
                    "draft",
                    defaults["price"],
                    defaults["billing"],
                    defaults["scope"],
                    success_criteria,
                    next_step,
                    "",
                    "",
                    "",
                    "",
                    "not_requested",
                    "",
                    "",
                    "",
                    "",
                ),
            )
            conn.commit()
        return proposal_id

    def list_proposals(self, limit: int = 50) -> list[ProposalRecord]:
        safe_limit = max(1, min(limit, 500))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM proposals ORDER BY created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_proposal(self, proposal_id: str) -> ProposalRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        return self._row_to_record(row) if row is not None else None

    def get_by_pilot_id(self, pilot_id: str) -> ProposalRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM proposals WHERE pilot_id = ? ORDER BY created_at DESC LIMIT 1",
                (pilot_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def update_proposal(
        self,
        proposal_id: str,
        *,
        status: str,
        package: str,
        proposed_price: str,
        billing: str,
        scope: str,
        success_criteria: str,
        next_step: str,
        notes: str,
    ) -> bool:
        safe_status = normalize_proposal_status(status)
        safe_package = normalize_proposal_package(package)
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE proposals
                SET updated_at = ?, status = ?, package = ?, proposed_price = ?, billing = ?,
                    scope = ?, success_criteria = ?, next_step = ?, notes = ?
                WHERE id = ?
                """,
                (
                    now,
                    safe_status,
                    safe_package,
                    proposed_price.strip(),
                    billing.strip(),
                    scope.strip(),
                    success_criteria.strip(),
                    next_step.strip(),
                    notes.strip(),
                    proposal_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_sent(self, proposal_id: str, *, follow_up_due: str = "") -> bool:
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE proposals
                SET updated_at = ?, status = 'sent', sent_at = ?, follow_up_due = ?
                WHERE id = ?
                """,
                (now, now, _date_value(follow_up_due), proposal_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def schedule_follow_up(self, proposal_id: str, *, follow_up_due: str) -> bool:
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                "UPDATE proposals SET updated_at = ?, follow_up_due = ? WHERE id = ?",
                (now, _date_value(follow_up_due), proposal_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_followed_up(self, proposal_id: str, *, follow_up_due: str = "") -> bool:
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE proposals
                SET updated_at = ?, status = CASE WHEN status = 'draft' THEN 'sent' ELSE status END,
                    last_follow_up_at = ?, follow_up_due = ?
                WHERE id = ?
                """,
                (now, now, _date_value(follow_up_due), proposal_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_payment(
        self,
        proposal_id: str,
        *,
        payment_status: str,
        payment_due: str = "",
        payment_url: str = "",
        invoice_reference: str = "",
    ) -> bool:
        now = datetime.now(UTC).isoformat()
        safe_status = normalize_payment_status(payment_status)
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE proposals
                SET updated_at = ?, payment_status = ?, payment_due = ?, payment_url = ?, invoice_reference = ?
                WHERE id = ?
                """,
                (now, safe_status, _date_value(payment_due), payment_url.strip(), invoice_reference.strip(), proposal_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_invoice_sent(
        self,
        proposal_id: str,
        *,
        payment_due: str = "",
        payment_url: str = "",
        invoice_reference: str = "",
    ) -> bool:
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE proposals
                SET updated_at = ?, payment_status = 'invoice_sent', payment_due = ?,
                    payment_url = ?, invoice_reference = ?
                WHERE id = ?
                """,
                (now, _date_value(payment_due), payment_url.strip(), invoice_reference.strip(), proposal_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_paid(self, proposal_id: str) -> bool:
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE proposals
                SET updated_at = ?, payment_status = 'paid', paid_at = ?
                WHERE id = ?
                """,
                (now, now, proposal_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def payment_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in PAYMENT_STATUSES}
        counts["overdue"] = 0
        for proposal in self.list_proposals(limit=2000):
            counts[normalize_payment_status(proposal.payment_status)] += 1
            if proposal.is_payment_overdue:
                counts["overdue"] += 1
        return counts

    def delivery_counts(self) -> dict[str, int]:
        counts = {"not_sent": 0, "sent": 0, "follow_up_due": 0, "accepted": 0, "lost": 0}
        for proposal in self.list_proposals(limit=2000):
            if proposal.status == "accepted":
                counts["accepted"] += 1
            elif proposal.status == "lost":
                counts["lost"] += 1
            elif proposal.is_follow_up_due:
                counts["follow_up_due"] += 1
            elif proposal.sent_at or proposal.status in {"sent", "negotiation"}:
                counts["sent"] += 1
            else:
                counts["not_sent"] += 1
        return counts

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in PROPOSAL_STATUSES}
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS count FROM proposals GROUP BY status").fetchall()
        for row in rows:
            counts[normalize_proposal_status(row["status"])] = int(row["count"] or 0)
        return counts

    def export_csv(self, limit: int = 2000) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "created_at", "updated_at", "company", "contact_name", "contact_email", "pilot_id",
            "package", "status", "proposed_price", "billing", "scope", "success_criteria",
            "next_step", "notes", "sent_at", "follow_up_due", "last_follow_up_at",
            "payment_status", "payment_due", "payment_url", "invoice_reference", "paid_at",
        ])
        for proposal in self.list_proposals(limit=limit):
            writer.writerow([
                proposal.created_at,
                proposal.updated_at,
                proposal.company,
                proposal.contact_name,
                proposal.contact_email,
                proposal.pilot_id,
                proposal.package,
                proposal.status,
                proposal.proposed_price,
                proposal.billing,
                proposal.scope,
                proposal.success_criteria,
                proposal.next_step,
                proposal.notes,
                proposal.sent_at,
                proposal.follow_up_due,
                proposal.last_follow_up_at,
                proposal.payment_status,
                proposal.payment_due,
                proposal.payment_url,
                proposal.invoice_reference,
                proposal.paid_at,
            ])
        return output.getvalue()

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    pilot_id TEXT NOT NULL DEFAULT '',
                    company TEXT NOT NULL DEFAULT '',
                    contact_name TEXT NOT NULL DEFAULT '',
                    contact_email TEXT NOT NULL DEFAULT '',
                    package TEXT NOT NULL DEFAULT 'starter',
                    status TEXT NOT NULL DEFAULT 'draft',
                    proposed_price TEXT NOT NULL DEFAULT '',
                    billing TEXT NOT NULL DEFAULT '',
                    scope TEXT NOT NULL DEFAULT '',
                    success_criteria TEXT NOT NULL DEFAULT '',
                    next_step TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    sent_at TEXT NOT NULL DEFAULT '',
                    follow_up_due TEXT NOT NULL DEFAULT '',
                    last_follow_up_at TEXT NOT NULL DEFAULT '',
                    payment_status TEXT NOT NULL DEFAULT 'not_requested',
                    payment_due TEXT NOT NULL DEFAULT '',
                    payment_url TEXT NOT NULL DEFAULT '',
                    invoice_reference TEXT NOT NULL DEFAULT '',
                    paid_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON proposals(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_proposals_pilot_id ON proposals(pilot_id);
                CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
                """
            )
            existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(proposals)").fetchall()}
            migrations = {
                "sent_at": "ALTER TABLE proposals ADD COLUMN sent_at TEXT NOT NULL DEFAULT ''",
                "follow_up_due": "ALTER TABLE proposals ADD COLUMN follow_up_due TEXT NOT NULL DEFAULT ''",
                "last_follow_up_at": "ALTER TABLE proposals ADD COLUMN last_follow_up_at TEXT NOT NULL DEFAULT ''",
                "payment_status": "ALTER TABLE proposals ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'not_requested'",
                "payment_due": "ALTER TABLE proposals ADD COLUMN payment_due TEXT NOT NULL DEFAULT ''",
                "payment_url": "ALTER TABLE proposals ADD COLUMN payment_url TEXT NOT NULL DEFAULT ''",
                "invoice_reference": "ALTER TABLE proposals ADD COLUMN invoice_reference TEXT NOT NULL DEFAULT ''",
                "paid_at": "ALTER TABLE proposals ADD COLUMN paid_at TEXT NOT NULL DEFAULT ''",
            }
            for column, statement in migrations.items():
                if column not in existing_columns:
                    conn.execute(statement)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ProposalRecord:
        return ProposalRecord(
            proposal_id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            pilot_id=row["pilot_id"],
            company=row["company"],
            contact_name=row["contact_name"],
            contact_email=row["contact_email"],
            package=normalize_proposal_package(row["package"]),
            status=normalize_proposal_status(row["status"]),
            proposed_price=row["proposed_price"] or "",
            billing=row["billing"] or "",
            scope=row["scope"] or "",
            success_criteria=row["success_criteria"] or "",
            next_step=row["next_step"] or "",
            notes=row["notes"] or "",
            sent_at=row["sent_at"] or "",
            follow_up_due=row["follow_up_due"] or "",
            last_follow_up_at=row["last_follow_up_at"] or "",
            payment_status=normalize_payment_status(row["payment_status"] or "not_requested"),
            payment_due=row["payment_due"] or "",
            payment_url=row["payment_url"] or "",
            invoice_reference=row["invoice_reference"] or "",
            paid_at=row["paid_at"] or "",
        )


def _proposal_defaults(package: str, *, settings: Mapping[str, str] | Any | None = None) -> dict[str, str]:
    defaults = dict(PACKAGE_DEFAULTS.get(package, PACKAGE_DEFAULTS["custom"]))
    if settings is None:
        return defaults

    price = _setting_get(settings, "default_proposal_price")
    billing = _setting_get(settings, "default_proposal_billing")
    if price:
        defaults["price"] = price
    if billing:
        defaults["billing"] = billing
    return defaults


def _setting_get(settings: Mapping[str, str] | Any, key: str) -> str:
    if isinstance(settings, Mapping):
        return str(settings.get(key, "") or "").strip()
    return str(getattr(settings, key, "") or "").strip()


def build_proposal_email(proposal: ProposalRecord) -> ProposalEmail:
    greeting_name = proposal.contact_name.split()[0] if proposal.contact_name else "there"
    subject = f"VendorVerdict next step for {proposal.company}"
    company_sentence = _sentence_value(proposal.company)
    body = (
        f"Hi {greeting_name},\n\n"
        f"Following the VendorVerdict pilot, I put together a proposed next step for {company_sentence}\n\n"
        f"Suggested package: {proposal.package_label}\n"
        f"Commercial starting point: {proposal.proposed_price}\n\n"
        f"Proposed scope:\n{proposal.scope}\n\n"
        f"Success criteria:\n{proposal.success_criteria}\n\n"
        f"Suggested next step:\n{proposal.next_step}\n\n"
        f"{_payment_email_block(proposal)}"
        "Would it be useful to discuss this and decide whether VendorVerdict should continue as a recurring vendor-review workflow for your team?\n\n"
        "Best,\n"
        "Vladimir"
    )
    return ProposalEmail(subject=subject, body=body)


def _payment_email_block(proposal: ProposalRecord) -> str:
    if not proposal.payment_url and not proposal.invoice_reference and not proposal.payment_due:
        return ""
    lines = ["Payment / invoice details:"]
    if proposal.invoice_reference:
        lines.append(f"Invoice reference: {proposal.invoice_reference}")
    if proposal.payment_due:
        lines.append(f"Payment due: {proposal.payment_due}")
    if proposal.payment_url:
        lines.append(f"Payment link: {proposal.payment_url}")
    return "\n".join(lines) + "\n\n"


def build_proposal_mailto(proposal: ProposalRecord) -> str:
    email = build_proposal_email(proposal)
    recipient = quote(proposal.contact_email.strip())
    subject = quote(email.subject)
    body = quote(email.body)
    return f"mailto:{recipient}?subject={subject}&body={body}"


def _payment_markdown_lines(proposal: ProposalRecord) -> list[str]:
    lines: list[str] = []
    if proposal.invoice_reference:
        lines.append(f"- Invoice reference: {proposal.invoice_reference}")
    if proposal.payment_due:
        lines.append(f"- Payment due: {proposal.payment_due}")
    if proposal.payment_url:
        lines.append(f"- Payment link: {proposal.payment_url}")
    return lines


def _date_value(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    # Browser date inputs submit YYYY-MM-DD. Keep only safe date-like values.
    try:
        datetime.fromisoformat(cleaned)
        return cleaned[:10]
    except ValueError:
        return ""


def render_proposal_markdown(proposal: ProposalRecord) -> str:
    """Render a customer-facing proposal Markdown export.

    Internal tracking details such as pipeline status, internal notes, pilot IDs, and email drafts stay on
    the protected dashboard rather than in customer-shareable exports.
    """
    return "\n".join(
        [
            f"# VendorVerdict proposal for {proposal.company}",
            "",
            "## Package and commercial terms",
            f"- Package: {proposal.package_label}",
            f"- Proposed price: {proposal.proposed_price or 'To be agreed'}",
            f"- Billing: {proposal.billing or 'To be agreed'}",
            *_payment_markdown_lines(proposal),
            f"- Contact: {proposal.contact_name} <{proposal.contact_email}>",
            "",
            "## Proposed scope",
            proposal.scope or "To be agreed.",
            "",
            "## Success criteria",
            customer_success_criteria(proposal.success_criteria) or "To be agreed.",
            "",
            "## Suggested next step",
            customer_next_step(proposal.next_step),
            "",
            "## Disclaimer",
            "This VendorVerdict proposal is a commercial discussion document. It is not legal advice, financial advice, a formal security audit, or a binding contract unless separately agreed in writing.",
            "",
        ]
    )


def customer_success_criteria(text: str) -> str:
    """Make proposal success criteria customer-facing.

    The proposal record can retain internal pilot detail for the dashboard, but customer exports should
    avoid weak progress metrics and overly vendor-specific wording such as "why Notion was
    recommended most often".
    """
    cleaned: list[str] = []
    inserted_vendor_approach = False
    generic_vendor_line = (
        "- Use the close-out discussion to confirm the recommended vendor approach, "
        "remaining evidence gaps, and rollout priorities."
    )
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if not line:
            continue
        if "pilot delivery baseline:" in lower and "reviews delivered" in lower:
            continue
        if (
            "recommended most often" in lower
            or ("review why" in lower and "recommended" in lower)
            or ("why " in lower and " was recommended" in lower)
        ):
            if not inserted_vendor_approach:
                cleaned.append(generic_vendor_line)
                inserted_vendor_approach = True
            continue
        cleaned.append(line)
    if not cleaned:
        return ""
    return "\n".join(cleaned)


def customer_next_step(text: str) -> str:
    """Return a polished customer-facing next step for proposal exports."""
    fallback = (
        "Book a 30-minute call to review the pilot outcome, confirm rollout scope, "
        "and agree the recurring VendorVerdict package."
    )
    candidate = (text or "").strip()
    if not candidate:
        return fallback
    lower = candidate.lower()
    if (
        "remaining pilot actions" in lower
        or "commercial close-out" in lower
        or "close-out call" in lower
        or "recurring package" in lower
    ):
        return fallback
    return candidate


def _sentence_value(value: str) -> str:
    cleaned = (value or "").strip() or "your team"
    return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."


def _success_criteria_from_outcome(outcome: PilotOutcome | None, pilot: PilotRecord) -> str:
    if outcome is None:
        return (
            "A recurring VendorVerdict workflow is useful if it helps the team create decision-ready "
            "SaaS review records before sensitive client or business data is put into new tools."
        )
    criteria = [
        f"Continue if VendorVerdict can support up to {outcome.review_target} recurring SaaS review decisions with clear reports and evidence-backed due-diligence questions.",
        "Use the close-out discussion to confirm the recommended vendor approach, remaining evidence gaps, and rollout priorities.",
        "Use the rollout discussion to agree recurring review volume, decision owners, and evidence standards.",
    ]
    if pilot.objective:
        criteria.append(f"Customer objective: {pilot.objective}")
    return "\n".join(f"- {item}" for item in criteria)


def _next_step_from_outcome(outcome: PilotOutcome | None) -> str:
    return (
        "Book a 30-minute call to review the pilot outcome, confirm rollout scope, "
        "and agree the recurring VendorVerdict package."
    )
