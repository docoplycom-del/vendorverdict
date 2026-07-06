from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vendorverdict.reporting import export_report_markdown
from vendorverdict.storage import ReportStore
from vendorverdict.tools.evidence import EvidenceCollector
from vendorverdict.verdict import build_vendor_verdict, render_verdict


DEMO_QUERY = (
    "Compare Notion, Airtable, and Coda for storing client project data for a "
    "10-person consulting startup in the UK."
)


class ReportStorageTests(unittest.TestCase):
    def _verdict_and_rendered(self):
        verdict = build_vendor_verdict(DEMO_QUERY, collector=EvidenceCollector(use_live_checks=False))
        rendered = render_verdict(verdict)
        return verdict, rendered

    def test_report_store_saves_and_reads_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ReportStore(Path(tmp) / "vendorverdict.sqlite3")
            verdict, rendered = self._verdict_and_rendered()
            report_id = store.save_report(verdict, rendered, metadata={"test": True})

            reports = store.list_reports()
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0]["id"], report_id)

            report = store.get_report(report_id)
            self.assertIsNotNone(report)
            assert report is not None
            self.assertEqual(report["recommendation"], "Notion")
            self.assertEqual(len(report["scores"]), 3)
            self.assertIn("VendorVerdict", report["rendered_response"])

    def test_report_store_records_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ReportStore(Path(tmp) / "vendorverdict.sqlite3")
            verdict, rendered = self._verdict_and_rendered()
            report_id = store.save_report(verdict, rendered)
            sources = store.list_sources(report_id)
            self.assertGreaterEqual(len(sources), 3)
            self.assertTrue(all(source["url"] for source in sources))
            self.assertTrue(all(source["source_type"] in {"fallback", "live_check"} for source in sources))

    def test_markdown_export_contains_evidence_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ReportStore(Path(tmp) / "vendorverdict.sqlite3")
            verdict, rendered = self._verdict_and_rendered()
            report_id = store.save_report(verdict, rendered)

            markdown = store.render_markdown(report_id)
            self.assertIn("# VendorVerdict Report", markdown)
            self.assertIn("## Evidence snapshot", markdown)
            self.assertIn("Notion", markdown)

            export_path = export_report_markdown(report_id, output_dir=Path(tmp) / "exports", store=store)
            self.assertTrue(export_path.exists())
            self.assertIn("VendorVerdict Report", export_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
