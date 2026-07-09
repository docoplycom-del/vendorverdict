from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from vendorverdict.proposals import ProposalRecord, normalize_proposal_package
from vendorverdict.storage import default_db_path


CUSTOMER_STATUSES = ("onboarding", "active", "paused", "churned")
CUSTOMER_PACKAGES = ("starter", "team", "advisor", "custom")
BILLING_STATUSES = ("trial", "current", "payment_due", "overdue", "waived")


PACKAGE_REVIEW_ALLOWANCE = {
    "starter": 20,
    "team": 40,
    "advisor": 100,
    "custom": 0,
}


def normalize_customer_status(value: str) -> str:
    normalized = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
    return normalized if normalized in CUSTOMER_STATUSES else "onboarding"


def normalize_billing_status(value: str) -> str:
    normalized = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
    return normalized if normalized in BILLING_STATUSES else "trial"


@dataclass(frozen=True)
class CustomerRecord:
    customer_id: str
    created_at: str
    updated_at: str
    proposal_id: str
    pilot_id: str
    company: str
    contact_name: str
    contact_email: str
    package: str
    status: str
    billing_status: str
    review_allowance: int
    renewal_date: str = ""
    onboarding_notes: str = ""
    internal_notes: str = ""
    review_count: int = 0

    def __getitem__(self, key: str) -> Any:
        mapping = {
            "id": self.customer_id,
            "customer_id": self.customer_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "proposal_id": self.proposal_id,
            "pilot_id": self.pilot_id,
            "company": self.company,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "package": self.package,
            "package_label": self.package_label,
            "status": self.status,
            "billing_status": self.billing_status,
            "review_allowance": self.review_allowance,
            "renewal_date": self.renewal_date,
            "onboarding_notes": self.onboarding_notes,
            "internal_notes": self.internal_notes,
            "review_count": self.review_count,
            "reviews_used": self.review_count,
            "reviews_remaining": self.reviews_remaining,
            "usage_percent": self.usage_percent,
            "billing_label": self.billing_label,
        }
        return mapping[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    @property
    def package_label(self) -> str:
        return {
            "starter": "Starter rollout",
            "team": "Team rollout",
            "advisor": "Advisor / agency rollout",
            "custom": "Custom rollout",
        }.get(self.package, "Custom rollout")

    @property
    def billing_label(self) -> str:
        label = self.billing_status.replace("_", " ")
        if self.renewal_date:
            return f"{label} · renews {self.renewal_date}"
        return label

    @property
    def reviews_remaining(self) -> int:
        if self.review_allowance <= 0:
            return 0
        return max(0, self.review_allowance - self.review_count)

    @property
    def usage_percent(self) -> int:
        if self.review_allowance <= 0:
            return 0
        return min(100, round((self.review_count / self.review_allowance) * 100))


@dataclass(frozen=True)
class CustomerReview:
    customer_id: str
    report_id: str
    created_at: str
    label: str
    status: str
    notes: str
    raw_query: str = ""
    vendors: tuple[str, ...] = ()
    use_case: str = ""
    recommended_vendor: str = ""
    overall_confidence: str = ""

    def __getitem__(self, key: str) -> Any:
        mapping = {
            "customer_id": self.customer_id,
            "report_id": self.report_id,
            "created_at": self.created_at,
            "label": self.label,
            "status": self.status,
            "notes": self.notes,
            "raw_query": self.raw_query,
            "vendors": self.vendors,
            "use_case": self.use_case,
            "recommended_vendor": self.recommended_vendor,
            "recommendation": self.recommended_vendor,
            "overall_confidence": self.overall_confidence,
            "confidence": self.overall_confidence,
        }
        return mapping[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


class CustomerStore:
    """SQLite-backed customer activation tracker.

    This starts after a proposal is accepted or paid. It is deliberately lightweight: it records who the
    customer is, which proposal/pilot created the account, the package, review allowance, billing state,
    renewal date, and onboarding notes.
    """

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        self.db_path = Path(db_path or default_db_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def create_from_proposal(
        self,
        proposal: ProposalRecord,
        *,
        status: str = "",
        billing_status: str = "",
        review_allowance: int | str | None = None,
        renewal_date: str = "",
        onboarding_notes: str = "",
    ) -> str:
        existing = self.get_by_proposal_id(proposal.proposal_id)
        if existing is not None:
            return existing.customer_id

        now = datetime.now(UTC).isoformat()
        customer_id = str(uuid4())
        package = normalize_proposal_package(proposal.package)
        safe_status = normalize_customer_status(status or ("active" if proposal.payment_status == "paid" else "onboarding"))
        safe_billing = normalize_billing_status(
            billing_status or ("current" if proposal.payment_status == "paid" else "payment_due" if proposal.payment_status == "invoice_sent" else "trial")
        )
        allowance = _review_allowance(review_allowance, package)
        renewal = _date_value(renewal_date) or _default_renewal_date()
        notes = onboarding_notes.strip() or _default_onboarding_notes(proposal)

        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO customer_accounts (
                    id, created_at, updated_at, proposal_id, pilot_id, company, contact_name, contact_email,
                    package, status, billing_status, review_allowance, renewal_date, onboarding_notes, internal_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    customer_id,
                    now,
                    now,
                    proposal.proposal_id,
                    proposal.pilot_id,
                    proposal.company,
                    proposal.contact_name,
                    proposal.contact_email,
                    package,
                    safe_status,
                    safe_billing,
                    allowance,
                    renewal,
                    notes,
                    "",
                ),
            )
            conn.commit()
        return customer_id

    def list_customers(self, limit: int = 100) -> list[CustomerRecord]:
        safe_limit = max(1, min(limit, 2000))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT ca.*, COALESCE(r.review_count, 0) AS review_count
                FROM customer_accounts ca
                LEFT JOIN (
                    SELECT customer_id, COUNT(*) AS review_count
                    FROM customer_reviews
                    GROUP BY customer_id
                ) r ON r.customer_id = ca.id
                ORDER BY ca.created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_customer(self, customer_id: str) -> CustomerRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT ca.*, COALESCE(r.review_count, 0) AS review_count
                FROM customer_accounts ca
                LEFT JOIN (
                    SELECT customer_id, COUNT(*) AS review_count
                    FROM customer_reviews
                    GROUP BY customer_id
                ) r ON r.customer_id = ca.id
                WHERE ca.id = ?
                """,
                (customer_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def get_by_proposal_id(self, proposal_id: str) -> CustomerRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT ca.*, COALESCE(r.review_count, 0) AS review_count
                FROM customer_accounts ca
                LEFT JOIN (
                    SELECT customer_id, COUNT(*) AS review_count
                    FROM customer_reviews
                    GROUP BY customer_id
                ) r ON r.customer_id = ca.id
                WHERE ca.proposal_id = ?
                ORDER BY ca.created_at DESC
                LIMIT 1
                """,
                (proposal_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def update_customer(
        self,
        customer_id: str,
        *,
        status: str,
        billing_status: str,
        package: str,
        review_allowance: int | str,
        renewal_date: str,
        onboarding_notes: str,
        internal_notes: str,
    ) -> bool:
        now = datetime.now(UTC).isoformat()
        safe_package = normalize_proposal_package(package)
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE customer_accounts
                SET updated_at = ?, status = ?, billing_status = ?, package = ?, review_allowance = ?,
                    renewal_date = ?, onboarding_notes = ?, internal_notes = ?
                WHERE id = ?
                """,
                (
                    now,
                    normalize_customer_status(status),
                    normalize_billing_status(billing_status),
                    safe_package,
                    _review_allowance(review_allowance, safe_package),
                    _date_value(renewal_date),
                    onboarding_notes.strip(),
                    internal_notes.strip(),
                    customer_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def link_report(
        self,
        customer_id: str,
        report_id: str,
        *,
        label: str = "",
        status: str = "completed",
        notes: str = "",
    ) -> bool:
        if self.get_customer(customer_id) is None:
            return False
        created_at = datetime.now(UTC).isoformat()
        safe_label = (label or "Customer vendor review").strip()
        safe_status = (status or "completed").strip().lower().replace(" ", "_")
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO customer_reviews (customer_id, report_id, created_at, label, status, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(customer_id, report_id) DO UPDATE SET
                    label = excluded.label,
                    status = excluded.status,
                    notes = excluded.notes
                """,
                (customer_id, report_id, created_at, safe_label, safe_status, notes.strip()),
            )
            conn.commit()
        return True

    def list_reviews(self, customer_id: str) -> list[CustomerReview]:
        with closing(self._connect()) as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT cr.customer_id, cr.report_id, cr.created_at, cr.label, cr.status, cr.notes,
                           r.raw_query, r.vendors_json, r.use_case, r.recommended_vendor, r.overall_confidence
                    FROM customer_reviews cr
                    LEFT JOIN reports r ON r.id = cr.report_id
                    WHERE cr.customer_id = ?
                    ORDER BY cr.created_at DESC
                    """,
                    (customer_id,),
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table: reports" not in str(exc):
                    raise
                rows = conn.execute(
                    """
                    SELECT customer_id, report_id, created_at, label, status, notes,
                           '' AS raw_query, '[]' AS vendors_json, '' AS use_case,
                           '' AS recommended_vendor, '' AS overall_confidence
                    FROM customer_reviews
                    WHERE customer_id = ?
                    ORDER BY created_at DESC
                    """,
                    (customer_id,),
                ).fetchall()
        return [self._row_to_review(row) for row in rows]

    def review_count(self, customer_id: str) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM customer_reviews WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
        return int(row["count"] or 0) if row is not None else 0

    def remaining_reviews(self, customer_id: str) -> int:
        customer = self.get_customer(customer_id)
        if customer is None or customer.review_allowance <= 0:
            return 0
        return max(0, customer.review_allowance - self.review_count(customer_id))

    def export_reviews_csv(self, customer_id: str) -> str:
        reviews = self.list_reviews(customer_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "created_at", "label", "status", "report_id", "vendors", "use_case",
            "recommended_vendor", "confidence", "notes",
        ])
        for review in reviews:
            writer.writerow([
                review.created_at,
                review.label,
                review.status,
                review.report_id,
                ", ".join(review.vendors),
                review.use_case,
                review.recommended_vendor,
                review.overall_confidence,
                review.notes,
            ])
        return output.getvalue()

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in CUSTOMER_STATUSES}
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS count FROM customer_accounts GROUP BY status").fetchall()
        for row in rows:
            counts[normalize_customer_status(row["status"])] = int(row["count"] or 0)
        return counts

    def billing_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in BILLING_STATUSES}
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT billing_status, COUNT(*) AS count FROM customer_accounts GROUP BY billing_status").fetchall()
        for row in rows:
            counts[normalize_billing_status(row["billing_status"])] = int(row["count"] or 0)
        return counts

    def export_csv(self, limit: int = 2000) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "created_at", "updated_at", "company", "contact_name", "contact_email", "proposal_id",
            "pilot_id", "package", "status", "billing_status", "review_allowance", "reviews_used",
            "reviews_remaining", "usage_percent", "renewal_date", "onboarding_notes", "internal_notes",
        ])
        for customer in self.list_customers(limit=limit):
            writer.writerow([
                customer.created_at,
                customer.updated_at,
                customer.company,
                customer.contact_name,
                customer.contact_email,
                customer.proposal_id,
                customer.pilot_id,
                customer.package,
                customer.status,
                customer.billing_status,
                customer.review_allowance,
                customer.review_count,
                customer.reviews_remaining,
                customer.usage_percent,
                customer.renewal_date,
                customer.onboarding_notes,
                customer.internal_notes,
            ])
        return output.getvalue()

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS customer_accounts (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    proposal_id TEXT NOT NULL DEFAULT '',
                    pilot_id TEXT NOT NULL DEFAULT '',
                    company TEXT NOT NULL DEFAULT '',
                    contact_name TEXT NOT NULL DEFAULT '',
                    contact_email TEXT NOT NULL DEFAULT '',
                    package TEXT NOT NULL DEFAULT 'starter',
                    status TEXT NOT NULL DEFAULT 'onboarding',
                    billing_status TEXT NOT NULL DEFAULT 'trial',
                    review_allowance INTEGER NOT NULL DEFAULT 0,
                    renewal_date TEXT NOT NULL DEFAULT '',
                    onboarding_notes TEXT NOT NULL DEFAULT '',
                    internal_notes TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS customer_reviews (
                    customer_id TEXT NOT NULL,
                    report_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'completed',
                    notes TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (customer_id, report_id)
                );

                CREATE INDEX IF NOT EXISTS idx_customer_accounts_created_at ON customer_accounts(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_customer_accounts_proposal_id ON customer_accounts(proposal_id);
                CREATE INDEX IF NOT EXISTS idx_customer_accounts_status ON customer_accounts(status);
                CREATE INDEX IF NOT EXISTS idx_customer_reviews_customer_id ON customer_reviews(customer_id);
                CREATE INDEX IF NOT EXISTS idx_customer_reviews_report_id ON customer_reviews(report_id);
                """
            )
            existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(customer_accounts)").fetchall()}
            migrations = {
                "billing_status": "ALTER TABLE customer_accounts ADD COLUMN billing_status TEXT NOT NULL DEFAULT 'trial'",
                "review_allowance": "ALTER TABLE customer_accounts ADD COLUMN review_allowance INTEGER NOT NULL DEFAULT 0",
                "renewal_date": "ALTER TABLE customer_accounts ADD COLUMN renewal_date TEXT NOT NULL DEFAULT ''",
                "onboarding_notes": "ALTER TABLE customer_accounts ADD COLUMN onboarding_notes TEXT NOT NULL DEFAULT ''",
                "internal_notes": "ALTER TABLE customer_accounts ADD COLUMN internal_notes TEXT NOT NULL DEFAULT ''",
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
    def _row_to_record(row: sqlite3.Row) -> CustomerRecord:
        return CustomerRecord(
            customer_id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            proposal_id=row["proposal_id"],
            pilot_id=row["pilot_id"],
            company=row["company"],
            contact_name=row["contact_name"],
            contact_email=row["contact_email"],
            package=normalize_proposal_package(row["package"]),
            status=normalize_customer_status(row["status"]),
            billing_status=normalize_billing_status(row["billing_status"]),
            review_allowance=int(row["review_allowance"] or 0),
            renewal_date=row["renewal_date"] or "",
            onboarding_notes=row["onboarding_notes"] or "",
            internal_notes=row["internal_notes"] or "",
            review_count=int(row["review_count"] or 0) if "review_count" in row.keys() else 0,
        )

    @staticmethod
    def _row_to_review(row: sqlite3.Row) -> CustomerReview:
        vendors: tuple[str, ...] = ()
        vendors_json = row["vendors_json"] if "vendors_json" in row.keys() else None
        if vendors_json:
            try:
                vendors = tuple(json.loads(vendors_json))
            except (TypeError, ValueError):
                vendors = ()
        return CustomerReview(
            customer_id=row["customer_id"],
            report_id=row["report_id"],
            created_at=row["created_at"],
            label=row["label"] or "Customer vendor review",
            status=row["status"] or "completed",
            notes=row["notes"] or "",
            raw_query=row["raw_query"] or "",
            vendors=vendors,
            use_case=row["use_case"] or "",
            recommended_vendor=row["recommended_vendor"] or "",
            overall_confidence=row["overall_confidence"] or "",
        )


def _review_allowance(value: int | str | None, package: str) -> int:
    if value is None or str(value).strip() == "":
        return PACKAGE_REVIEW_ALLOWANCE.get(package, 0)
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return PACKAGE_REVIEW_ALLOWANCE.get(package, 0)
    return max(0, min(parsed, 10000))


def _date_value(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    try:
        datetime.fromisoformat(cleaned)
        return cleaned[:10]
    except ValueError:
        return ""


def _default_renewal_date() -> str:
    return (datetime.now(UTC).date() + timedelta(days=30)).isoformat()


def _default_onboarding_notes(proposal: ProposalRecord) -> str:
    if proposal.payment_status == "paid":
        return "Payment recorded. Start customer onboarding, confirm first recurring review batch, and agree reporting cadence."
    if proposal.status == "accepted":
        return "Proposal accepted. Confirm payment, onboarding call, and first recurring review batch."
    return "Customer account created from proposal. Confirm commercial acceptance, payment status, and onboarding call."
