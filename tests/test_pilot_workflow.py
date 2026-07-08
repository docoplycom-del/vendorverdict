from __future__ import annotations

import os
import tempfile
import unittest

from vendorverdict.leads import LeadStore
from vendorverdict.pilots import PilotStore, normalize_pilot_package, normalize_pilot_status


class PilotWorkflowStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "pilots.sqlite3")
        self.leads = LeadStore(self.db_path)
        self.pilots = PilotStore(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_pilot_from_lead_with_default_checklist(self) -> None:
        lead_id = self.leads.save_lead(
            name="Alex Buyer",
            email="alex@example.com",
            company="Example Consulting",
            vendors="Notion, Airtable",
            use_case="client project data",
        )
        lead = self.leads.get_lead(lead_id)
        self.assertIsNotNone(lead)

        pilot_id = self.pilots.create_from_lead(lead, package="team", review_target=30)
        pilot = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)
        self.assertEqual(pilot.company, "Example Consulting")
        self.assertEqual(pilot.package, "team")
        self.assertEqual(pilot.status, "planned")
        self.assertEqual(pilot.review_target, 30)
        self.assertGreaterEqual(pilot.total_tasks, 8)
        self.assertEqual(pilot.progress_percent, 0)

        tasks = self.pilots.list_tasks(pilot_id)
        self.assertTrue(any(task.task_key == "scope_call" for task in tasks))
        self.assertTrue(self.pilots.set_task_completed(pilot_id, "scope_call", True))
        updated = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.completed_tasks, 1)
        self.assertGreater(updated.progress_percent, 0)

    def test_pilot_status_package_and_csv(self) -> None:
        self.assertEqual(normalize_pilot_status("Active"), "active")
        self.assertEqual(normalize_pilot_status("unknown"), "planned")
        self.assertEqual(normalize_pilot_package("advisor"), "advisor")
        self.assertEqual(normalize_pilot_package("bad"), "founding")

        lead_id = self.leads.save_lead(name="Pat", email="pat@example.com", use_case="SaaS review")
        lead = self.leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = self.pilots.create_from_lead(lead)
        self.pilots.update_pilot(
            pilot_id,
            status="active",
            package="founding",
            objective="Run first pilot reviews",
            review_target="12",
            start_date="2026-07-10",
            end_date="2026-08-10",
            notes="Kickoff booked.",
        )
        pilot = self.pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)
        self.assertEqual(pilot.status, "active")
        self.assertEqual(self.pilots.status_counts()["active"], 1)
        csv_text = self.pilots.export_csv()
        self.assertIn("contact_name", csv_text)
        self.assertIn("Kickoff booked.", csv_text)


if __name__ == "__main__":
    unittest.main()
