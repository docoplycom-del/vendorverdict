from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from vendorverdict.api import app
from vendorverdict.business_metrics import build_business_metrics_snapshot, render_business_metrics_markdown
from vendorverdict.customers import CustomerStore
from vendorverdict.leads import LeadStore
from vendorverdict.pilots import PilotStore
from vendorverdict.proposals import ProposalStore
from vendorverdict.storage import ReportStore


class BusinessMetricsDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("VENDORVERDICT_API_DB_PATH")
        self.old_live = os.environ.get("VENDORVERDICT_API_LIVE_EVIDENCE")
        self.db_path = os.path.join(self.tmp.name, "metrics.sqlite3")
        os.environ["VENDORVERDICT_API_DB_PATH"] = self.db_path
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        self.client = TestClient(app)
        self.reports = ReportStore(self.db_path)
        self.leads = LeadStore(self.db_path)
        self.pilots = PilotStore(self.db_path)
        self.proposals = ProposalStore(self.db_path)
        self.customers = CustomerStore(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        _restore_env("VENDORVERDICT_API_DB_PATH", self.old_db)
        _restore_env("VENDORVERDICT_API_LIVE_EVIDENCE", self.old_live)

    def test_business_metrics_snapshot_tracks_funnel_and_actions(self) -> None:
        customer_id = self._seed_customer_account()
        self.customers.update_customer(
            customer_id,
            status="active",
            billing_status="current",
            package="team",
            review_allowance="40",
            renewal_date="2026-08-01",
            onboarding_notes="Active customer.",
            internal_notes="Weekly check-in needed.",
            health_status="at_risk",
            next_check_in_due="2020-01-01",
        )
        self.customers.link_report(customer_id, "report-demo-1", label="CRM review")
        self.leads.save_lead(
            name="New Buyer",
            email="new@example.com",
            company="New Co",
            vendors="Slack, Teams",
            use_case="internal collaboration",
        )

        snapshot = build_business_metrics_snapshot(
            reports=self.reports.list_reports(limit=1000),
            leads=self.leads.list_leads(limit=1000),
            pilots=self.pilots.list_pilots(limit=1000),
            proposals=self.proposals.list_proposals(limit=1000),
            customers=self.customers.list_customers(limit=1000),
            share_count=0,
            check_ins_due_count=self.customers.check_in_due_count(),
        )

        self.assertEqual(snapshot.lead_count, 2)
        self.assertEqual(snapshot.pilot_count, 1)
        self.assertEqual(snapshot.proposal_count, 1)
        self.assertEqual(snapshot.customer_count, 1)
        self.assertEqual(snapshot.paid_proposal_count, 1)
        self.assertEqual(snapshot.lead_to_pilot_rate, 50)
        self.assertEqual(snapshot.proposal_to_customer_rate, 100)
        self.assertEqual(snapshot.customer_review_count, 1)
        self.assertEqual(snapshot.check_ins_due_count, 1)
        self.assertTrue(any("new lead" in action.lower() for action in snapshot.next_actions))
        self.assertTrue(any("at-risk" in action.lower() for action in snapshot.next_actions))

        markdown = render_business_metrics_markdown(snapshot)
        self.assertIn("VendorVerdict business metrics", markdown)
        self.assertIn("Leads: 2", markdown)
        self.assertIn("Next actions", markdown)

    def test_metrics_dashboard_and_markdown_export_render(self) -> None:
        self._seed_customer_account()
        page = self.client.get("/dashboard/metrics")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Business metrics", page.text)
        self.assertIn("Lead-to-customer funnel", page.text)
        self.assertIn("Next best actions", page.text)
        self.assertIn("Export Markdown", page.text)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Business metrics", dashboard.text)

        export = self.client.get("/dashboard/metrics.md")
        self.assertEqual(export.status_code, 200)
        self.assertIn("text/markdown", export.headers["content-type"])
        self.assertIn("vendorverdict-business-metrics.md", export.headers["content-disposition"])
        self.assertIn("VendorVerdict business metrics", export.text)

    def _seed_customer_account(self) -> str:
        lead_id = self.leads.save_lead(
            name="Alex Customer",
            email="alex@example.com",
            company="Metrics Co",
            vendors="Notion, Airtable",
            use_case="client records",
        )
        lead = self.leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = self.pilots.create_from_lead(lead, package="team", review_target=20)
        pilot = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)
        proposal_id = self.proposals.create_from_pilot(pilot)
        self.assertTrue(self.proposals.mark_paid(proposal_id, invoice_reference="INV-METRICS-001"))
        proposal = self.proposals.get_proposal(proposal_id)
        self.assertIsNotNone(proposal)
        return self.customers.create_from_proposal(proposal)


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
