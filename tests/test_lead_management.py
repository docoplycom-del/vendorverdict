from __future__ import annotations

import os
import tempfile
import unittest

from vendorverdict.leads import LeadStore, normalize_lead_status


class LeadManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "leads.sqlite3")
        self.store = LeadStore(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_status_update_notes_and_counts(self) -> None:
        lead_id = self.store.save_lead(
            name="Alex Buyer",
            email="alex@example.com",
            company="Example Ltd",
            vendors="Notion, Airtable",
            use_case="client data",
        )
        self.assertEqual(self.store.status_counts()["new"], 1)

        updated = self.store.update_lead_status(
            lead_id,
            status="qualified",
            notes="Strong pilot fit.",
        )
        self.assertTrue(updated)
        lead = self.store.get_lead(lead_id)
        self.assertIsNotNone(lead)
        self.assertEqual(lead.status, "qualified")
        self.assertEqual(lead.notes, "Strong pilot fit.")
        self.assertEqual(self.store.status_counts()["qualified"], 1)

    def test_csv_export_contains_follow_up_fields(self) -> None:
        lead_id = self.store.save_lead(name="Pat", email="pat@example.com", vendors="Slack", use_case="team chat")
        self.store.update_lead_status(lead_id, status="contacted", notes="Sent LinkedIn follow-up.")
        csv_text = self.store.export_csv()
        self.assertIn("created_at,name,email,company,vendors,use_case,message,source,status,notes", csv_text)
        self.assertIn("pat@example.com", csv_text)
        self.assertIn("contacted", csv_text)
        self.assertIn("Sent LinkedIn follow-up.", csv_text)

    def test_invalid_status_normalizes_to_new(self) -> None:
        self.assertEqual(normalize_lead_status("unknown"), "new")
        self.assertEqual(normalize_lead_status("Contacted"), "contacted")


if __name__ == "__main__":
    unittest.main()
