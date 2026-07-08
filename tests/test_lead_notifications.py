from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from vendorverdict.api import app
from vendorverdict.lead_notifications import (
    LeadNotificationResult,
    LeadNotificationSettings,
    format_lead_notification,
    get_lead_notification_settings,
)
from vendorverdict.leads import LeadRecord, LeadStore


class LeadNotificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_env = {key: os.environ.get(key) for key in LEAD_NOTIFY_ENV_KEYS}
        os.environ["VENDORVERDICT_API_DB_PATH"] = os.path.join(self.tmp.name, "leads.sqlite3")
        os.environ["VENDORVERDICT_API_EXPORT_DIR"] = os.path.join(self.tmp.name, "reports")
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        os.environ["VENDORVERDICT_AUTH_ENABLED"] = "0"
        os.environ["VENDORVERDICT_LEAD_NOTIFY_ENABLED"] = "0"
        os.environ.pop("VENDORVERDICT_LEAD_WEBHOOK_URL", None)
        os.environ.pop("VENDORVERDICT_ALERT_WEBHOOK_URL", None)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_settings_can_reuse_monitor_alert_webhook(self) -> None:
        os.environ["VENDORVERDICT_LEAD_NOTIFY_ENABLED"] = "1"
        os.environ["VENDORVERDICT_ALERT_WEBHOOK_URL"] = "https://hooks.example/monitor"
        os.environ["VENDORVERDICT_ALERT_WEBHOOK_FORMAT"] = "discord"

        settings = get_lead_notification_settings()

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.webhook_url, "https://hooks.example/monitor")
        self.assertEqual(settings.webhook_format, "discord")

    def test_format_lead_notification_contains_actionable_context(self) -> None:
        lead = LeadRecord(
            lead_id="lead-123",
            created_at="2026-07-07T21:00:00+00:00",
            name="Alex Buyer",
            email="alex@example.com",
            company="Example Consulting",
            use_case="storing client project data",
            vendors="Notion, Airtable",
            message="Please send pilot details.",
            source="demo",
            status="new",
        )
        body = format_lead_notification(
            lead,
            app_base_url="https://vendorverdict.docoply.com",
            settings=LeadNotificationSettings(
                enabled=True,
                name="VendorVerdict lead capture",
                webhook_url="https://hooks.example/lead",
                webhook_format="generic",
                email_to="",
                email_from="vendorverdict@docoply.com",
                timeout_seconds=10,
            ),
        )

        self.assertIn("Alex Buyer", body)
        self.assertIn("alex@example.com", body)
        self.assertIn("Notion, Airtable", body)
        self.assertIn("https://vendorverdict.docoply.com/dashboard/leads", body)

    def test_lead_submission_records_notification_status(self) -> None:
        os.environ["VENDORVERDICT_LEAD_NOTIFY_ENABLED"] = "1"
        os.environ["VENDORVERDICT_LEAD_WEBHOOK_URL"] = "https://hooks.example/lead"
        with patch(
            "vendorverdict.api.send_lead_notification",
            return_value=LeadNotificationResult(status="sent", message="Lead notification sent via webhook."),
        ) as notify:
            response = self.client.post(
                "/leads/request",
                data={
                    "name": "Alex Buyer",
                    "email": "alex@example.com",
                    "company": "Example Consulting",
                    "vendors": "Notion, Airtable",
                    "use_case": "storing client project data",
                    "message": "We want a pilot.",
                    "source": "demo",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        notify.assert_called_once()
        leads = LeadStore(os.environ["VENDORVERDICT_API_DB_PATH"]).list_leads()
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].notification_status, "sent")
        self.assertEqual(leads[0].notification_error, "Lead notification sent via webhook.")

        inbox = self.client.get("/dashboard/leads")
        self.assertEqual(inbox.status_code, 200)
        self.assertIn("sent", inbox.text)

    def test_lead_submission_does_not_fail_when_notification_is_skipped(self) -> None:
        response = self.client.post(
            "/leads/request",
            data={"name": "Pat Prospect", "email": "pat@example.com", "vendors": "Notion, Airtable", "source": "demo"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        leads = LeadStore(os.environ["VENDORVERDICT_API_DB_PATH"]).list_leads()
        self.assertEqual(leads[0].notification_status, "skipped")


LEAD_NOTIFY_ENV_KEYS = [
    "VENDORVERDICT_API_DB_PATH",
    "VENDORVERDICT_API_EXPORT_DIR",
    "VENDORVERDICT_API_LIVE_EVIDENCE",
    "VENDORVERDICT_AUTH_ENABLED",
    "VENDORVERDICT_LEAD_NOTIFY_ENABLED",
    "VENDORVERDICT_LEAD_NOTIFY_NAME",
    "VENDORVERDICT_LEAD_WEBHOOK_URL",
    "VENDORVERDICT_LEAD_WEBHOOK_FORMAT",
    "VENDORVERDICT_LEAD_EMAIL_TO",
    "VENDORVERDICT_LEAD_EMAIL_FROM",
    "VENDORVERDICT_LEAD_NOTIFY_TIMEOUT_SECONDS",
    "VENDORVERDICT_ALERT_WEBHOOK_URL",
    "VENDORVERDICT_ALERT_WEBHOOK_FORMAT",
    "VENDORVERDICT_PUBLIC_URL",
]


if __name__ == "__main__":
    unittest.main()
