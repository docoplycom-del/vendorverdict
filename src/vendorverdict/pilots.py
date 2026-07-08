from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from vendorverdict.leads import LeadRecord
from vendorverdict.storage import default_db_path


PILOT_STATUSES = ("planned", "active", "paused", "completed", "cancelled")
PILOT_PACKAGES = ("founding", "team", "advisor")

DEFAULT_PILOT_TASKS = [
    ("scope_call", "Book pilot scope call", "Setup"),
    ("confirm_package", "Confirm package, duration, and success criteria", "Setup"),
    ("define_risk_rubric", "Define risk priorities and scoring emphasis", "Workflow"),
    ("collect_vendor_list", "Collect first vendor list and use cases", "Workflow"),
    ("run_first_reports", "Run first 3–5 vendor reviews", "Delivery"),
    ("review_due_diligence", "Review due-diligence questions with customer", "Delivery"),
    ("export_artifacts", "Export PDF/Markdown reports for decision records", "Delivery"),
    ("final_review", "Hold end-of-pilot review and next-step decision", "Close"),
]


def normalize_pilot_status(value: str) -> str:
    normalized = (value or "").strip().lower().replace(" ", "_")
    return normalized if normalized in PILOT_STATUSES else "planned"


def normalize_pilot_package(value: str) -> str:
    normalized = (value or "").strip().lower().replace(" ", "_")
    return normalized if normalized in PILOT_PACKAGES else "founding"


