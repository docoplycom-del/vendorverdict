from __future__ import annotations

import os
import tempfile
import unittest

from vendorverdict.leads import LeadStore
from vendorverdict.pilot_outcomes import build_pilot_outcome, render_pilot_outcome_markdown
from vendorverdict.pilots import PilotStore
from vendorverdict.storage import ReportStore
from vendorverdict.tools.evidence import EvidenceCollector
from vendorverdict.verdict import build_vendor_verdict, render_verdict


class PilotOutcomeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "pilot-outcomes.sqlite3")
        self.leads = LeadStore(self.db_path)
        self.pilots = PilotStore(self.db_path)
        self.reports = ReportStore(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_builds_outcome_summary_and_markdown(self) -> None:
        lead_id = self.leads.save_lead(
            name="Casey Buyer",
            email="casey@example.com",
            company="Pilot Co",
            vendors="Notion, Airtable",
            use_case="client delivery records",
        )
        lead = self.leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = self.pilots.create_from_lead(lead, review_target=2)
        pilot = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)

        query = "Compare Notion and Airtable for client delivery records for a 10-person UK consulting team."
        verdict = build_vendor_verdict(query, collector=EvidenceCollector(use_live_checks=False))
        report_id = self.reports.save_report(verdict, render_verdict(verdict), raw_query=query)
        self.assertTrue(self.pilots.link_report(pilot_id, report_id, label="Client delivery shortlist"))
        self.assertTrue(self.pilots.set_task_completed(pilot_id, "scope_call", True))

        updated = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(updated)
        outcome = build_pilot_outcome(updated, self.pilots.list_tasks(pilot_id), self.pilots.list_reviews(pilot_id))

        self.assertEqual(outcome.company, "Pilot Co")
        self.assertEqual(outcome.review_count, 1)
        self.assertEqual(outcome.review_progress_percent, 50)
        self.assertTrue(outcome.success_signals)
        self.assertTrue(outcome.open_actions)
        self.assertIn("VendorVerdict pilot outcome", outcome.followup_email_subject)

        markdown = render_pilot_outcome_markdown(outcome)
        self.assertIn("# VendorVerdict pilot outcome: Pilot Co", markdown)
        self.assertIn("Client delivery shortlist", markdown)
        self.assertIn(report_id, markdown)
        self.assertIn("Follow-up email draft", markdown)


if __name__ == "__main__":
    unittest.main()
