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

    def test_single_vendor_audit_mode_does_not_ask_for_more_vendors(self):
        response = render_response(
            "Check Coda for storing client project data for a 10-person consulting startup in the UK.",
            use_live_evidence=False,
        )

        self.assertIn("SaaS Vendor Risk Review", response)
        self.assertIn("Review Coda for storing client project data", response)
        self.assertIn("Vendor decision:", response)
        self.assertIn("Risk scorecard:", response)
        self.assertIn("Hi Coda team", response)
        self.assertNotIn("Which vendors should I compare?", response)


if __name__ == "__main__":
    unittest.main()
