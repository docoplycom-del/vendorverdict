from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from vendorverdict.storage import default_db_path


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
                       vendors, message, source, status
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
                       vendors, message, source, status
                FROM lead_requests
                WHERE id = ?
                """,
                (lead_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

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
                    status TEXT NOT NULL DEFAULT 'new'
                );

                CREATE INDEX IF NOT EXISTS idx_lead_requests_created_at
                    ON lead_requests(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_lead_requests_email
                    ON lead_requests(email);
                """
            )
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
            status=row["status"],
        )
