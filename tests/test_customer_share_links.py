from __future__ import annotations

import os
import re
import tempfile
import unittest

from fastapi.testclient import TestClient

from vendorverdict.api import app
from vendorverdict.leads import LeadStore
from vendorverdict.pilot_outcomes import build_pilot_outcome
from vendorverdict.pilots import PilotStore
from vendorverdict.proposals import ProposalStore
from vendorverdict.shares import ShareStore


class CustomerShareLinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_env = {
            "VENDORVERDICT_API_DB_PATH": os.environ.get("VENDORVERDICT_API_DB_PATH"),
            "VENDORVERDICT_API_EXPORT_DIR": os.environ.get("VENDORVERDICT_API_EXPORT_DIR"),
            "VENDORVERDICT_API_LIVE_EVIDENCE": os.environ.get("VENDORVERDICT_API_LIVE_EVIDENCE"),
            "VENDORVERDICT_AUTH_ENABLED": os.environ.get("VENDORVERDICT_AUTH_ENABLED"),
        }
        self.db_path = os.path.join(self.tmp.name, "shares.sqlite3")
        os.environ["VENDORVERDICT_API_DB_PATH"] = self.db_path
        os.environ["VENDORVERDICT_API_EXPORT_DIR"] = os.path.join(self.tmp.name, "reports")
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        os.environ.pop("VENDORVERDICT_AUTH_ENABLED", None)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_report_share_link_creates_public_customer_view_and_exports(self) -> None:
        sample = self.client.post("/reviews/sample", follow_redirects=False)
        self.assertEqual(sample.status_code, 303)
        report_path = sample.headers["location"]
        self.assertTrue(report_path.startswith("/dashboard/reports/"))

        detail_before = self.client.get(report_path)
        self.assertEqual(detail_before.status_code, 200)
        self.assertIn("Create share link", detail_before.text)

        create_share = self.client.post(f"{report_path}/share", follow_redirects=False)
        self.assertEqual(create_share.status_code, 303)
        self.assertEqual(create_share.headers["location"], report_path)

        detail_after = self.client.get(report_path)
        self.assertEqual(detail_after.status_code, 200)
        self.assertIn("Customer share link", detail_after.text)
        match = re.search(r'href="(/share/report/[A-Za-z0-9_-]+)"', detail_after.text)
        self.assertIsNotNone(match)
        share_path = match.group(1)

        shared = self.client.get(share_path)
        self.assertEqual(shared.status_code, 200)
        self.assertIn("Shared customer report", shared.text)
        self.assertIn("Download PDF", shared.text)
        self.assertIn("Scorecard", shared.text)

        markdown = self.client.get(f"{share_path}.md")
        self.assertEqual(markdown.status_code, 200)
        self.assertIn("VendorVerdict Report", markdown.text)

        pdf = self.client.get(f"{share_path}.pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.content[:4], b"%PDF")

        token = share_path.rsplit("/", 1)[-1]
        share = ShareStore(self.db_path).get_share(token)
        self.assertIsNotNone(share)
        self.assertGreaterEqual(share.view_count, 3)

    def test_proposal_share_link_creates_public_customer_view_and_exports(self) -> None:
        leads = LeadStore(self.db_path)
        pilots = PilotStore(self.db_path)
        proposals = ProposalStore(self.db_path)

        lead_id = leads.save_lead(
            name="Riley Sponsor",
            email="riley@example.com",
            company="Share Co",
            vendors="Notion, Airtable",
            use_case="client records",
        )
        lead = leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = pilots.create_from_lead(lead, package="team", review_target=20)
        pilot = pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)
        outcome = build_pilot_outcome(pilot, pilots.list_tasks(pilot_id), pilots.list_reviews(pilot_id))
        proposal_id = proposals.create_from_pilot(pilot, outcome)

        proposal_path = f"/dashboard/proposals/{proposal_id}"
        detail_before = self.client.get(proposal_path)
        self.assertEqual(detail_before.status_code, 200)
        self.assertIn("Create share link", detail_before.text)

        create_share = self.client.post(f"{proposal_path}/share", follow_redirects=False)
        self.assertEqual(create_share.status_code, 303)
        self.assertEqual(create_share.headers["location"], proposal_path)

        detail_after = self.client.get(proposal_path)
        self.assertEqual(detail_after.status_code, 200)
        match = re.search(r'href="(/share/proposal/[A-Za-z0-9_-]+)"', detail_after.text)
        self.assertIsNotNone(match)
        share_path = match.group(1)

        shared = self.client.get(share_path)
        self.assertEqual(shared.status_code, 200)
        self.assertIn("Shared customer proposal", shared.text)
        self.assertIn("Share Co", shared.text)
        self.assertIn("Download PDF", shared.text)
        self.assertNotIn("Internal notes", shared.text)

        markdown = self.client.get(f"{share_path}.md")
        self.assertEqual(markdown.status_code, 200)
        self.assertIn("VendorVerdict proposal for Share Co", markdown.text)

        pdf = self.client.get(f"{share_path}.pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.content[:4], b"%PDF")

    def test_share_store_reuses_active_tokens_and_tracks_views(self) -> None:
        shares = ShareStore(self.db_path)
        first = shares.create_or_get("report", "report-123", label="Example report")
        second = shares.create_or_get("report", "report-123", label="Example report")
        self.assertEqual(first.token, second.token)
        self.assertEqual(second.view_count, 0)
        self.assertTrue(shares.record_view(second.token))
        viewed = shares.get_share(second.token)
        self.assertIsNotNone(viewed)
        self.assertEqual(viewed.view_count, 1)
        self.assertTrue(viewed.last_viewed_at)


if __name__ == "__main__":
    unittest.main()
