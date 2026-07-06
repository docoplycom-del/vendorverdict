import tempfile
import unittest
from pathlib import Path

from vendorverdict.models import EvidenceFinding, SourceCheck, VendorRequest, VendorScore, VendorVerdict
from vendorverdict.storage import ReportStore


class ReportFindingStorageTests(unittest.TestCase):
    def _verdict_with_findings(self):
        finding = EvidenceFinding(
            vendor="ExampleVendor",
            signal="soc_2",
            label="SOC 2",
            source_label="security",
            source_url="https://example.com/security",
            snippet="ExampleVendor maintains SOC 2 controls for its platform.",
            confidence="High",
            checked_at="2026-07-06T00:00:00+00:00",
        )
        check = SourceCheck(
            label="security",
            url="https://example.com/security",
            ok=True,
            status_code=200,
            note="reachable",
            findings=(finding,),
        )
        score = VendorScore(
            vendor="ExampleVendor",
            security=82,
            privacy=76,
            pricing_predictability=70,
            lock_in=68,
            sme_fit=78,
            operational_maturity=75,
            overall=76,
            confidence="High",
            evidence_urls=("https://example.com/security",),
            strengths=("Public trust material is available.",),
            risks=("Confirm plan-specific controls.",),
            source_checks=(check,),
            live_findings=("Extracted 1 evidence-backed signal: SOC 2.",),
            extracted_findings=(finding,),
        )
        request = VendorRequest(
            vendors=("ExampleVendor",),
            use_case="storing client project data",
            raw_query="Check ExampleVendor for client project data",
            data_sensitivity="medium-high",
        )
        return VendorVerdict(
            request=request,
            scores=(score,),
            recommendation=score,
            assumptions=("Data sensitivity is treated as medium-high.",),
            due_diligence_email="Hi ExampleVendor team, please confirm SOC 2.",
            confidence="High",
            collaboration_steps=("Evidence Agent extracted source-backed findings.",),
            critic_warnings=(),
        )

    def test_report_store_saves_extracted_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ReportStore(Path(tmp) / "vendorverdict.sqlite3")
            verdict = self._verdict_with_findings()
            report_id = store.save_report(verdict, "Rendered report with SOC 2 evidence")
            findings = store.list_findings(report_id)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["signal"], "soc_2")
            self.assertIn("SOC 2", findings[0]["snippet"])

    def test_markdown_export_contains_extracted_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ReportStore(Path(tmp) / "vendorverdict.sqlite3")
            verdict = self._verdict_with_findings()
            report_id = store.save_report(verdict, "Rendered report with SOC 2 evidence")
            markdown = store.render_markdown(report_id)
            self.assertIn("## Extracted evidence findings", markdown)
            self.assertIn("SOC 2", markdown)
            self.assertIn("https://example.com/security", markdown)


if __name__ == "__main__":
    unittest.main()
