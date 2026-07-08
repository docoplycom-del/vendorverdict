from __future__ import annotations

import os
import tempfile
import unittest

from vendorverdict.leads import LeadStore
from vendorverdict.pilots import PilotStore
from vendorverdict.storage import ReportStore
from vendorverdict.tools.evidence import EvidenceCollector
from vendorverdict.verdict import build_vendor_verdict, render_verdict


class PilotReviewDeliveryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "pilot-reviews.sqlite3")
        self.leads = LeadStore(self.db_path)
        self.pilots = PilotStore(self.db_path)
        self.reports = ReportStore(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_link_report_to_pilot_and_export_reviews_csv(self) -> None:
        lead_id = self.leads.save_lead(
            name="Alex Buyer",
            email="alex@example.com",
            company="Example Consulting",
            vendors="Notion, Airtable",
            use_case="client project data",
        )
        lead = self.leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = self.pilots.create_from_lead(lead, review_target=10)

        query = "Compare Notion and Airtable for client project data for a 10-person UK consulting team."
        verdict = build_vendor_verdict(query, collector=EvidenceCollector(use_live_checks=False))
        report_id = self.reports.save_report(
            verdict,
            render_verdict(verdict),
            raw_query=query,
            metadata={"pilot_id": pilot_id},
        )

        self.assertTrue(self.pilots.link_report(pilot_id, report_id, label="Client data review"))
        self.assertEqual(self.pilots.review_count(pilot_id), 1)
        reviews = self.pilots.list_reviews(pilot_id)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].report_id, report_id)
        self.assertEqual(reviews[0].label, "Client data review")
        self.assertIn("client project data", reviews[0].use_case)
        self.assertTrue(reviews[0].recommended_vendor)

        csv_text = self.pilots.export_reviews_csv(pilot_id)
        self.assertIn("Client data review", csv_text)
        self.assertIn(report_id, csv_text)
        self.assertIn("recommended_vendor", csv_text)


if __name__ == "__main__":
    unittest.main()
