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

    def test_unknown_single_vendor_with_use_case_is_valid(self):
        request = parse_vendor_request(
            "Check Northstar CRM for storing customer lead data for a 6-person sales team in the UK.",
            ["Notion", "Airtable", "Coda"],
        )
        self.assertEqual(request.vendors, ("Northstar CRM",))
        self.assertEqual(request.use_case, "storing customer lead data")
        self.assertEqual(request.team_size, "6 people")
        self.assertEqual(request.missing_fields, ())

    def test_unknown_compare_vendors_are_extracted_from_segment(self):
        request = parse_vendor_request(
            "Compare AlphaDocs, BetaBase and GammaFlow for storing client files.",
            ["Notion", "Airtable", "Coda"],
        )
        self.assertEqual(request.vendors, ("AlphaDocs", "BetaBase", "GammaFlow"))
        self.assertEqual(request.use_case, "storing client files")
        self.assertEqual(request.missing_fields, ())

    def test_extracts_unknown_vendor_from_explicit_check_prompt(self):
        request = parse_vendor_request(
            "Check ExampleCRM for storing customer lead data for a 6-person sales team in the UK.",
            ["Notion", "Airtable", "Coda"],
        )
        self.assertEqual(request.vendors, ("ExampleCRM",))
        self.assertEqual(request.use_case, "storing customer lead data")
        self.assertEqual(request.missing_fields, ())

    def test_extracts_mixed_known_and_unknown_vendors(self):
        request = parse_vendor_request(
            "Compare Notion, ExampleCRM, and Coda for managing client projects.",
            ["Notion", "Airtable", "Coda"],
        )
        self.assertEqual(request.vendors, ("Notion", "ExampleCRM", "Coda"))


if __name__ == "__main__":
    unittest.main()
