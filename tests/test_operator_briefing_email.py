from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from vendorverdict.api import app
from vendorverdict.business_metrics import build_business_metrics_snapshot
from vendorverdict.operator_briefing import build_operator_briefing
from vendorverdict.operator_briefing_delivery import (
    BriefingDeliveryStore,
    build_operator_briefing_email,
    briefing_email_summary,
    send_operator_briefing_email,
)
from vendorverdict.proposal_email_delivery import ProposalEmailSettings
from vendorverdict.settings import SettingsStore


class OperatorBriefingEmailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "briefing-email.sqlite3")
        self.old_env = {key: os.environ.get(key) for key in ENV_KEYS}
        os.environ["VENDORVERDICT_API_DB_PATH"] = self.db_path
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        os.environ["VENDORVERDICT_AUTH_ENABLED"] = "0"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_build_briefing_email_and_mailto(self) -> None:
        snapshot = self._empty_snapshot()
        email = build_operator_briefing_email(
            snapshot,
            recipient="founder@example.com",
            public_url="https://vendorverdict.docoply.com",
        )
        self.assertIn("VendorVerdict operator briefing", email.subject)
        self.assertEqual(email.recipient, "founder@example.com")
        self.assertIn("Open the live briefing", email.body)
        self.assertIn("/dashboard/briefing", email.body)
        self.assertTrue(email.mailto_url.startswith("mailto:founder%40example.com"))
        self.assertIn("subject=", email.mailto_url)

    def test_delivery_store_records_attempts(self) -> None:
        store = BriefingDeliveryStore(self.db_path)
        delivery_id = store.record_delivery(
            status="sent",
            recipient="founder@example.com",
            subject="Daily briefing",
            detail="Sent",
            action_count=3,
            urgent_count=1,
        )
        records = store.list_deliveries()
        self.assertEqual(records[0].delivery_id, delivery_id)
        self.assertEqual(records[0].status, "sent")
        self.assertEqual(records[0].action_count, 3)
        self.assertEqual(records[0].urgent_count, 1)

    def test_send_uses_smtp_when_enabled(self) -> None:
        os.environ["VENDORVERDICT_BRIEFING_EMAIL_ENABLED"] = "1"
        snapshot = self._empty_snapshot()
        settings = ProposalEmailSettings(
            enabled=True,
            host="smtp.example.com",
            port=587,
            username="user",
            password="password",
            from_email="hello@example.com",
            from_name="VendorVerdict",
            starttls=True,
        )
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        smtp.send_message.return_value = {}
        with patch("vendorverdict.operator_briefing_delivery.smtplib.SMTP", return_value=smtp) as smtp_cls:
            result = send_operator_briefing_email(
                snapshot,
                recipient="founder@example.com",
                public_url="https://vendorverdict.docoply.com",
                settings=settings,
            )
        self.assertTrue(result.sent)
        smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=15)
        smtp.login.assert_called_once_with("user", "password")
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message["To"], "founder@example.com")
        self.assertIn("VendorVerdict operator briefing", message["Subject"])

    def test_dashboard_briefing_email_controls_and_send_route(self) -> None:
        SettingsStore(self.db_path).update_settings({"operator_email": "founder@example.com"})
        os.environ["VENDORVERDICT_BRIEFING_EMAIL_ENABLED"] = "1"
        os.environ["VENDORVERDICT_EMAIL_SEND_ENABLED"] = "1"
        os.environ["VENDORVERDICT_SMTP_HOST"] = "smtp.example.com"
        os.environ["VENDORVERDICT_SMTP_FROM"] = "hello@example.com"
        page = self.client.get("/dashboard/briefing")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Email this briefing", page.text)
        self.assertIn("Open briefing email", page.text)
        self.assertIn("founder@example.com", page.text)

        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        smtp.send_message.return_value = {}
        with patch("vendorverdict.operator_briefing_delivery.smtplib.SMTP", return_value=smtp):
            response = self.client.post("/dashboard/briefing/send", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("email=sent", response.headers["location"])
        records = BriefingDeliveryStore(self.db_path).list_deliveries()
        self.assertEqual(records[0].status, "sent")
        self.assertEqual(records[0].recipient, "founder@example.com")

    def test_summary_reports_missing_recipient_and_enablement(self) -> None:
        for key in ["VENDORVERDICT_BRIEFING_EMAIL_ENABLED", "VENDORVERDICT_BRIEFING_EMAIL_TO"]:
            os.environ.pop(key, None)
        summary = briefing_email_summary(
            operator_email="",
            smtp_settings=ProposalEmailSettings(enabled=False),
        )
        self.assertFalse(summary.enabled)
        self.assertIn("VENDORVERDICT_BRIEFING_EMAIL_ENABLED", summary.missing_fields)
        self.assertTrue(any("operator_email" in field for field in summary.missing_fields))

    @staticmethod
    def _empty_snapshot():
        metrics = build_business_metrics_snapshot(
            reports=[],
            leads=[],
            pilots=[],
            proposals=[],
            customers=[],
            share_count=0,
            check_ins_due_count=0,
        )
        return build_operator_briefing(metrics=metrics)


ENV_KEYS = [
    "VENDORVERDICT_API_DB_PATH",
    "VENDORVERDICT_API_LIVE_EVIDENCE",
    "VENDORVERDICT_AUTH_ENABLED",
    "VENDORVERDICT_BRIEFING_EMAIL_ENABLED",
    "VENDORVERDICT_BRIEFING_EMAIL_TO",
    "VENDORVERDICT_EMAIL_SEND_ENABLED",
    "VENDORVERDICT_SMTP_HOST",
    "VENDORVERDICT_SMTP_PORT",
    "VENDORVERDICT_SMTP_USERNAME",
    "VENDORVERDICT_SMTP_PASSWORD",
    "VENDORVERDICT_SMTP_FROM",
    "VENDORVERDICT_SMTP_FROM_NAME",
    "VENDORVERDICT_SMTP_STARTTLS",
    "VENDORVERDICT_SMTP_TIMEOUT_SECONDS",
]


if __name__ == "__main__":
    unittest.main()
