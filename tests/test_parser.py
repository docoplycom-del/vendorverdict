import unittest

from vendorverdict.parser import parse_vendor_request


class ParserTests(unittest.TestCase):
    def test_demo_query_extracts_core_fields(self):
        vendors = ["Notion", "Airtable", "Coda"]
        query = (
            "Compare Notion, Airtable, and Coda for storing client project data "
            "for a 10-person consulting startup in the UK."
        )
        request = parse_vendor_request(query, vendors)
        self.assertEqual(request.vendors, ("Notion", "Airtable", "Coda"))
        self.assertEqual(request.use_case, "storing client project data")
        self.assertEqual(request.team_size, "10 people")
        self.assertEqual(request.business_type, "consulting startup")
        self.assertEqual(request.region, "UK")
        self.assertEqual(request.data_sensitivity, "medium-high")
        self.assertEqual(request.missing_fields, ())

    def test_missing_use_case_is_detected(self):
        request = parse_vendor_request("Compare Notion and Airtable", ["Notion", "Airtable"])
        self.assertIn("use_case", request.missing_fields)

    def test_single_vendor_with_use_case_is_valid_audit_request(self):
        request = parse_vendor_request(
            "Check Coda for storing client project data for a 10-person consulting startup in the UK.",
            ["Notion", "Airtable", "Coda"],
        )
        self.assertEqual(request.vendors, ("Coda",))
        self.assertEqual(request.use_case, "storing client project data")
        self.assertEqual(request.missing_fields, ())


if __name__ == "__main__":
    unittest.main()
