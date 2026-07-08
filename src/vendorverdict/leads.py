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

from vendorverdict.storage import default_db_path


LEAD_STATUSES = ("new", "contacted", "qualified", "won", "lost")


def normalize_lead_status(value: str) -> str:
    normalized = (value or "").strip().lower().replace(" ", "_")
    return normalized if normalized in LEAD_STATUSES else "new"


@dataclass(frozen=True)
class LeadRecord:
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
    notes: str = ""
    notification_status: str = "not_sent"
    notified_at: str = ""
    notification_error: str = ""

    def __getitem__(self, key: str) -> Any:
        mapping = {
            "id": self.lead_id,
            "lead_id": self.lead_id,
            "created_at": self.created_at,
            "name": self.name,
            "email": self.email,
            "company": self.company,
            "use_case": self.use_case,
            "vendors": self.vendors,
            "message": self.message,
            "source": self.source,
            "status": self.status,
            "notes": self.notes,
            "notification_status": self.notification_status,
            "notified_at": self.notified_at,
            "notification_error": self.notification_error,
        }
        return mapping[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


class LeadStore:
    """SQLite-backed lead capture store for pilot requests."""

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        self.db_path = Path(db_path or default_db_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def save_lead(
        self,
        *,
        name: str,
        email: str,
        company: str = "",
        use_case: str = "",
        vendors: str = "",
        message: str = "",
        source: str = "demo",
    ) -> str:
        lead_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO lead_requests (
                    id, created_at, name, email, company, use_case,
                    vendors, message, source, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lead_id,
                    created_at,
                    name.strip(),
                    email.strip(),
                    company.strip(),
                    use_case.strip(),
                    vendors.strip(),
                    message.strip(),
                    source.strip() or "demo",
                    "new",
                ),
            )
            conn.commit()
        return lead_id

    def list_leads(self, limit: int = 50) -> list[LeadRecord]:
        safe_limit = max(1, min(limit, 200))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, name, email, company, use_case,
                       vendors, message, source, status, notes,
                       notification_status, notified_at, notification_error
                FROM lead_requests
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_lead(self, lead_id: str) -> LeadRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT id, created_at, name, email, company, use_case,
                       vendors, message, source, status, notes,
                       notification_status, notified_at, notification_error
                FROM lead_requests
                WHERE id = ?
                """,
                (lead_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def update_notification_status(self, lead_id: str, *, status: str, error: str = "") -> None:
        notified_at = datetime.now(UTC).isoformat() if status == "sent" else ""
        with closing(self._connect()) as conn:
            conn.execute(
                """
                UPDATE lead_requests
                SET notification_status = ?, notified_at = ?, notification_error = ?
                WHERE id = ?
                """,
                (status.strip() or "unknown", notified_at, error.strip(), lead_id),
            )
            conn.commit()

    def update_lead_status(self, lead_id: str, *, status: str, notes: str | None = None) -> bool:
        safe_status = normalize_lead_status(status)
        with closing(self._connect()) as conn:
            if notes is None:
                cursor = conn.execute(
                    "UPDATE lead_requests SET status = ? WHERE id = ?",
                    (safe_status, lead_id),
                )
            else:
                cursor = conn.execute(
                    "UPDATE lead_requests SET status = ?, notes = ? WHERE id = ?",
                    (safe_status, notes.strip(), lead_id),
                )
            conn.commit()
            return cursor.rowcount > 0

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in LEAD_STATUSES}
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM lead_requests GROUP BY status"
            ).fetchall()
        for row in rows:
            counts[normalize_lead_status(row["status"])] = int(row["count"] or 0)
        return counts

    def export_csv(self, limit: int = 500) -> str:
        safe_limit = max(1, min(limit, 2000))
        leads = self.list_leads(limit=safe_limit)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "created_at",
            "name",
            "email",
            "company",
            "vendors",
            "use_case",
            "message",
            "source",
            "status",
            "notes",
            "notification_status",
            "notified_at",
            "notification_error",
        ])
        for lead in leads:
            writer.writerow([
                lead.created_at,
                lead.name,
                lead.email,
                lead.company,
                lead.vendors,
                lead.use_case,
                lead.message,
                lead.source,
                lead.status,
                lead.notes,
                lead.notification_status,
                lead.notified_at,
                lead.notification_error,
            ])
        return output.getvalue()

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS lead_requests (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    company TEXT NOT NULL DEFAULT '',
                    use_case TEXT NOT NULL DEFAULT '',
                    vendors TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'demo',
                    status TEXT NOT NULL DEFAULT 'new',
                    notes TEXT NOT NULL DEFAULT '',
                    notification_status TEXT NOT NULL DEFAULT 'not_sent',
                    notified_at TEXT NOT NULL DEFAULT '',
                    notification_error TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_lead_requests_created_at
                    ON lead_requests(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_lead_requests_email
                    ON lead_requests(email);
                """
            )
            existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(lead_requests)").fetchall()}
            migrations = {
                "notes": "ALTER TABLE lead_requests ADD COLUMN notes TEXT NOT NULL DEFAULT ''",
                "notification_status": "ALTER TABLE lead_requests ADD COLUMN notification_status TEXT NOT NULL DEFAULT 'not_sent'",
                "notified_at": "ALTER TABLE lead_requests ADD COLUMN notified_at TEXT NOT NULL DEFAULT ''",
                "notification_error": "ALTER TABLE lead_requests ADD COLUMN notification_error TEXT NOT NULL DEFAULT ''",
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
    def _row_to_record(row: sqlite3.Row) -> LeadRecord:
        return LeadRecord(
            lead_id=row["id"],
            created_at=row["created_at"],
            name=row["name"],
            email=row["email"],
            company=row["company"],
            use_case=row["use_case"],
            vendors=row["vendors"],
            message=row["message"],
            source=row["source"],
            status=normalize_lead_status(row["status"]),
            notes=row["notes"],
            notification_status=row["notification_status"],
            notified_at=row["notified_at"],
            notification_error=row["notification_error"],
        )
