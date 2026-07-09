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

from vendorverdict.storage import default_db_path


@dataclass(frozen=True)
class ActivityItem:
    occurred_at: str
    category: str
    title: str
    detail: str
    href: str = ""
    status: str = ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @property
    def occurred_date(self) -> str:
        return (self.occurred_at or "")[:10]


@dataclass(frozen=True)
class ActivitySnapshot:
    generated_at: str
    items: tuple[ActivityItem, ...]
    category_counts: dict[str, int]

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def latest_activity_at(self) -> str:
        return self.items[0].occurred_at if self.items else ""


class ActivityStore:
    """Read-only operating timeline built from existing VendorVerdict tables."""

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        self.db_path = Path(db_path or default_db_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def build_snapshot(self, *, limit: int = 100) -> ActivitySnapshot:
        safe_limit = max(1, min(limit, 500))
        items: list[ActivityItem] = []
        with closing(self._connect()) as conn:
            items.extend(self._report_items(conn, safe_limit))
            items.extend(self._lead_items(conn, safe_limit))
            items.extend(self._pilot_items(conn, safe_limit))
            items.extend(self._proposal_items(conn, safe_limit))
            items.extend(self._share_items(conn, safe_limit))
            items.extend(self._customer_items(conn, safe_limit))

        items.sort(key=lambda item: _sort_key(item.occurred_at), reverse=True)
        items = items[:safe_limit]
        counts: dict[str, int] = {}
        for item in items:
            counts[item.category] = counts.get(item.category, 0) + 1
        return ActivitySnapshot(
            generated_at=datetime.now(UTC).isoformat(),
            items=tuple(items),
            category_counts=dict(sorted(counts.items())),
        )

    def render_markdown(self, *, limit: int = 100) -> str:
        return render_activity_markdown(self.build_snapshot(limit=limit))

    def render_csv(self, *, limit: int = 500) -> str:
        return render_activity_csv(self.build_snapshot(limit=limit))

    def _report_items(self, conn: sqlite3.Connection, limit: int) -> list[ActivityItem]:
        if not _table_exists(conn, "reports"):
            return []
        rows = conn.execute(
            """
            SELECT id, created_at, vendors_json, use_case, recommended_vendor, overall_confidence
            FROM reports
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        items: list[ActivityItem] = []
        for row in rows:
            vendors = _json_list(row["vendors_json"])
            vendor_label = " vs ".join(vendors) if vendors else "Vendor review"
            recommendation = row["recommended_vendor"] or "Needs review"
            items.append(ActivityItem(
                occurred_at=row["created_at"],
                category="Report",
                title="Vendor report created",
                detail=f"{vendor_label} · {row['use_case'] or 'No use case'} · recommendation: {recommendation}",
                href=f"/dashboard/reports/{row['id']}",
                status=row["overall_confidence"] or "",
            ))
        return items

    def _lead_items(self, conn: sqlite3.Connection, limit: int) -> list[ActivityItem]:
        if not _table_exists(conn, "lead_requests"):
            return []
        rows = conn.execute(
            """
            SELECT id, created_at, name, company, email, vendors, use_case, source, status, notification_status, notified_at
            FROM lead_requests
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        items: list[ActivityItem] = []
        for row in rows:
            company = row["company"] or row["name"] or row["email"] or "Prospect"
            detail_bits = [company]
            if row["vendors"]:
                detail_bits.append(row["vendors"])
            if row["use_case"]:
                detail_bits.append(row["use_case"])
            if row["source"]:
                detail_bits.append(f"source: {row['source']}")
            items.append(ActivityItem(
                occurred_at=row["created_at"],
                category="Lead",
                title="Pilot request captured",
                detail=" · ".join(detail_bits),
                href=f"/dashboard/leads/{row['id']}",
                status=row["status"] or "new",
            ))
            if row["notified_at"]:
                items.append(ActivityItem(
                    occurred_at=row["notified_at"],
                    category="Lead",
                    title="Lead notification sent",
                    detail=f"{company} · notification status: {row['notification_status']}",
                    href=f"/dashboard/leads/{row['id']}",
                    status=row["notification_status"] or "sent",
                ))
        return items

    def _pilot_items(self, conn: sqlite3.Connection, limit: int) -> list[ActivityItem]:
        if not _table_exists(conn, "pilots"):
            return []
        rows = conn.execute(
            """
            SELECT id, created_at, company, contact_name, package, status, objective, review_target
            FROM pilots
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        items: list[ActivityItem] = [
            ActivityItem(
                occurred_at=row["created_at"],
                category="Pilot",
                title="Pilot workspace created",
                detail=f"{row['company'] or row['contact_name'] or 'Pilot'} · {row['package']} · target {row['review_target']} reviews · {row['objective']}",
                href=f"/dashboard/pilots/{row['id']}",
                status=row["status"] or "planned",
            )
            for row in rows
        ]
        if _table_exists(conn, "pilot_tasks"):
            task_rows = conn.execute(
                """
                SELECT pilot_id, label, category, completed_at
                FROM pilot_tasks
                WHERE completed = 1 AND completed_at <> ''
                ORDER BY completed_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            for row in task_rows:
                items.append(ActivityItem(
                    occurred_at=row["completed_at"],
                    category="Pilot",
                    title="Pilot checklist task completed",
                    detail=f"{row['label']} · {row['category']}",
                    href=f"/dashboard/pilots/{row['pilot_id']}",
                    status="completed",
                ))
        if _table_exists(conn, "pilot_reviews"):
            review_rows = conn.execute(
                """
                SELECT pilot_id, report_id, created_at, label, status
                FROM pilot_reviews
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            for row in review_rows:
                items.append(ActivityItem(
                    occurred_at=row["created_at"],
                    category="Pilot",
                    title="Pilot vendor review delivered",
                    detail=row["label"] or f"Report {row['report_id'][:8]}",
                    href=f"/dashboard/pilots/{row['pilot_id']}",
                    status=row["status"] or "completed",
                ))
        return items

    def _proposal_items(self, conn: sqlite3.Connection, limit: int) -> list[ActivityItem]:
        if not _table_exists(conn, "proposals"):
            return []
        rows = conn.execute(
            """
            SELECT id, created_at, updated_at, company, contact_name, package, status, proposed_price,
                   sent_at, follow_up_due, last_follow_up_at, payment_status, payment_due,
                   invoice_reference, paid_at
            FROM proposals
            ORDER BY updated_at DESC, created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        items: list[ActivityItem] = []
        for row in rows:
            company = row["company"] or row["contact_name"] or "Prospect"
            items.append(ActivityItem(
                occurred_at=row["created_at"],
                category="Proposal",
                title="Commercial proposal created",
                detail=f"{company} · {row['package']} · {row['proposed_price']}",
                href=f"/dashboard/proposals/{row['id']}",
                status=row["status"] or "draft",
            ))
            if row["sent_at"]:
                items.append(ActivityItem(
                    occurred_at=row["sent_at"],
                    category="Proposal",
                    title="Proposal marked sent",
                    detail=f"{company} · follow-up due {row['follow_up_due'] or 'not scheduled'}",
                    href=f"/dashboard/proposals/{row['id']}",
                    status="sent",
                ))
            if row["last_follow_up_at"]:
                items.append(ActivityItem(
                    occurred_at=row["last_follow_up_at"],
                    category="Proposal",
                    title="Proposal follow-up recorded",
                    detail=f"{company} · next follow-up {row['follow_up_due'] or 'not scheduled'}",
                    href=f"/dashboard/proposals/{row['id']}",
                    status="followed_up",
                ))
            if row["paid_at"]:
                items.append(ActivityItem(
                    occurred_at=row["paid_at"],
                    category="Payment",
                    title="Payment marked received",
                    detail=f"{company} · {row['invoice_reference'] or row['payment_status']}",
                    href=f"/dashboard/proposals/{row['id']}",
                    status="paid",
                ))
        if _table_exists(conn, "proposal_payment_events"):
            events = conn.execute(
                """
                SELECT event_id, created_at, proposal_id, event_type, status, detail
                FROM proposal_payment_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            for row in events:
                items.append(ActivityItem(
                    occurred_at=row["created_at"],
                    category="Payment",
                    title="Stripe payment event received",
                    detail=f"{row['event_type']} · {row['detail']}",
                    href=f"/dashboard/proposals/{row['proposal_id']}" if row["proposal_id"] else "",
                    status=row["status"] or "event",
                ))
        return items

    def _share_items(self, conn: sqlite3.Connection, limit: int) -> list[ActivityItem]:
        if not _table_exists(conn, "share_links"):
            return []
        rows = conn.execute(
            """
            SELECT token, resource_type, resource_id, created_at, label, view_count, last_viewed_at, is_active
            FROM share_links
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        items: list[ActivityItem] = []
        for row in rows:
            resource = row["resource_type"] or "resource"
            label = row["label"] or row["resource_id"]
            href = f"/share/{resource}/{row['token']}" if row["is_active"] else ""
            items.append(ActivityItem(
                occurred_at=row["created_at"],
                category="Share",
                title=f"Customer share link created",
                detail=f"{resource} · {label} · views: {row['view_count']}",
                href=href,
                status="active" if row["is_active"] else "inactive",
            ))
            if row["last_viewed_at"]:
                items.append(ActivityItem(
                    occurred_at=row["last_viewed_at"],
                    category="Share",
                    title="Customer share link viewed",
                    detail=f"{resource} · {label} · total views: {row['view_count']}",
                    href=href,
                    status="viewed",
                ))
        return items

    def _customer_items(self, conn: sqlite3.Connection, limit: int) -> list[ActivityItem]:
        if not _table_exists(conn, "customer_accounts"):
            return []
        rows = conn.execute(
            """
            SELECT id, created_at, updated_at, company, contact_name, package, status, billing_status,
                   renewal_date, health_status, last_check_in_at, next_check_in_due
            FROM customer_accounts
            ORDER BY updated_at DESC, created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        items: list[ActivityItem] = []
        for row in rows:
            company = row["company"] or row["contact_name"] or "Customer"
            items.append(ActivityItem(
                occurred_at=row["created_at"],
                category="Customer",
                title="Customer account created",
                detail=f"{company} · {row['package']} · {row['billing_status']} · renewal {row['renewal_date'] or 'not set'}",
                href=f"/dashboard/customers/{row['id']}",
                status=row["status"] or "onboarding",
            ))
            if row["last_check_in_at"]:
                items.append(ActivityItem(
                    occurred_at=row["last_check_in_at"],
                    category="Customer",
                    title="Customer check-in recorded",
                    detail=f"{company} · next check-in {row['next_check_in_due'] or 'not scheduled'} · health {row['health_status'] or 'not set'}",
                    href=f"/dashboard/customers/{row['id']}",
                    status="check_in_sent",
                ))
        if _table_exists(conn, "customer_reviews"):
            reviews = conn.execute(
                """
                SELECT customer_id, report_id, created_at, label, status
                FROM customer_reviews
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            for row in reviews:
                items.append(ActivityItem(
                    occurred_at=row["created_at"],
                    category="Customer",
                    title="Customer review delivered",
                    detail=row["label"] or f"Report {row['report_id'][:8]}",
                    href=f"/dashboard/customers/{row['customer_id']}",
                    status=row["status"] or "completed",
                ))
        return items

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def render_activity_markdown(snapshot: ActivitySnapshot) -> str:
    lines = [
        "# VendorVerdict activity timeline",
        "",
        f"Generated: {snapshot.generated_at}",
        f"Total recent activity items: {snapshot.total_count}",
        "",
        "## Category summary",
    ]
    if snapshot.category_counts:
        for category, count in snapshot.category_counts.items():
            lines.append(f"- {category}: {count}")
    else:
        lines.append("- No activity yet")
    lines.extend(["", "## Recent activity"])
    if not snapshot.items:
        lines.append("- No activity yet")
    for item in snapshot.items:
        suffix = f" — {item.detail}" if item.detail else ""
        status = f" ({item.status})" if item.status else ""
        lines.append(f"- {item.occurred_at} · **{item.title}**{suffix}{status}")
    return "\n".join(lines).strip() + "\n"


def render_activity_csv(snapshot: ActivitySnapshot) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["occurred_at", "category", "title", "detail", "status", "href"])
    for item in snapshot.items:
        writer.writerow([item.occurred_at, item.category, item.title, item.detail, item.status, item.href])
    return output.getvalue()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def _sort_key(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    if "T" not in cleaned and len(cleaned) == 10:
        return cleaned + "T00:00:00+00:00"
    return cleaned
