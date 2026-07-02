from __future__ import annotations

import unittest

from vendorverdict.payment.fet_verifier import demo_payment_mode_enabled, fet_to_attofet
from vendorverdict.payment.premium_report import (
    render_payment_offer,
    render_premium_dossier,
    render_upgrade_cta,
    wants_premium_report,
)
from vendorverdict.payment.pricing import PREMIUM_VENDOR_DOSSIER


class PaymentTests(unittest.TestCase):
    def test_premium_detection(self):
        self.assertTrue(wants_premium_report("Upgrade this to a Premium Vendor Dossier"))
        self.assertTrue(wants_premium_report("Generate the board-ready risk register"))
        self.assertFalse(wants_premium_report("Compare Notion and Airtable for project data"))

    def test_paid_product_has_credible_price_and_description(self):
        self.assertEqual(PREMIUM_VENDOR_DOSSIER.sku, "premium_vendor_dossier")
        self.assertTrue(PREMIUM_VENDOR_DOSSIER.price_fet)
        self.assertIn("procurement", PREMIUM_VENDOR_DOSSIER.description.lower())

    def test_upgrade_cta_and_offer_explain_payment_value(self):
        self.assertIn("FET", render_upgrade_cta())
        offer = render_payment_offer("ref-123")
        self.assertIn("Payment Protocol", offer)
        self.assertIn("ref-123", offer)
        self.assertIn("risk register", offer)

    def test_premium_dossier_includes_paid_artifacts(self):
        report = render_premium_dossier(
            "Compare Notion, Airtable, and Coda for storing client project data for a 10-person consulting startup in the UK.",
            use_live_evidence=False,
        )
        self.assertIn("Premium Vendor Dossier", report)
        self.assertIn("Approval conditions", report)
        self.assertIn("Vendor risk register", report)
        self.assertIn("Rollout checklist", report)
        self.assertIn("Expanded due-diligence questions", report)

    def test_fet_unit_conversion(self):
        self.assertEqual(fet_to_attofet("0.05"), 50_000_000_000_000_000)
        self.assertIsInstance(demo_payment_mode_enabled(), bool)


if __name__ == "__main__":
    unittest.main()
