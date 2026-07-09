from __future__ import annotations

import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from vendorverdict.api import app
from vendorverdict.activity import ActivityStore
from vendorverdict.business_metrics import build_business_metrics_snapshot
from vendorverdict.customers import CustomerStore
from vendorverdict.leads import LeadStore
from vendorverdict.operator_briefing import build_operator_briefing, render_operator_briefing_markdown
from vendorverdict.pilots import PilotStore
from vendorverdict.proposals import ProposalStore
from vendorverdict.shares import ShareStore
from vendorverdict.storage import ReportStore


class OperatorBriefingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("VENDORVERDICT_API_DB_PATH")
        self.old_live = os.environ.get("VENDORVERDICT_API_LIVE_EVIDENCE")
        self.db_path = os.path.join(self.tmp.name, "briefing.sqlite3")
        os.environ["VENDORVERDICT_API_DB_PATH"] = self.db_path
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        self.client = TestClient(app)
        self.reports = ReportStore(self.db_path)
        self.leads = LeadStore(self.db_path)
        self.pilots = PilotStore(self.db_path)
        self.proposals = ProposalStore(self.db_path)
        self.customers = CustomerStore(self.db_path)
        self.shares = ShareStore(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        _restore_env("VENDORVERDICT_API_DB_PATH", self.old_db)
        _restore_env("VENDORVERDICT_API_LIVE_EVIDENCE", self.old_live)

    def test_operator_briefing_prioritizes_due_actions(self) -> None:
        self._seed_due_flow()
        customers = self.customers.list_customers(limit=100)
        metrics = build_business_metrics_snapshot(
            reports=self.reports.list_reports(limit=1000),
            leads=self.leads.list_leads(limit=1000),
            pilots=self.pilots.list_pilots(limit=1000),
            proposals=self.proposals.list_proposals(limit=1000),
            customers=customers,
            share_count=len(self.shares.list_shares(limit=1000)),
            check_ins_due_count=self.customers.check_in_due_count(),
        )
        activity = ActivityStore(self.db_path).build_snapshot(limit=25)
        snapshot = build_operator_briefing(
            metrics=metrics,
            activity_items=activity.items,
            leads=self.leads.list_leads(limit=1000),
            pilots=self.pilots.list_pilots(limit=1000),
            proposals=self.proposals.list_proposals(limit=1000),
            customers=customers,
        )

        titles = [action.title for action in snapshot.priority_actions]
        self.assertTrue(any("Follow up proposal" in title for title in titles))
        self.assertTrue(any(("Check payment status" in title) or ("Resolve overdue payment" in title) for title in titles))
        self.assertTrue(any("at-risk customer" in title.lower() for title in titles))
        self.assertEqual(snapshot.health_label, "Needs attention")
        self.assertGreaterEqual(snapshot.urgent_count, 2)

        markdown = render_operator_briefing_markdown(snapshot)
        self.assertIn("VendorVerdict operator briefing", markdown)
        self.assertIn("Priority actions", markdown)
        self.assertIn("Follow up proposal", markdown)

    def test_operator_briefing_dashboard_and_export_render(self) -> None:
        self._seed_due_flow()
        page = self.client.get("/dashboard/briefing")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Operator briefing", page.text)
        self.assertIn("Priority queue", page.text)
        self.assertIn("Export Markdown", page.text)
        self.assertIn("Follow up proposal", page.text)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Operator briefing", dashboard.text)

        markdown = self.client.get("/dashboard/briefing.md")
        self.assertEqual(markdown.status_code, 200)
        self.assertIn("text/markdown", markdown.headers["content-type"])
        self.assertIn("vendorverdict-operator-briefing.md", markdown.headers["content-disposition"])
        self.assertIn("VendorVerdict operator briefing", markdown.text)

    def test_empty_operator_briefing_is_safe(self) -> None:
        metrics = build_business_metrics_snapshot(
            reports=[],
            leads=[],
            pilots=[],
            proposals=[],
            customers=[],
            share_count=0,
            check_ins_due_count=0,
        )
        snapshot = build_operator_briefing(metrics=metrics)
        self.assertEqual(snapshot.health_label, "Build pipeline")
        self.assertIn("next serious pilot conversation", render_operator_briefing_markdown(snapshot))

    def _seed_due_flow(self) -> None:
        lead_id = self.leads.save_lead(
            name="Sam Buyer",
            email="sam@example.com",
            company="Briefing Co",
            vendors="Notion, Airtable",
            use_case="client data",
            source="pilot",
        )
        lead = self.leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = self.pilots.create_from_lead(lead, package="team", review_target=20)
        pilot = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)
        proposal_id = self.proposals.create_from_pilot(pilot)
        today = datetime.now(UTC).date()
        self.proposals.mark_sent(proposal_id, follow_up_due=today.isoformat())
        self.proposals.mark_invoice_sent(
            proposal_id,
            payment_due=(today - timedelta(days=1)).isoformat(),
            invoice_reference="INV-BRIEF-001",
        )
        proposal = self.proposals.get_proposal(proposal_id)
        self.assertIsNotNone(proposal)
        self.shares.create_or_get("proposal", proposal_id, label=proposal.company)
        customer_id = self.customers.create_from_proposal(proposal, billing_status="payment_due")
        self.customers.update_customer(
            customer_id,
            status="active",
            billing_status="payment_due",
            package="team",
            review_allowance="40",
            renewal_date=today.isoformat(),
            onboarding_notes="Initial customer account.",
            internal_notes="Needs attention.",
            health_status="at_risk",
            next_check_in_due=today.isoformat(),
        )


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
