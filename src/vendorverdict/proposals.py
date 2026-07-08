from __future__ import annotations

import csv
import io
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from vendorverdict.pilot_outcomes import PilotOutcome
from vendorverdict.pilots import PilotRecord
from vendorverdict.storage import default_db_path


PROPOSAL_STATUSES = ("draft", "sent", "negotiation", "accepted", "lost")
PROPOSAL_PACKAGES = ("starter", "team", "advisor", "custom")


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
            "package_label": self.package_label,
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

    def create_from_pilot(self, pilot: PilotRecord, outcome: PilotOutcome | None = None) -> str:
        existing = self.get_by_pilot_id(pilot.pilot_id)
        if existing is not None:
            return existing.proposal_id

        proposal_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        package = package_from_pilot(pilot.package)
        defaults = PACKAGE_DEFAULTS[package]
        company = pilot.company or pilot.contact_name or "Prospect"
        success_criteria = _success_criteria_from_outcome(outcome, pilot)
        next_step = _next_step_from_outcome(outcome)

        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO proposals (
                    id, created_at, updated_at, pilot_id, company, contact_name, contact_email,
                    package, status, proposed_price, billing, scope, success_criteria, next_step, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            "next_step", "notes",
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
                    notes TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON proposals(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_proposals_pilot_id ON proposals(pilot_id);
                CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
                """
            )
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
        )


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
        "Would it be useful to discuss this and decide whether VendorVerdict should continue as a recurring vendor-review workflow for your team?\n\n"
        "Best,\n"
        "Vladimir"
    )
    return ProposalEmail(subject=subject, body=body)


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
            f"- Contact: {proposal.contact_name} <{proposal.contact_email}>",
            "",
            "## Proposed scope",
            proposal.scope or "To be agreed.",
            "",
            "## Success criteria",
            customer_success_criteria(proposal.success_criteria) or "To be agreed.",
            "",
            "## Suggested next step",
            proposal.next_step or "Book a commercial follow-up call.",
            "",
            "## Disclaimer",
            "This VendorVerdict proposal is a commercial discussion document. It is not legal advice, financial advice, a formal security audit, or a binding contract unless separately agreed in writing.",
            "",
        ]
    )


def customer_success_criteria(text: str) -> str:
    """Remove internal pilot metrics from customer-facing proposal exports."""
    cleaned: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if not line:
            continue
        if "pilot delivery baseline:" in lower and "reviews delivered" in lower:
            continue
        cleaned.append(line)
    if not cleaned:
        return ""
    return "\n".join(cleaned)


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
        "Use the pilot close-out discussion to agree recurring review volume, decision owners, and evidence standards for rollout.",
    ]
    if outcome.top_recommended_vendor:
        criteria.append(f"Review why {outcome.top_recommended_vendor} was recommended and confirm any remaining evidence gaps before rollout.")
    if pilot.objective:
        criteria.append(f"Customer objective: {pilot.objective}")
    return "\n".join(f"- {item}" for item in criteria)


def _next_step_from_outcome(outcome: PilotOutcome | None) -> str:
    if outcome and outcome.open_actions and outcome.open_actions != ("No major open actions recorded.",):
        return "Book a 30-minute commercial close-out call, resolve the remaining pilot actions, and agree the recurring package."
    return "Book a 30-minute commercial close-out call and agree whether to start the recurring VendorVerdict package."
