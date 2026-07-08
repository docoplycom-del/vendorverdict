from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vendorverdict.storage import default_db_path

SHARE_RESOURCE_TYPES = ("report", "proposal")


@dataclass(frozen=True)
class ShareLink:
    token: str
    resource_type: str
    resource_id: str
    created_at: str
    updated_at: str
    label: str = ""
    is_active: bool = True
    view_count: int = 0
    last_viewed_at: str = ""

    def __getitem__(self, key: str) -> Any:
        mapping = {
            "token": self.token,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "label": self.label,
            "is_active": self.is_active,
            "view_count": self.view_count,
            "last_viewed_at": self.last_viewed_at,
        }
        return mapping[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


class ShareStore:
    """SQLite-backed share links for customer-safe public report/proposal views.

    Share links deliberately expose only customer-facing views. Tokens are unguessable,
    can be reused for the same resource, and can later be deactivated without deleting
    the underlying report or proposal record.
    """

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        self.db_path = Path(db_path or default_db_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def create_or_get(self, resource_type: str, resource_id: str, *, label: str = "") -> ShareLink:
        safe_type = _resource_type(resource_type)
        safe_id = (resource_id or "").strip()
        if not safe_id:
            raise ValueError("resource_id is required")
        existing = self.get_for_resource(safe_type, safe_id)
        if existing is not None:
            return existing

        now = datetime.now(UTC).isoformat()
        token = self._new_token()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO share_links (
                    token, resource_type, resource_id, created_at, updated_at,
                    label, is_active, view_count, last_viewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, 0, '')
                """,
                (token, safe_type, safe_id, now, now, (label or "").strip()),
            )
            conn.commit()
        created = self.get_share(token)
        if created is None:
            raise RuntimeError("share link was not persisted")
        return created

    def get_share(self, token: str) -> ShareLink | None:
        cleaned = (token or "").strip()
        if not cleaned:
            return None
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM share_links WHERE token = ? AND is_active = 1",
                (cleaned,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def get_for_resource(self, resource_type: str, resource_id: str) -> ShareLink | None:
        safe_type = _resource_type(resource_type)
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT * FROM share_links
                WHERE resource_type = ? AND resource_id = ? AND is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (safe_type, resource_id),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def record_view(self, token: str) -> bool:
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE share_links
                SET updated_at = ?, view_count = view_count + 1, last_viewed_at = ?
                WHERE token = ? AND is_active = 1
                """,
                (now, now, token),
            )
            conn.commit()
            return cursor.rowcount > 0

    def deactivate(self, token: str) -> bool:
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                "UPDATE share_links SET updated_at = ?, is_active = 0 WHERE token = ?",
                (now, token),
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_shares(self, limit: int = 100) -> list[ShareLink]:
        safe_limit = max(1, min(limit, 1000))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM share_links ORDER BY created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _new_token(self) -> str:
        for _ in range(5):
            token = secrets.token_urlsafe(24)
            if self.get_share(token) is None:
                return token
        raise RuntimeError("could not create unique share token")

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS share_links (
                    token TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    view_count INTEGER NOT NULL DEFAULT 0,
                    last_viewed_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_share_links_resource ON share_links(resource_type, resource_id);
                CREATE INDEX IF NOT EXISTS idx_share_links_created_at ON share_links(created_at DESC);
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ShareLink:
        return ShareLink(
            token=row["token"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            label=row["label"] or "",
            is_active=bool(row["is_active"]),
            view_count=int(row["view_count"] or 0),
            last_viewed_at=row["last_viewed_at"] or "",
        )


def _resource_type(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in SHARE_RESOURCE_TYPES:
        raise ValueError(f"unsupported share resource type: {value}")
    return normalized
