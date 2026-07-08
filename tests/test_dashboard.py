from __future__ import annotations

import os
from pathlib import Path
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


    def test_public_demo_page_renders(self) -> None:
        response = self.client.get("/demo")
        self.assertEqual(response.status_code, 200)
        self.assertIn("30-second customer demo", response.text)
        self.assertIn("Sample vendor review", response.text)
        self.assertIn("Ranked scorecard", response.text)
        self.assertIn("Due-diligence email", response.text)


    def test_public_pilot_request_form_renders(self) -> None:
        response = self.client.get("/pilot")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Request a pilot", response.text)
        self.assertIn("Vendors you are considering", response.text)

    def test_demo_page_contains_lead_capture_form(self) -> None:
        response = self.client.get("/demo")
        self.assertEqual(response.status_code, 200)
        self.assertIn('action="/leads/request"', response.text)
        self.assertIn("Request pilot", response.text)

    def test_lead_form_saves_request_and_dashboard_lists_it(self) -> None:
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
        self.assertTrue(response.headers["location"].startswith("/pilot/thanks"))

        thanks = self.client.get(response.headers["location"])
        self.assertEqual(thanks.status_code, 200)
        self.assertIn("pilot request was saved", thanks.text)

        leads = self.client.get("/dashboard/leads")
        self.assertEqual(leads.status_code, 200)
        self.assertIn("Alex Buyer", leads.text)
        self.assertIn("alex@example.com", leads.text)
        self.assertIn("Example Consulting", leads.text)

    def test_invalid_lead_form_returns_errors(self) -> None:
        response = self.client.post("/leads/request", data={"name": "A", "email": "bad"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Enter a valid email address", response.text)

    def test_dashboard_can_run_sample_review(self) -> None:
        response = self.client.post("/reviews/sample", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["location"].startswith("/dashboard/reports/"))

        detail = self.client.get(response.headers["location"])
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Notion vs Airtable vs Coda", detail.text)
        self.assertIn("Download PDF", detail.text)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Run sample review", dashboard.text)

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

class ContrastCssTests(unittest.TestCase):
    def test_demo_and_lead_capture_contrast_rules_are_present(self):
        css = Path("src/vendorverdict/web/static/style.css").read_text(encoding="utf-8")
        self.assertIn("--vv-action-bg", css)
        self.assertIn("--vv-field-bg", css)
        self.assertIn("--vv-field-placeholder", css)
        self.assertIn("html body .container a.button", css)
        self.assertIn("html body .form-card textarea", css)
        self.assertIn("html body .callout", css)

    def test_stylesheet_is_versioned_to_break_browser_cache(self):
        template = Path("src/vendorverdict/web/templates/base.html").read_text(encoding="utf-8")
        self.assertIn("style.css?v=20260708-visual-contrast-final", template)
