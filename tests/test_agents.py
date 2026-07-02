import unittest

from vendorverdict.agents import VendorVerdictMultiAgentOrchestrator
from vendorverdict.tools.evidence import EvidenceCollector


class MultiAgentCollaborationTests(unittest.TestCase):
    def test_orchestrator_records_specialist_agent_steps(self):
        orchestrator = VendorVerdictMultiAgentOrchestrator(
            collector=EvidenceCollector(use_live_checks=False)
        )
        verdict = orchestrator.run(
            "Compare Notion, Airtable, and Coda for storing client project data for a 10-person consulting startup in the UK."
        )

        joined_steps = "\n".join(verdict.collaboration_steps)
        self.assertIn("Procurement Intent Agent", joined_steps)
        self.assertIn("Evidence Agent", joined_steps)
        self.assertIn("Risk Scoring Agent", joined_steps)
        self.assertIn("Recommendation Agent", joined_steps)
        self.assertIn("Email Agent", joined_steps)
        self.assertIn("Critic Agent", joined_steps)
        self.assertEqual(verdict.recommendation.vendor, "Notion")

    def test_orchestrator_preserves_clarifying_questions(self):
        orchestrator = VendorVerdictMultiAgentOrchestrator(
            collector=EvidenceCollector(use_live_checks=False)
        )
        verdict = orchestrator.run("Compare Notion and Airtable")

        self.assertIn("use_case", verdict.request.missing_fields)
        self.assertEqual(verdict.scores, ())
        self.assertEqual(verdict.confidence, "Low")


if __name__ == "__main__":
    unittest.main()
