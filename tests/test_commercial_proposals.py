from __future__ import annotations

import os
import tempfile
import unittest

from vendorverdict.leads import LeadStore
from vendorverdict.pilot_outcomes import build_pilot_outcome
from vendorverdict.pilots import PilotStore
from vendorverdict.proposal_pdf import export_proposal_pdf, format_proposal_date
from vendorverdict.proposals import (
    ProposalStore,
    build_proposal_email,
    normalize_proposal_package,
    normalize_proposal_status,
    customer_next_step,
    customer_success_criteria,
    render_proposal_markdown,
)
from vendorverdict.storage import ReportStore
from vendorverdict.tools.evidence import EvidenceCollector
from vendorverdict.verdict import build_vendor_verdict, render_verdict


class CommercialProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "commercial-proposals.sqlite3")
        self.leads = LeadStore(self.db_path)
        self.pilots = PilotStore(self.db_path)
        self.reports = ReportStore(self.db_path)
        self.proposals = ProposalStore(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_update_export_and_render_commercial_proposal(self) -> None:
        self.assertEqual(normalize_proposal_status("Negotiation"), "negotiation")
        self.assertEqual(normalize_proposal_status("bad"), "draft")
        self.assertEqual(normalize_proposal_package("Team"), "team")
        self.assertEqual(normalize_proposal_package("bad"), "starter")

        lead_id = self.leads.save_lead(
            name="Morgan Buyer",
            email="morgan@example.com",
            company="Proposal Co",
            vendors="Notion, Airtable",
            use_case="client project data",
        )
        lead = self.leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = self.pilots.create_from_lead(lead, package="team", review_target=2)
        pilot = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)

        query = "Compare Notion and Airtable for client project data for a 10-person UK consulting team."
        verdict = build_vendor_verdict(query, collector=EvidenceCollector(use_live_checks=False))
        report_id = self.reports.save_report(verdict, render_verdict(verdict), raw_query=query)
        self.assertTrue(self.pilots.link_report(pilot_id, report_id, label="Client data shortlist"))

        updated_pilot = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(updated_pilot)
        outcome = build_pilot_outcome(
            updated_pilot,
            self.pilots.list_tasks(pilot_id),
            self.pilots.list_reviews(pilot_id),
        )
        proposal_id = self.proposals.create_from_pilot(updated_pilot, outcome)
        proposal = self.proposals.get_proposal(proposal_id)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.company, "Proposal Co")
        self.assertEqual(proposal.package, "team")
        self.assertEqual(proposal.status, "draft")
        self.assertIn("£1,000", proposal.proposed_price)
        self.assertNotIn("1/2 reviews", proposal.success_criteria)
        self.assertIn("up to 2 recurring SaaS review decisions", proposal.success_criteria)
        self.assertIn("recommended vendor approach", proposal.success_criteria)
        self.assertNotIn("Review why Notion", proposal.success_criteria)
        self.assertIn("review the pilot outcome", proposal.next_step)

        duplicate = self.proposals.create_from_pilot(updated_pilot, outcome)
        self.assertEqual(duplicate, proposal_id)

        self.assertTrue(
            self.proposals.update_proposal(
                proposal_id,
                status="sent",
                package="team",
                proposed_price="£1,250/month",
                billing="Monthly after pilot.",
                scope="Recurring vendor reviews.",
                success_criteria="Decision records created before tool adoption.",
                next_step="Book a close-out call.",
                notes="Sent to Morgan.",
            )
        )
        updated = self.proposals.get_proposal(proposal_id)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "sent")
        self.assertEqual(self.proposals.status_counts()["sent"], 1)

        email = build_proposal_email(updated)
        self.assertIn("VendorVerdict next step", email.subject)
        self.assertIn("£1,250/month", email.body)

        markdown = render_proposal_markdown(updated)
        self.assertIn("VendorVerdict proposal", markdown)
        self.assertIn("Recurring vendor reviews", markdown)
        self.assertNotIn("Follow-up email draft", markdown)
        self.assertNotIn("Internal notes", markdown)

        self.assertEqual(format_proposal_date("2026-07-08T10:26:15.864861+00:00"), "8 July 2026")
        customer_criteria = customer_success_criteria("- Pilot delivery baseline: 1/20 reviews delivered and 62% checklist completion.\n- Use the close-out discussion to confirm why Notion was recommended most often and what evidence gaps remain.\n- Customer objective: Storing client data")
        self.assertNotIn("1/20 reviews", customer_criteria)
        self.assertNotIn("Notion was recommended", customer_criteria)
        self.assertIn("recommended vendor approach", customer_criteria)
        self.assertIn("Customer objective", customer_criteria)
        polished_next_step = customer_next_step("Book a 30-minute commercial close-out call, resolve the remaining pilot actions, and agree the recurring package.")
        self.assertIn("review the pilot outcome", polished_next_step)
        self.assertNotIn("remaining pilot actions", polished_next_step)

        pdf_path = export_proposal_pdf(proposal_id, output_dir=self.tmp.name, store=self.proposals)
        self.assertTrue(os.path.exists(pdf_path))
        with open(pdf_path, "rb") as handle:
            self.assertEqual(handle.read(4), b"%PDF")
        self.assertIn("vendorverdict-commercial-proposal", os.path.basename(pdf_path))

        csv_text = self.proposals.export_csv()
        self.assertIn("Proposal Co", csv_text)
        self.assertIn("£1,250/month", csv_text)


if __name__ == "__main__":
    unittest.main()