@dataclass(frozen=True)
class PilotRecord:
    pilot_id: str
    created_at: str
    lead_id: str
    company: str
    contact_name: str
    contact_email: str
    package: str
    status: str
    objective: str
    review_target: int
    start_date: str = ""
    end_date: str = ""
    notes: str = ""
    completed_tasks: int = 0
    total_tasks: int = 0

    def __getitem__(self, key: str) -> Any:
        mapping = {
            "id": self.pilot_id,
            "pilot_id": self.pilot_id,
            "created_at": self.created_at,
            "lead_id": self.lead_id,
            "company": self.company,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "package": self.package,
            "status": self.status,
            "objective": self.objective,
            "review_target": self.review_target,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "notes": self.notes,
            "completed_tasks": self.completed_tasks,
            "total_tasks": self.total_tasks,
            "progress_percent": self.progress_percent,
        }
        return mapping[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    @property
    def progress_percent(self) -> int:
        if not self.total_tasks:
            return 0
        return round((self.completed_tasks / self.total_tasks) * 100)


@dataclass(frozen=True)
class PilotTask:
    task_key: str
    label: str
    category: str
    completed: bool
    completed_at: str = ""

    def __getitem__(self, key: str) -> Any:
        mapping = {
            "task_key": self.task_key,
            "label": self.label,
            "category": self.category,
            "completed": self.completed,
            "completed_at": self.completed_at,
        }
        return mapping[key]




@dataclass(frozen=True)
class PilotReview:
    pilot_id: str
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
            "pilot_id": self.pilot_id,
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

class PilotStore:
    """SQLite-backed pilot onboarding tracker."""

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        self.db_path = Path(db_path or default_db_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def create_from_lead(
        self,
        lead: LeadRecord,
        *,
        package: str = "founding",
        objective: str = "",
        review_target: int | str = 20,
        notes: str = "",
    ) -> str:
        existing = self.get_by_lead_id(lead.lead_id)
        if existing is not None:
            return existing.pilot_id

        pilot_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        safe_package = normalize_pilot_package(package)
        try:
            safe_target = int(review_target)
        except (TypeError, ValueError):
            safe_target = 20
        safe_target = max(1, min(safe_target, 200))
        safe_objective = (objective or lead.use_case or lead.message or "Run a focused SaaS vendor review pilot.").strip()

        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO pilots (
                    id, created_at, lead_id, company, contact_name, contact_email,
                    package, status, objective, review_target, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pilot_id,
                    created_at,
                    lead.lead_id,
                    lead.company,
                    lead.name,
                    lead.email,
                    safe_package,
                    "planned",
                    safe_objective,
                    safe_target,
                    notes.strip(),
                ),
            )
            for task_key, label, category in DEFAULT_PILOT_TASKS:
                conn.execute(
                    """
                    INSERT INTO pilot_tasks (pilot_id, task_key, label, category, completed, completed_at)
                    VALUES (?, ?, ?, ?, 0, '')
                    """,
                    (pilot_id, task_key, label, category),
                )
            conn.commit()
        return pilot_id

    def list_pilots(self, limit: int = 50) -> list[PilotRecord]:
        safe_limit = max(1, min(limit, 200))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT p.*, COALESCE(t.total_tasks, 0) AS total_tasks,
                       COALESCE(t.completed_tasks, 0) AS completed_tasks
                FROM pilots p
                LEFT JOIN (
                    SELECT pilot_id,
                           COUNT(*) AS total_tasks,
                           SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed_tasks
                    FROM pilot_tasks
                    GROUP BY pilot_id
                ) t ON t.pilot_id = p.id
                ORDER BY p.created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_pilot(self, pilot_id: str) -> PilotRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT p.*, COALESCE(t.total_tasks, 0) AS total_tasks,
                       COALESCE(t.completed_tasks, 0) AS completed_tasks
                FROM pilots p
                LEFT JOIN (
                    SELECT pilot_id,
                           COUNT(*) AS total_tasks,
                           SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed_tasks
                    FROM pilot_tasks
                    GROUP BY pilot_id
                ) t ON t.pilot_id = p.id
                WHERE p.id = ?
                """,
                (pilot_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def get_by_lead_id(self, lead_id: str) -> PilotRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT p.*, COALESCE(t.total_tasks, 0) AS total_tasks,
                       COALESCE(t.completed_tasks, 0) AS completed_tasks
                FROM pilots p
                LEFT JOIN (
                    SELECT pilot_id,
                           COUNT(*) AS total_tasks,
                           SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed_tasks
                    FROM pilot_tasks
                    GROUP BY pilot_id
                ) t ON t.pilot_id = p.id
                WHERE p.lead_id = ?
                LIMIT 1
                """,
                (lead_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def list_tasks(self, pilot_id: str) -> list[PilotTask]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT task_key, label, category, completed, completed_at
                FROM pilot_tasks
                WHERE pilot_id = ?
                ORDER BY rowid ASC
                """,
                (pilot_id,),
            ).fetchall()
        return [
            PilotTask(
                task_key=row["task_key"],
                label=row["label"],
                category=row["category"],
                completed=bool(row["completed"]),
                completed_at=row["completed_at"] or "",
            )
            for row in rows
        ]

    def update_pilot(
        self,
        pilot_id: str,
        *,
        status: str,
        package: str,
        objective: str,
        review_target: int | str,
        start_date: str = "",
        end_date: str = "",
        notes: str = "",
    ) -> bool:
        safe_status = normalize_pilot_status(status)
        safe_package = normalize_pilot_package(package)
        try:
            safe_target = int(review_target)
        except (TypeError, ValueError):
            safe_target = 20
        safe_target = max(1, min(safe_target, 200))
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE pilots
                SET status = ?, package = ?, objective = ?, review_target = ?,
                    start_date = ?, end_date = ?, notes = ?
                WHERE id = ?
                """,
                (
                    safe_status,
                    safe_package,
                    objective.strip(),
                    safe_target,
                    start_date.strip(),
                    end_date.strip(),
                    notes.strip(),
                    pilot_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def set_task_completed(self, pilot_id: str, task_key: str, completed: bool) -> bool:
        completed_at = datetime.now(UTC).isoformat() if completed else ""
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE pilot_tasks
                SET completed = ?, completed_at = ?
                WHERE pilot_id = ? AND task_key = ?
                """,
                (1 if completed else 0, completed_at, pilot_id, task_key),
            )
            conn.commit()
            return cursor.rowcount > 0

    def link_report(
        self,
        pilot_id: str,
        report_id: str,
        *,
        label: str = "",
        status: str = "completed",
        notes: str = "",
    ) -> bool:
        if self.get_pilot(pilot_id) is None:
            return False
        created_at = datetime.now(UTC).isoformat()
        safe_label = (label or "Pilot vendor review").strip()
        safe_status = (status or "completed").strip().lower().replace(" ", "_")
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO pilot_reviews (pilot_id, report_id, created_at, label, status, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(pilot_id, report_id) DO UPDATE SET
                    label = excluded.label,
                    status = excluded.status,
                    notes = excluded.notes
                """,
                (pilot_id, report_id, created_at, safe_label, safe_status, notes.strip()),
            )
            conn.commit()
        return True

    def list_reviews(self, pilot_id: str) -> list[PilotReview]:
        with closing(self._connect()) as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT pr.pilot_id, pr.report_id, pr.created_at, pr.label, pr.status, pr.notes,
                           r.raw_query, r.vendors_json, r.use_case, r.recommended_vendor, r.overall_confidence
                    FROM pilot_reviews pr
                    LEFT JOIN reports r ON r.id = pr.report_id
                    WHERE pr.pilot_id = ?
                    ORDER BY pr.created_at DESC
                    """,
                    (pilot_id,),
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table: reports" not in str(exc):
                    raise
                rows = conn.execute(
                    """
                    SELECT pilot_id, report_id, created_at, label, status, notes,
                           '' AS raw_query, '[]' AS vendors_json, '' AS use_case,
                           '' AS recommended_vendor, '' AS overall_confidence
                    FROM pilot_reviews
                    WHERE pilot_id = ?
                    ORDER BY created_at DESC
                    """,
                    (pilot_id,),
                ).fetchall()
        return [self._row_to_review(row) for row in rows]

    def review_count(self, pilot_id: str) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM pilot_reviews WHERE pilot_id = ?",
                (pilot_id,),
            ).fetchone()
        return int(row["count"] or 0) if row is not None else 0

    def export_reviews_csv(self, pilot_id: str) -> str:
        reviews = self.list_reviews(pilot_id)
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
        counts = {status: 0 for status in PILOT_STATUSES}
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS count FROM pilots GROUP BY status").fetchall()
        for row in rows:
            counts[normalize_pilot_status(row["status"])] = int(row["count"] or 0)
        return counts

    def export_csv(self, limit: int = 500) -> str:
        pilots = self.list_pilots(limit=limit)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "created_at", "company", "contact_name", "contact_email", "package", "status",
            "objective", "review_target", "start_date", "end_date", "notes", "progress_percent",
        ])
        for pilot in pilots:
            writer.writerow([
                pilot.created_at, pilot.company, pilot.contact_name, pilot.contact_email, pilot.package,
                pilot.status, pilot.objective, pilot.review_target, pilot.start_date, pilot.end_date,
                pilot.notes, pilot.progress_percent,
            ])
        return output.getvalue()

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS pilots (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    lead_id TEXT NOT NULL DEFAULT '',
                    company TEXT NOT NULL DEFAULT '',
                    contact_name TEXT NOT NULL DEFAULT '',
                    contact_email TEXT NOT NULL DEFAULT '',
                    package TEXT NOT NULL DEFAULT 'founding',
                    status TEXT NOT NULL DEFAULT 'planned',
                    objective TEXT NOT NULL DEFAULT '',
                    review_target INTEGER NOT NULL DEFAULT 20,
                    start_date TEXT NOT NULL DEFAULT '',
                    end_date TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS pilot_tasks (
                    pilot_id TEXT NOT NULL,
                    task_key TEXT NOT NULL,
                    label TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    completed INTEGER NOT NULL DEFAULT 0,
                    completed_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (pilot_id, task_key)
                );

                CREATE TABLE IF NOT EXISTS pilot_reviews (
                    pilot_id TEXT NOT NULL,
                    report_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'completed',
                    notes TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (pilot_id, report_id)
                );

                CREATE INDEX IF NOT EXISTS idx_pilots_created_at ON pilots(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_pilots_lead_id ON pilots(lead_id);
                CREATE INDEX IF NOT EXISTS idx_pilots_status ON pilots(status);
                CREATE INDEX IF NOT EXISTS idx_pilot_reviews_pilot_id ON pilot_reviews(pilot_id);
                CREATE INDEX IF NOT EXISTS idx_pilot_reviews_report_id ON pilot_reviews(report_id);
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_review(row: sqlite3.Row) -> PilotReview:
        vendors: tuple[str, ...] = ()
        vendors_json = row["vendors_json"] if "vendors_json" in row.keys() else None
        if vendors_json:
            try:
                vendors = tuple(json.loads(vendors_json))
            except (TypeError, ValueError):
                vendors = ()
        return PilotReview(
            pilot_id=row["pilot_id"],
            report_id=row["report_id"],
            created_at=row["created_at"],
            label=row["label"] or "Pilot vendor review",
            status=row["status"] or "completed",
            notes=row["notes"] or "",
            raw_query=row["raw_query"] or "",
            vendors=vendors,
            use_case=row["use_case"] or "",
            recommended_vendor=row["recommended_vendor"] or "",
            overall_confidence=row["overall_confidence"] or "",
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row | None) -> PilotRecord:
        if row is None:
            raise ValueError("Cannot convert empty row to PilotRecord")
        return PilotRecord(
            pilot_id=row["id"],
            created_at=row["created_at"],
            lead_id=row["lead_id"],
            company=row["company"],
            contact_name=row["contact_name"],
            contact_email=row["contact_email"],
            package=normalize_pilot_package(row["package"]),
            status=normalize_pilot_status(row["status"]),
            objective=row["objective"],
            review_target=int(row["review_target"] or 0),
            start_date=row["start_date"] or "",
            end_date=row["end_date"] or "",
            notes=row["notes"] or "",
            completed_tasks=int(row["completed_tasks"] or 0),
            total_tasks=int(row["total_tasks"] or 0),
        )
