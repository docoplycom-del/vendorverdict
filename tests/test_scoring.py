import unittest

from vendorverdict.data_loader import load_fallback_vendors
from vendorverdict.models import VendorRequest
from vendorverdict.scoring import rank_vendors, score_vendor


class ScoringTests(unittest.TestCase):
    def test_score_is_bounded(self):
        vendors = load_fallback_vendors()
        request = VendorRequest(
            vendors=("Notion",),
            use_case="storing client project data",
            raw_query="Compare Notion for client data",
            data_sensitivity="medium-high",
        )
        score = score_vendor(vendors["notion"], request)
        self.assertGreaterEqual(score.overall, 0)
        self.assertLessEqual(score.overall, 100)

    def test_rank_vendors_returns_descending_scores(self):
        vendors = load_fallback_vendors()
        request = VendorRequest(
            vendors=("Notion", "Airtable", "Coda"),
            use_case="storing client project data",
            raw_query="Compare Notion, Airtable, and Coda for client project data",
            data_sensitivity="medium-high",
        )
        scores = rank_vendors([vendors["notion"], vendors["airtable"], vendors["coda"]], request)
        self.assertEqual([s.overall for s in scores], sorted([s.overall for s in scores], reverse=True))
        self.assertEqual(scores[0].vendor, "Notion")


if __name__ == "__main__":
    unittest.main()
