from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from vendorverdict.api import app
from vendorverdict.customer_success import build_customer_success_emails, build_customer_success_snapshot
from vendorverdict.customers import CustomerStore, normalize_customer_health
from vendorverdict.leads import LeadStore
from vendorverdict.pilots import PilotStore
from vendorverdict.proposals import ProposalStore


class CustomerSuccessWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("VENDORVERDICT_API_DB_PATH")
        self.old_live = os.environ.get("VENDORVERDICT_API_LIVE_EVIDENCE")
        self.db_path = os.path.join(self.tmp.name, "customer-success.sqlite3")
        os.environ["VENDORVERDICT_API_DB_PATH"] = self.db_path
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        self.client = TestClient(app)
        self.leads = LeadStore(self.db_path)
        self.pilots = PilotStore(self.db_path)
        self.proposals = ProposalStore(self.db_path)
        self.customers = CustomerStore(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        _restore_env("VENDORVERDICT_API_DB_PATH", self.old_db)
        _restore_env("VENDORVERDICT_API_LIVE_EVIDENCE", self.old_live)

    def test_customer_success_snapshot_and_email_templates(self) -> None:
        self.assertEqual(normalize_customer_health("Renewal Due"), "renewal_due")
        self.assertEqual(normalize_customer_health("bad"), "")
        customer_id = self._create_customer()
        self.customers.update_customer(
            customer_id,
            status="active",
            billing_status="current",
            package="team",
            review_allowance="40",
            renewal_date="2026-07-15",
            onboarding_notes="Renewal call needed.",
            internal_notes="Potential expansion account.",
            health_status="renewal_due",
            next_check_in_due="2026-07-20",
        )
        customer = self.customers.get_customer(customer_id)
        self.assertIsNotNone(customer)
        snapshot = build_customer_success_snapshot(customer, self.customers.list_reviews(customer_id))
        self.assertEqual(snapshot.health_status, "renewal_due")
        self.assertIn("renewal", snapshot.next_best_action.lower())

        emails = build_customer_success_emails(customer, snapshot)
        self.assertIn("VendorVerdict check-in", emails["check_in"].subject)
        self.assertIn("mailto:", emails["check_in"].mailto_url)
        self.assertIn("VendorVerdict renewal", emails["renewal"].subject)
        self.assertIn("Renewal date", emails["renewal"].body)

    def test_dashboard_shows_success_panel_and_marks_check_in_sent(self) -> None:
        customer_id = self._create_customer()
        detail = self.client.get(f"/dashboard/customers/{customer_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Customer success", detail.text)
        self.assertIn("Open check-in email", detail.text)
        self.assertIn("Open renewal email", detail.text)
        self.assertIn("Mark check-in sent", detail.text)

        response = self.client.post(
            f"/dashboard/customers/{customer_id}/check-in-sent",
            data={"health_status": "healthy", "next_check_in_due": "2026-08-01"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        refreshed = self.customers.get_customer(customer_id)
        self.assertIsNotNone(refreshed)
        self.assertEqual(refreshed.health_status, "healthy")
        self.assertEqual(refreshed.next_check_in_due, "2026-08-01")
        self.assertTrue(refreshed.last_check_in_at)

    def test_customer_success_markdown_export_and_customer_list_metrics(self) -> None:
        customer_id = self._create_customer()
        self.customers.update_customer(
            customer_id,
            status="active",
            billing_status="payment_due",
            package="team",
            review_allowance="40",
            renewal_date="2026-08-01",
            onboarding_notes="Need finance follow-up.",
            internal_notes="Watch billing.",
            health_status="at_risk",
            next_check_in_due="2020-01-01",
        )
        summary = self.client.get(f"/dashboard/customers/{customer_id}/success.md")
        self.assertEqual(summary.status_code, 200)
        self.assertIn("text/markdown", summary.headers["content-type"])
        self.assertIn("VendorVerdict customer success summary", summary.text)
        self.assertIn("Billing status", summary.text)
        self.assertIn("Next best action", summary.text)

        customers_page = self.client.get("/dashboard/customers")
        self.assertEqual(customers_page.status_code, 200)
        self.assertIn("at risk", customers_page.text)
        self.assertIn("check-ins due", customers_page.text)
        self.assertIn("2020-01-01", customers_page.text)

        csv_text = self.customers.export_csv()
        self.assertIn("health_status", csv_text)
        self.assertIn("next_check_in_due", csv_text)
        self.assertIn("at_risk", csv_text)

    def _create_customer(self) -> str:
        lead_id = self.leads.save_lead(
            name="Alex Customer",
            email="alex@example.com",
            company="Success Co",
            vendors="Notion, Airtable",
            use_case="client records",
        )
        lead = self.leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = self.pilots.create_from_lead(lead, package="team", review_target=20)
        pilot = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)
        proposal_id = self.proposals.create_from_pilot(pilot)
        self.assertTrue(self.proposals.mark_paid(proposal_id, invoice_reference="INV-SUCCESS-001"))
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
