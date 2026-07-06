import unittest
from unittest.mock import Mock, patch

from vendorverdict.tools.evidence import EvidenceCollector


class EvidenceCollectorTests(unittest.TestCase):
    def test_can_disable_live_checks_for_reliable_fallback(self):
        collector = EvidenceCollector(use_live_checks=False)
        evidence = collector.get("Notion")
        self.assertEqual(evidence.name, "Notion")
        self.assertEqual(evidence.source_checks, ())
        self.assertEqual(evidence.live_findings, ())

    @patch("vendorverdict.tools.evidence.requests.get")
    def test_live_check_records_reachable_official_sources(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.url = "https://www.notion.com/security"
        response.headers = {"content-type": "text/html"}
        response.text = "SOC 2 encryption GDPR DPA SSO audit logs data export"
        mock_get.return_value = response

        collector = EvidenceCollector(use_live_checks=True, timeout_seconds=0.1)
        evidence = collector.get("Notion")

        self.assertGreaterEqual(len(evidence.source_checks), 1)
        self.assertTrue(any(check.ok for check in evidence.source_checks))
        self.assertTrue(evidence.live_findings)
        self.assertTrue(evidence.extracted_findings)


if __name__ == "__main__":
    unittest.main()
