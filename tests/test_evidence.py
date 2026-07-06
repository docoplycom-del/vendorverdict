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

    @patch("requests.get")
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

    @patch("requests.get")
    def test_unknown_vendor_uses_source_discovery_before_live_checks(self, mock_get):
        def fake_response(url, **_kwargs):
            response = Mock()
            if url in {
                "https://northstarcrm.com",
                "https://northstarcrm.com/security",
                "https://northstarcrm.com/pricing",
                "https://northstarcrm.com/privacy",
                "https://northstarcrm.com/docs",
            }:
                response.status_code = 200
            elif url.startswith("https://northstarcrm.com/"):
                response.status_code = 404
            else:
                response.status_code = 404
            response.url = url
            response.headers = {"content-type": "text/html"}
            response.text = "SOC 2 GDPR SSO encryption data export"
            return response

        mock_get.side_effect = fake_response

        collector = EvidenceCollector(use_live_checks=True, timeout_seconds=0.1)
        evidence = collector.get("Northstar CRM")

        self.assertEqual(evidence.security_url, "https://northstarcrm.com/security")
        self.assertTrue(any(check.ok for check in evidence.source_checks))
        self.assertTrue(evidence.extracted_findings)
        self.assertTrue(any("Source discovery" in item for item in evidence.live_findings))

    @patch("requests.get")
    def test_source_discovery_fills_unknown_vendor_targets(self, mock_get):
        def response_for(url, **_kwargs):
            response = Mock()
            response.status_code = 200
            response.url = url
            response.headers = {"content-type": "text/html"}
            response.text = "SOC 2 encryption GDPR DPA SSO data export"
            return response

        mock_get.side_effect = response_for

        collector = EvidenceCollector(use_live_checks=True, use_source_discovery=True, timeout_seconds=0.01)
        evidence = collector.get("Acme CRM")

        self.assertTrue(evidence.source_checks)
        self.assertTrue(any(check.discovered for check in evidence.source_checks))
        self.assertTrue(any("Source Discovery Agent" in note for note in evidence.live_findings))


if __name__ == "__main__":
    unittest.main()
