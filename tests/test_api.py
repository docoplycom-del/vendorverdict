from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from vendorverdict.api import app


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("VENDORVERDICT_API_DB_PATH")
        self.old_export = os.environ.get("VENDORVERDICT_API_EXPORT_DIR")
        self.old_live = os.environ.get("VENDORVERDICT_LIVE_EVIDENCE")
        os.environ["VENDORVERDICT_API_DB_PATH"] = os.path.join(self.tmp.name, "api.sqlite3")
        os.environ["VENDORVERDICT_API_EXPORT_DIR"] = os.path.join(self.tmp.name, "reports")
        os.environ["VENDORVERDICT_LIVE_EVIDENCE"] = "0"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        _restore_env("VENDORVERDICT_API_DB_PATH", self.old_db)
        _restore_env("VENDORVERDICT_API_EXPORT_DIR", self.old_export)
        _restore_env("VENDORVERDICT_LIVE_EVIDENCE", self.old_live)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("specialist-agent workflow", data["checks"])

    def test_run_list_get_and_export_report(self) -> None:
        payload = {
            "query": "Compare Notion and Airtable for storing client project data for a 10-person consulting startup in the UK.",
            "live_evidence": False,
        }
        response = self.client.post("/reports/run", json=payload)
        self.assertEqual(response.status_code, 200)
        created = response.json()
        self.assertEqual(created["status"], "completed")
        self.assertIsNotNone(created["report_id"])
        report_id = created["report_id"]
        self.assertIn("markdown", created["links"])
        self.assertIn("pdf", created["links"])

        list_response = self.client.get("/reports")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()[0]["id"], report_id)

        detail_response = self.client.get(f"/reports/{report_id}")
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()
        self.assertEqual(detail["recommendation"], "Notion")
        self.assertIn("rendered_response", detail)
        self.assertIn("scores", detail)

        markdown_response = self.client.get(f"/reports/{report_id}/markdown")
        self.assertEqual(markdown_response.status_code, 200)
        self.assertIn("VendorVerdict Report", markdown_response.text)

        pdf_response = self.client.get(f"/reports/{report_id}/pdf")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.headers["content-type"], "application/pdf")
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))

    def test_missing_report_returns_404(self) -> None:
        response = self.client.get("/reports/missing-report-id")
        self.assertEqual(response.status_code, 404)

    def test_missing_use_case_returns_needs_clarification_without_saving(self) -> None:
        response = self.client.post("/reports/run", json={"query": "Compare Notion and Airtable", "live_evidence": False})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "needs_clarification")
        self.assertIsNone(data["report_id"])


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
