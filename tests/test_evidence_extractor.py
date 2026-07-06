import unittest

from vendorverdict.tools.evidence_extractor import extract_evidence_findings, normalize_text, summarize_findings


class EvidenceExtractorTests(unittest.TestCase):
    def test_extracts_common_security_and_privacy_signals(self):
        page = """
        <html><body>
        Our platform maintains SOC 2 controls, encrypts data at rest and in transit,
        supports SSO, provides audit logs, and offers a GDPR Data Processing Agreement.
        Customers can export your data before account closure.
        </body></html>
        """
        findings = extract_evidence_findings(
            page,
            vendor="ExampleVendor",
            source_url="https://example.com/security",
            source_label="security",
            checked_at="2026-07-06T00:00:00+00:00",
        )
        signals = {finding.signal for finding in findings}
        self.assertIn("soc_2", signals)
        self.assertIn("encryption", signals)
        self.assertIn("sso", signals)
        self.assertIn("audit_logs", signals)
        self.assertIn("gdpr", signals)
        self.assertIn("dpa", signals)
        self.assertIn("data_export", signals)
        self.assertTrue(all(finding.snippet for finding in findings))

    def test_normalize_text_removes_markup_and_script(self):
        text = normalize_text("<script>ignore SOC 2</script><p>GDPR &amp; DPA</p>")
        self.assertNotIn("ignore SOC 2", text)
        self.assertIn("GDPR & DPA", text)

    def test_summarize_findings_is_readable(self):
        findings = extract_evidence_findings(
            "SOC 2 and ISO 27001",
            vendor="ExampleVendor",
            source_url="https://example.com/security",
            source_label="security",
        )
        summary = summarize_findings(findings)
        self.assertIn("Extracted", summary)
        self.assertIn("SOC 2", summary)


if __name__ == "__main__":
    unittest.main()
