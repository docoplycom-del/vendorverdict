import unittest
from unittest.mock import Mock, patch

from vendorverdict.tools.evidence import EvidenceCollector


class EvidenceDiscoveryIntegrationTests(unittest.TestCase):
    @patch("requests.get")
    def test_unknown_vendor_uses_source_discovery_then_live_checks(self, mock_get):
        def fake_get(url, **kwargs):
            response = Mock()
            response.url = url
            response.headers = {"content-type": "text/html"}
            response.text = "SOC 2 GDPR SSO MFA encryption data export status page"
            if url == "https://examplecrm.com":
                response.status_code = 200
            elif url in {
                "https://examplecrm.com/security",
                "https://examplecrm.com/pricing",
                "https://examplecrm.com/privacy",
                "https://examplecrm.com/docs",
            }:
                response.status_code = 200
            else:
                response.status_code = 404
            return response

        mock_get.side_effect = fake_get
        collector = EvidenceCollector(use_live_checks=True, timeout_seconds=0.01, use_source_discovery=True)
        evidence = collector.get("ExampleCRM")

        self.assertEqual(evidence.name, "ExampleCRM")
        self.assertTrue(evidence.source_discovery_notes)
        self.assertEqual(len(evidence.source_checks), 4)
        self.assertTrue(any("Source Discovery Agent" in note for note in evidence.live_findings))
        self.assertTrue(evidence.extracted_findings)


if __name__ == "__main__":
    unittest.main()
