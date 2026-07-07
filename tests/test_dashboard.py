from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from vendorverdict.api import app


class DashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("VENDORVERDICT_API_DB_PATH")
        self.old_export = os.environ.get("VENDORVERDICT_API_EXPORT_DIR")
        self.old_live = os.environ.get("VENDORVERDICT_API_LIVE_EVIDENCE")
        os.environ["VENDORVERDICT_API_DB_PATH"] = os.path.join(self.tmp.name, "dashboard.sqlite3")
        os.environ["VENDORVERDICT_API_EXPORT_DIR"] = os.path.join(self.tmp.name, "reports")
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        _restore_env("VENDORVERDICT_API_DB_PATH", self.old_db)
        _restore_env("VENDORVERDICT_API_EXPORT_DIR", self.old_export)
        _restore_env("VENDORVERDICT_API_LIVE_EVIDENCE", self.old_live)


    def test_public_landing_page_renders(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Evidence-backed vendor reviews", response.text)
        self.assertIn("Login to dashboard", response.text)

    def test_favicon_routes_are_available(self) -> None:
        ico = self.client.get("/favicon.ico")
        self.assertEqual(ico.status_code, 200)
        png = self.client.get("/favicon.png")
        self.assertEqual(png.status_code, 200)

    def test_dashboard_renders_empty_state(self) -> None:
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("VendorVerdict Dashboard", response.text)
        self.assertIn("No saved reports yet", response.text)
        self.assertIn("Start new vendor review", response.text)

    def test_new_review_form_renders(self) -> None:
        response = self.client.get("/reviews/new")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Create a vendor-risk report", response.text)
        self.assertIn("Generate report", response.text)
        self.assertIn("Vendors", response.text)
        self.assertIn("Use case", response.text)
        self.assertIn("medium-high", response.text)

    def test_dashboard_can_create_and_view_report(self) -> None:
        response = self.client.post(
            "/reviews/run",
            data={
                "query": "Compare Notion and Airtable for storing client project data for a 10-person consulting startup in the UK.",
                "export_markdown": "1",
                "export_pdf": "1",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        location = response.headers["location"]
        self.assertTrue(location.startswith("/dashboard/reports/"))

        detail = self.client.get(location)
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Notion vs Airtable", detail.text)
        self.assertIn("Recommendation: Notion", detail.text)
        self.assertIn("Download PDF", detail.text)
        self.assertIn("Multi-agent workflow", detail.text)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Notion vs Airtable", dashboard.text)


    def test_dashboard_guided_form_builds_review_query(self) -> None:
        response = self.client.post(
            "/reviews/run",
            data={
                "vendors": "Notion, Airtable",
                "use_case": "storing client project data",
                "team_size": "10",
                "region": "UK",
                "data_sensitivity": "medium-high",
                "export_pdf": "1",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        detail = self.client.get(response.headers["location"])
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Evidence-backed findings", detail.text)
        self.assertIn("Official-source snapshot", detail.text)

    def test_dashboard_shows_clarification_instead_of_saving_incomplete_request(self) -> None:
        response = self.client.post(
            "/reviews/run",
            data={"query": "Compare Notion and Airtable"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("needs clarification", response.text.lower())
        self.assertIn("Clarification response", response.text)


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
