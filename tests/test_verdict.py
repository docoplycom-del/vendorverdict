import unittest

from vendorverdict.verdict import render_response


class VerdictRenderTests(unittest.TestCase):
    def test_response_includes_agent_workflow_section(self):
        response = render_response(
            "Compare Notion, Airtable, and Coda for storing client project data for a 10-person consulting startup in the UK.",
            use_live_evidence=False,
        )

        self.assertIn("Agent workflow completed:", response)
        self.assertIn("Parsed procurement intent", response)
        self.assertIn("Generated a ready-to-send due-diligence email", response)
