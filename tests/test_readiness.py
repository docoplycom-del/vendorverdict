from __future__ import annotations

import unittest

from vendorverdict.readiness import build_readiness_snapshot


class ReadinessSnapshotTests(unittest.TestCase):
    def test_empty_workflow_shows_warnings_and_next_actions(self) -> None:
        snapshot = build_readiness_snapshot(
            report_count=0,
            lead_count=0,
            pilot_count=0,
            proposal_count=0,
            share_count=0,
            public_url="",
        )
        self.assertLess(snapshot.readiness_percent, 100)
        self.assertFalse(snapshot.is_pilot_ready)
        self.assertEqual(snapshot.headline, "Setup in progress")
        self.assertTrue(snapshot.next_actions)
        self.assertIn("Submit a test request", snapshot.next_actions[0].action)

    def test_populated_workflow_is_pilot_ready(self) -> None:
        snapshot = build_readiness_snapshot(
            report_count=1,
            lead_count=1,
            pilot_count=1,
            proposal_count=1,
            share_count=1,
            public_url="https://vendorverdict.docoply.com",
        )
        self.assertEqual(snapshot.readiness_percent, 100)
        self.assertTrue(snapshot.is_pilot_ready)
        self.assertEqual(snapshot.headline, "Pilot-ready")
        self.assertEqual(snapshot.next_actions, [])
