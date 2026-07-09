from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from vendorverdict.activity import ActivityStore, render_activity_csv, render_activity_markdown
from vendorverdict.api import app
from vendorverdict.customers import CustomerStore
from vendorverdict.leads import LeadStore
from vendorverdict.pilots import PilotStore
from vendorverdict.proposals import ProposalStore
from vendorverdict.shares import ShareStore
from vendorverdict.storage import ReportStore


class ActivityTimelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("VENDORVERDICT_API_DB_PATH")
        self.old_live = os.environ.get("VENDORVERDICT_API_LIVE_EVIDENCE")
        self.db_path = os.path.join(self.tmp.name, "activity.sqlite3")
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

    def test_activity_snapshot_collects_commercial_and_customer_events(self) -> None:
        self._seed_commercial_flow()
        snapshot = ActivityStore(self.db_path).build_snapshot(limit=50)

        titles = [item.title for item in snapshot.items]
        self.assertIn("Pilot request captured", titles)
        self.assertIn("Pilot workspace created", titles)
        self.assertIn("Commercial proposal created", titles)
        self.assertIn("Proposal marked sent", titles)
        self.assertIn("Payment marked received", titles)
        self.assertIn("Customer share link created", titles)
        self.assertIn("Customer account created", titles)
        self.assertIn("Customer check-in recorded", titles)
        self.assertGreaterEqual(snapshot.category_counts.get("Proposal", 0), 2)
        self.assertGreaterEqual(snapshot.category_counts.get("Customer", 0), 2)

        markdown = render_activity_markdown(snapshot)
        self.assertIn("VendorVerdict activity timeline", markdown)
        self.assertIn("Commercial proposal created", markdown)

        csv_text = render_activity_csv(snapshot)
        self.assertIn("occurred_at,category,title,detail,status,href", csv_text)
        self.assertIn("Payment marked received", csv_text)

    def test_activity_dashboard_and_exports_render(self) -> None:
        self._seed_commercial_flow()
        page = self.client.get("/dashboard/activity")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Activity timeline", page.text)
        self.assertIn("Pilot request captured", page.text)
        self.assertIn("Export Markdown", page.text)
        self.assertIn("Export CSV", page.text)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Activity timeline", dashboard.text)

        markdown = self.client.get("/dashboard/activity.md")
        self.assertEqual(markdown.status_code, 200)
        self.assertIn("text/markdown", markdown.headers["content-type"])
        self.assertIn("vendorverdict-activity-timeline.md", markdown.headers["content-disposition"])
        self.assertIn("VendorVerdict activity timeline", markdown.text)

        csv_response = self.client.get("/dashboard/activity.csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response.headers["content-type"])
        self.assertIn("vendorverdict-activity-timeline.csv", csv_response.headers["content-disposition"])
        self.assertIn("Payment marked received", csv_response.text)

    def test_empty_activity_timeline_is_safe(self) -> None:
        snapshot = ActivityStore(self.db_path).build_snapshot(limit=10)
        self.assertEqual(snapshot.total_count, 0)
        self.assertIn("No activity yet", render_activity_markdown(snapshot))

    def _seed_commercial_flow(self) -> str:
        lead_id = self.leads.save_lead(
            name="Sam Buyer",
            email="sam@example.com",
            company="Activity Co",
            vendors="Notion, Airtable",
            use_case="client data",
            source="pilot",
        )
        lead = self.leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        self.leads.update_notification_status(lead_id, status="sent")
        pilot_id = self.pilots.create_from_lead(lead, package="team", review_target=20)
        pilot = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)
        proposal_id = self.proposals.create_from_pilot(pilot)
        self.proposals.mark_sent(proposal_id, follow_up_due="2026-07-15")
        self.proposals.mark_paid(proposal_id, invoice_reference="INV-ACT-001")
        proposal = self.proposals.get_proposal(proposal_id)
        self.assertIsNotNone(proposal)
        self.shares.create_or_get("proposal", proposal_id, label=proposal.company)
        customer_id = self.customers.create_from_proposal(proposal)
        self.customers.mark_check_in_sent(customer_id, next_check_in_due="2026-07-22", health_status="healthy")
        return customer_id


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
