from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
import re
import tempfile
import unittest

from fastapi.testclient import TestClient

from vendorverdict.api import app
from vendorverdict.settings import SettingsStore


class AdminSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_env = {key: os.environ.get(key) for key in [
            "VENDORVERDICT_API_DB_PATH",
            "VENDORVERDICT_API_EXPORT_DIR",
            "VENDORVERDICT_API_LIVE_EVIDENCE",
            "VENDORVERDICT_PUBLIC_URL",
            "VENDORVERDICT_DEFAULT_REVIEW_REGION",
            "VENDORVERDICT_DEFAULT_DATA_SENSITIVITY",
            "VENDORVERDICT_DEFAULT_PROPOSAL_PRICE",
            "VENDORVERDICT_DEFAULT_PROPOSAL_BILLING",
            "VENDORVERDICT_DEFAULT_FOLLOW_UP_DAYS",
        ]}
        os.environ["VENDORVERDICT_API_DB_PATH"] = os.path.join(self.tmp.name, "settings.sqlite3")
        os.environ["VENDORVERDICT_API_EXPORT_DIR"] = os.path.join(self.tmp.name, "reports")
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_settings_page_renders_and_validates(self) -> None:
        response = self.client.get("/dashboard/settings")
        self.assertEqual(response.status_code, 200)
        self.assertIn("VendorVerdict settings", response.text)
        self.assertIn("Default proposal price", response.text)
        self.assertIn("Secrets stay outside the dashboard", response.text)

        invalid = self.client.post(
            "/dashboard/settings",
            data={
                "company_name": "VendorVerdict",
                "public_url": "vendorverdict.docoply.com",
                "default_review_region": "UK",
                "default_data_sensitivity": "medium",
                "default_proposal_price": "From £1,000/month after pilot",
                "default_proposal_billing": "Monthly subscription.",
                "default_follow_up_days": "7",
                "operator_email": "",
            },
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("Public URL must start", invalid.text)

    def test_saved_settings_feed_review_proposal_and_follow_up_defaults(self) -> None:
        saved = self.client.post(
            "/dashboard/settings",
            data={
                "company_name": "VendorVerdict",
                "public_url": "https://vendorverdict.example.com",
                "default_review_region": "EU",
                "default_data_sensitivity": "high",
                "default_proposal_price": "From £2,000/month after pilot",
                "default_proposal_billing": "Quarterly subscription after the paid pilot.",
                "default_follow_up_days": "5",
                "operator_email": "ops@example.com",
            },
            follow_redirects=False,
        )
        self.assertEqual(saved.status_code, 303)

        review_form = self.client.get("/reviews/new")
        self.assertEqual(review_form.status_code, 200)
        self.assertIn('value="EU"', review_form.text)
        self.assertIn('value="high"', review_form.text)

        self.client.post(
            "/leads/request",
            data={
                "name": "Morgan Buyer",
                "email": "morgan@example.com",
                "company": "Settings Co",
                "vendors": "Notion, Airtable",
                "use_case": "client data reviews",
                "source": "pilot",
            },
            follow_redirects=False,
        )
        inbox = self.client.get("/dashboard/leads")
        match = re.search(r'href="(/dashboard/leads/[^"]+)"[^>]*><strong>Morgan Buyer</strong>', inbox.text)
        self.assertIsNotNone(match)
        lead_path = match.group(1)
        pilot = self.client.post(
            f"{lead_path}/pilot",
            data={"package": "team", "review_target": "20", "objective": "client data reviews"},
            follow_redirects=False,
        )
        self.assertEqual(pilot.status_code, 303)
        proposal = self.client.post(f"{pilot.headers['location']}/proposal", follow_redirects=False)
        self.assertEqual(proposal.status_code, 303)
        proposal_page = self.client.get(proposal.headers["location"])
        self.assertEqual(proposal_page.status_code, 200)
        self.assertIn("From £2,000/month after pilot", proposal_page.text)
        self.assertIn("Quarterly subscription after the paid pilot.", proposal_page.text)

        mark_sent = self.client.post(
            f"{proposal.headers['location']}/delivery",
            data={"action": "mark_sent", "follow_up_due": ""},
            follow_redirects=False,
        )
        self.assertEqual(mark_sent.status_code, 303)
        expected_due = (datetime.now(UTC).date() + timedelta(days=5)).isoformat()
        updated = self.client.get(proposal.headers["location"])
        self.assertIn(expected_due, updated.text)

    def test_settings_store_uses_environment_defaults_and_can_reset(self) -> None:
        os.environ["VENDORVERDICT_DEFAULT_REVIEW_REGION"] = "US"
        store = SettingsStore(os.environ["VENDORVERDICT_API_DB_PATH"])
        self.assertEqual(store.get_settings().default_review_region, "US")
        store.update_settings({"default_review_region": "UK", "default_follow_up_days": "14"})
        self.assertEqual(store.get_settings().default_review_region, "UK")
        self.assertEqual(store.get_settings().follow_up_days_int, 14)
        store.reset_settings()
        self.assertEqual(store.get_settings().default_review_region, "US")


if __name__ == "__main__":
    unittest.main()
