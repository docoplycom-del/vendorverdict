from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from vendorverdict.api import app
from vendorverdict.customers import CustomerStore
from vendorverdict.leads import LeadStore
from vendorverdict.pilots import PilotStore
from vendorverdict.proposals import ProposalStore


class CustomerReviewOperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("VENDORVERDICT_API_DB_PATH")
        self.old_live = os.environ.get("VENDORVERDICT_API_LIVE_EVIDENCE")
        self.db_path = os.path.join(self.tmp.name, "customer-reviews.sqlite3")
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

    def test_customer_store_links_reports_and_exports_usage_csv(self) -> None:
        customer_id = self._create_customer()
        self.assertEqual(self.customers.review_count(customer_id), 0)

        response = self.client.post(
            f"/dashboard/customers/{customer_id}/reviews/run",
            data={
                "label": "CRM renewal review",
                "vendors": "Notion, Airtable",
                "use_case": "storing client project data",
                "team_size": "12",
                "region": "UK",
                "data_sensitivity": "medium-high",
                "export_markdown": "1",
                "export_pdf": "1",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], f"/dashboard/customers/{customer_id}")

        customer = self.customers.get_customer(customer_id)
        self.assertIsNotNone(customer)
        self.assertEqual(customer.review_count, 1)
        self.assertEqual(customer.reviews_remaining, customer.review_allowance - 1)

        reviews = self.customers.list_reviews(customer_id)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].label, "CRM renewal review")
        self.assertIn("Notion", reviews[0].vendors)
        self.assertIn("Airtable", reviews[0].vendors)
        self.assertEqual(reviews[0].use_case, "storing client project data")
        self.assertTrue(reviews[0].recommended_vendor)

        detail = self.client.get(f"/dashboard/customers/{customer_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Run customer review", detail.text)
        self.assertIn("CRM renewal review", detail.text)
        self.assertIn("reviews remaining", detail.text)
        self.assertIn("View report", detail.text)

        customers = self.client.get("/dashboard/customers")
        self.assertEqual(customers.status_code, 200)
        self.assertIn("1/40 reviews", customers.text)
        self.assertIn("39 remaining", customers.text)

        csv_export = self.client.get(f"/dashboard/customers/{customer_id}/reviews.csv")
        self.assertEqual(csv_export.status_code, 200)
        self.assertIn("text/csv", csv_export.headers["content-type"])
        self.assertIn("vendorverdict-customer-reviews.csv", csv_export.headers["content-disposition"])
        self.assertIn("CRM renewal review", csv_export.text)
        self.assertIn("storing client project data", csv_export.text)

        accounts_csv = self.customers.export_csv()
        self.assertIn("reviews_used", accounts_csv)
        self.assertIn("reviews_remaining", accounts_csv)
        self.assertIn("Customer Ops Co", accounts_csv)

    def test_customer_review_form_returns_errors_for_incomplete_request(self) -> None:
        customer_id = self._create_customer()
        response = self.client.post(
            f"/dashboard/customers/{customer_id}/reviews/run",
            data={"label": "Incomplete customer review", "vendors": "", "use_case": ""},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Enter vendors and a use case", response.text)
        self.assertEqual(self.customers.review_count(customer_id), 0)

    def _create_customer(self) -> str:
        lead_id = self.leads.save_lead(
            name="Morgan Buyer",
            email="morgan@example.com",
            company="Customer Ops Co",
            vendors="Notion, Airtable",
            use_case="client records",
        )
        lead = self.leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = self.pilots.create_from_lead(lead, package="team", review_target=20)
        pilot = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)
        proposal_id = self.proposals.create_from_pilot(pilot)
        self.assertTrue(self.proposals.mark_paid(proposal_id, invoice_reference="INV-CUSTOMER-001"))
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
