import unittest
from unittest.mock import Mock, patch

from vendorverdict.tools.source_discovery import (
    discover_vendor_sources,
    infer_base_urls,
    normalize_vendor_slug,
)


def _fake_response(url: str, status_code: int = 200, text: str = ""):
    response = Mock()
    response.status_code = status_code
    response.url = url
    response.text = text
    response.headers = {"content-type": "text/html"}
    return response


class SourceDiscoveryTests(unittest.TestCase):
    def test_normalize_vendor_slug_handles_common_names(self):
        self.assertEqual(normalize_vendor_slug("Acme CRM Inc."), "acmecrm")
        self.assertEqual(normalize_vendor_slug("example.io"), "example.io")

    def test_infer_base_urls_prefers_configured_domains(self):
        bases = infer_base_urls("Acme CRM", ["https://trust.acme.com/security"])
        self.assertEqual(bases[0], "https://trust.acme.com")
        self.assertIn("https://www.acmecrm.com", bases)

    @patch("vendorverdict.tools.source_discovery.requests.get")
    def test_discovers_missing_privacy_from_configured_base(self, mock_get):
        def side_effect(url, **kwargs):
            if url == "https://example.com/privacy":
                return _fake_response(url, status_code=200)
            return _fake_response(url, status_code=404)

        mock_get.side_effect = side_effect
        discovered = discover_vendor_sources(
            "Example",
            configured_urls={"security": "https://example.com/security", "pricing": "", "privacy": "", "docs": ""},
            labels=("privacy",),
            timeout_seconds=0.01,
        )
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].label, "privacy")
        self.assertEqual(discovered[0].url, "https://example.com/privacy")


if __name__ == "__main__":
    unittest.main()
