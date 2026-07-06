from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vendorverdict.reporting import export_report_pdf
from vendorverdict.storage import ReportStore
from vendorverdict.tools.evidence import EvidenceCollector
from vendorverdict.verdict import build_vendor_verdict, render_verdict


DEMO_QUERY = (
    "Compare Notion, Airtable, and Coda for storing client project data for a "
    "10-person consulting startup in the UK."
)


class PdfExportTests(unittest.TestCase):
    def _stored_report(self, tmp: str):
        store = ReportStore(Path(tmp) / "vendorverdict.sqlite3")
        verdict = build_vendor_verdict(DEMO_QUERY, collector=EvidenceCollector(use_live_checks=False))
        rendered = render_verdict(verdict)
        report_id = store.save_report(verdict, rendered)
        return store, report_id

    def test_pdf_export_creates_valid_pdf_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, report_id = self._stored_report(tmp)
            pdf_path = export_report_pdf(report_id, output_dir=Path(tmp) / "exports", store=store)

            self.assertTrue(pdf_path.exists())
            pdf_bytes = pdf_path.read_bytes()
            self.assertTrue(pdf_bytes.startswith(b"%PDF"))
            self.assertGreater(len(pdf_bytes), 2000)

    def test_pdf_export_raises_for_missing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ReportStore(Path(tmp) / "vendorverdict.sqlite3")
            with self.assertRaises(KeyError):
                export_report_pdf("missing-report", output_dir=Path(tmp) / "exports", store=store)


if __name__ == "__main__":
    unittest.main()
