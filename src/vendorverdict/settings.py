from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vendorverdict.storage import default_db_path


SETTING_DEFINITIONS: dict[str, dict[str, str]] = {
    "company_name": {
        "label": "Company / product name",
        "description": "Shown on admin pages and used as the default product name for customer workflows.",
        "env": "VENDORVERDICT_COMPANY_NAME",
        "default": "VendorVerdict",
    },
    "public_url": {
        "label": "Public URL",
        "description": "Used when generating lead follow-up links and customer share links.",
        "env": "VENDORVERDICT_PUBLIC_URL",
        "default": "",
    },
    "default_review_region": {
        "label": "Default review region",
        "description": "Pre-filled region on new vendor reviews and pilot reviews.",
        "env": "VENDORVERDICT_DEFAULT_REVIEW_REGION",
        "default": "UK",
    },
    "default_data_sensitivity": {
        "label": "Default data sensitivity",
        "description": "Pre-filled data sensitivity on new vendor reviews and pilot reviews.",
        "env": "VENDORVERDICT_DEFAULT_DATA_SENSITIVITY",
        "default": "medium",
    },
    "default_proposal_price": {
        "label": "Default proposal price",
        "description": "Default commercial starting point for new proposals created from pilots.",
        "env": "VENDORVERDICT_DEFAULT_PROPOSAL_PRICE",
        "default": "From £1,000/month after pilot",
    },
    "default_proposal_billing": {
        "label": "Default proposal billing text",
        "description": "Default billing wording for new proposals created from pilots.",
        "env": "VENDORVERDICT_DEFAULT_PROPOSAL_BILLING",
        "default": "Monthly or quarterly subscription after the paid pilot, depending on review volume and support needs.",
    },
    "default_follow_up_days": {
        "label": "Default follow-up days",
        "description": "Number of days after sending a proposal before the next follow-up is due.",
        "env": "VENDORVERDICT_DEFAULT_FOLLOW_UP_DAYS",
        "default": "7",
    },
    "operator_email": {
        "label": "Operator email",
        "description": "Internal contact shown on the settings page for admin reference.",
        "env": "VENDORVERDICT_OPERATOR_EMAIL",
        "default": "",
    },
}


@dataclass(frozen=True)
class AppSettings:
    company_name: str
    public_url: str
    default_review_region: str
    default_data_sensitivity: str
    default_proposal_price: str
    default_proposal_billing: str
    default_follow_up_days: str
    operator_email: str
    updated_at: str = ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def as_dict(self) -> dict[str, str]:
        return {
            "company_name": self.company_name,
            "public_url": self.public_url,
            "default_review_region": self.default_review_region,
            "default_data_sensitivity": self.default_data_sensitivity,
            "default_proposal_price": self.default_proposal_price,
            "default_proposal_billing": self.default_proposal_billing,
            "default_follow_up_days": self.default_follow_up_days,
            "operator_email": self.operator_email,
            "updated_at": self.updated_at,
        }

    @property
    def follow_up_days_int(self) -> int:
        try:
            value = int(str(self.default_follow_up_days).strip())
        except ValueError:
            return 7
        return max(0, min(value, 90))


class SettingsStore:
    """SQLite-backed runtime settings for non-secret product defaults.

    Secrets such as passwords, webhook URLs, API keys, and auth secrets intentionally remain in
    /etc/vendorverdict/vendorverdict.env. This store only keeps non-sensitive defaults that are
    useful to edit from the admin dashboard.
    """

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        self.db_path = Path(db_path or default_db_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def get_settings(self) -> AppSettings:
        values = self._default_values()
        latest_update = ""
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT key, value, updated_at FROM app_settings").fetchall()
        for row in rows:
            key = str(row["key"])
            if key in values:
                values[key] = str(row["value"] or "")
                latest_update = max(latest_update, str(row["updated_at"] or ""))
        return AppSettings(updated_at=latest_update, **values)

    def update_settings(self, values: dict[str, str]) -> AppSettings:
        cleaned = self._sanitize(values)
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            for key, value in cleaned.items():
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (key, value, now),
                )
            conn.commit()
        return self.get_settings()

    def reset_settings(self) -> AppSettings:
        with closing(self._connect()) as conn:
            conn.execute("DELETE FROM app_settings")
            conn.commit()
        return self.get_settings()

    def env_summary(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for key, definition in SETTING_DEFINITIONS.items():
            env_name = definition.get("env", "")
            if not env_name:
                continue
            rows.append(
                {
                    "key": key,
                    "env": env_name,
                    "is_set": "yes" if os.getenv(env_name) else "no",
                    "description": definition["description"],
                }
            )
        return rows

    def _default_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for key, definition in SETTING_DEFINITIONS.items():
            env_name = definition.get("env", "")
            values[key] = os.getenv(env_name, definition["default"]).strip()
        return values

    def _sanitize(self, values: dict[str, str]) -> dict[str, str]:
        current = self.get_settings().as_dict()
        cleaned: dict[str, str] = {}
        for key in SETTING_DEFINITIONS:
            value = values.get(key, current.get(key, ""))
            value = str(value or "").strip()
            if key == "public_url":
                value = value.rstrip("/")
            if key == "default_follow_up_days":
                try:
                    days = int(value)
                except ValueError:
                    days = 7
                value = str(max(0, min(days, 90)))
            cleaned[key] = value
        return cleaned

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
