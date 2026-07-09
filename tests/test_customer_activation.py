from __future__ import annotations

import os
import re
import tempfile
import unittest

from fastapi.testclient import TestClient

from vendorverdict.api import app
from vendorverdict.customers import (
    CustomerStore,
    normalize_billing_status,
    normalize_customer_status,
)
from vendorverdict.leads import LeadStore
from vendorverdict.pilots import PilotStore
from vendorverdict.proposals import ProposalStore


class CustomerActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("VENDORVERDICT_API_DB_PATH")
        self.old_live = os.environ.get("VENDORVERDICT_API_LIVE_EVIDENCE")
        self.db_path = os.path.join(self.tmp.name, "customers.sqlite3")
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

    def test_customer_store_creates_and_updates_account_from_paid_proposal(self) -> None:
        self.assertEqual(normalize_customer_status("Active"), "active")
        self.assertEqual(normalize_customer_status("bad"), "onboarding")
        self.assertEqual(normalize_billing_status("Payment Due"), "payment_due")
        self.assertEqual(normalize_billing_status("bad"), "trial")

        proposal_id = self._create_paid_proposal()
        proposal = self.proposals.get_proposal(proposal_id)
        self.assertIsNotNone(proposal)

        customer_id = self.customers.create_from_proposal(proposal)
        customer = self.customers.get_customer(customer_id)
        self.assertIsNotNone(customer)
        self.assertEqual(customer.company, "Customer Co")
        self.assertEqual(customer.status, "active")
        self.assertEqual(customer.billing_status, "current")
        self.assertEqual(customer.package, "team")
        self.assertEqual(customer.review_allowance, 40)
        self.assertTrue(customer.renewal_date)
        self.assertIn("Payment recorded", customer.onboarding_notes)

        duplicate = self.customers.create_from_proposal(proposal)
        self.assertEqual(duplicate, customer_id)

        self.assertTrue(
            self.customers.update_customer(
                customer_id,
                status="paused",
                billing_status="overdue",
                package="custom",
                review_allowance="75",
                renewal_date="2026-08-01",
                onboarding_notes="Pause pending procurement review.",
                internal_notes="Call finance.",
            )
        )
        updated = self.customers.get_customer(customer_id)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "paused")
        self.assertEqual(updated.billing_status, "overdue")
        self.assertEqual(updated.review_allowance, 75)
        self.assertEqual(updated.renewal_date, "2026-08-01")
        self.assertIn("Pause pending", updated.onboarding_notes)
        self.assertEqual(self.customers.status_counts()["paused"], 1)
        self.assertEqual(self.customers.billing_counts()["overdue"], 1)

        csv_text = self.customers.export_csv()
        self.assertIn("Customer Co", csv_text)
        self.assertIn("billing_status", csv_text)
        self.assertIn("overdue", csv_text)
        self.assertIn("75", csv_text)

    def test_dashboard_can_activate_customer_from_proposal(self) -> None:
        proposal_id = self._create_paid_proposal()
        proposal_page = self.client.get(f"/dashboard/proposals/{proposal_id}")
        self.assertEqual(proposal_page.status_code, 200)
        self.assertIn("Customer activation", proposal_page.text)
        self.assertIn("Create customer account", proposal_page.text)

        create_response = self.client.post(
            f"/dashboard/proposals/{proposal_id}/customer",
            data={"status": "active", "billing_status": "current", "review_allowance": "50", "renewal_date": "2026-08-15"},
            follow_redirects=False,
        )
        self.assertEqual(create_response.status_code, 303)
        self.assertRegex(create_response.headers["location"], r"/dashboard/customers/[0-9a-f-]+")

        detail = self.client.get(create_response.headers["location"])
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Customer workspace", detail.text)
        self.assertIn("Customer Co", detail.text)
        self.assertIn("50", detail.text)
        self.assertIn("reviews/month", detail.text)

        update = self.client.post(
            create_response.headers["location"] + "/update",
            data={
                "status": "active",
                "billing_status": "current",
                "package": "team",
                "review_allowance": "60",
                "renewal_date": "2026-09-01",
                "onboarding_notes": "First recurring batch scheduled.",
                "internal_notes": "Good expansion prospect.",
            },
            follow_redirects=False,
        )
        self.assertEqual(update.status_code, 303)

        updated = self.client.get(create_response.headers["location"])
        self.assertEqual(updated.status_code, 200)
        self.assertIn("First recurring batch scheduled.", updated.text)
        self.assertIn("Good expansion prospect.", updated.text)
        self.assertIn("60", updated.text)

        customers = self.client.get("/dashboard/customers")
        self.assertEqual(customers.status_code, 200)
        self.assertIn("Customer activation", customers.text)
        self.assertIn("Customer Co", customers.text)
        self.assertIn("billing current", customers.text)

        csv_export = self.client.get("/dashboard/customers.csv")
        self.assertEqual(csv_export.status_code, 200)
        self.assertIn("text/csv", csv_export.headers["content-type"])
        self.assertIn("vendorverdict-customers.csv", csv_export.headers["content-disposition"])
        self.assertIn("Customer Co", csv_export.text)
        self.assertIn("First recurring batch scheduled.", csv_export.text)

        refreshed_proposal = self.client.get(f"/dashboard/proposals/{proposal_id}")
        self.assertEqual(refreshed_proposal.status_code, 200)
        self.assertIn("Open customer account", refreshed_proposal.text)

    def _create_paid_proposal(self) -> str:
        lead_id = self.leads.save_lead(
            name="Taylor Buyer",
            email="taylor@example.com",
            company="Customer Co",
            vendors="Notion, Airtable",
            use_case="client records",
        )
        lead = self.leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = self.pilots.create_from_lead(lead, package="team", review_target=20)
        pilot = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)
        proposal_id = self.proposals.create_from_pilot(pilot)
        self.assertTrue(self.proposals.mark_paid(proposal_id, invoice_reference="INV-PAID-001"))
        return proposal_id


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
