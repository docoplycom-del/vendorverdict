from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from vendorverdict.api import app


class DashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("VENDORVERDICT_API_DB_PATH")
        self.old_export = os.environ.get("VENDORVERDICT_API_EXPORT_DIR")
        self.old_live = os.environ.get("VENDORVERDICT_API_LIVE_EVIDENCE")
        self.old_email_send = os.environ.get("VENDORVERDICT_EMAIL_SEND_ENABLED")
        os.environ["VENDORVERDICT_API_DB_PATH"] = os.path.join(self.tmp.name, "dashboard.sqlite3")
        os.environ["VENDORVERDICT_API_EXPORT_DIR"] = os.path.join(self.tmp.name, "reports")
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        os.environ["VENDORVERDICT_EMAIL_SEND_ENABLED"] = "0"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        _restore_env("VENDORVERDICT_API_DB_PATH", self.old_db)
        _restore_env("VENDORVERDICT_API_EXPORT_DIR", self.old_export)
        _restore_env("VENDORVERDICT_API_LIVE_EVIDENCE", self.old_live)
        _restore_env("VENDORVERDICT_EMAIL_SEND_ENABLED", self.old_email_send)


    def test_public_landing_page_renders(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Evidence-backed vendor reviews", response.text)
        self.assertIn("Login to dashboard", response.text)
        self.assertIn("Pilot package", response.text)

    def test_favicon_routes_are_available(self) -> None:
        ico = self.client.get("/favicon.ico")
        self.assertEqual(ico.status_code, 200)
        png = self.client.get("/favicon.png")
        self.assertEqual(png.status_code, 200)


    def test_public_demo_page_renders(self) -> None:
        response = self.client.get("/demo")
        self.assertEqual(response.status_code, 200)
        self.assertIn("30-second customer demo", response.text)
        self.assertIn("Sample vendor review", response.text)
        self.assertIn("Ranked scorecard", response.text)
        self.assertIn("Due-diligence email", response.text)



    def test_public_pricing_page_renders(self) -> None:
        response = self.client.get("/pricing")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Start with a focused paid pilot", response.text)
        self.assertIn("From £1,500", response.text)
        self.assertIn("10–20", response.text)


    def test_public_trust_privacy_and_disclaimer_pages_render(self) -> None:
        trust = self.client.get("/trust")
        self.assertEqual(trust.status_code, 200)
        self.assertIn("Trust & safety", trust.text)
        self.assertIn("Do not submit sensitive secrets", trust.text)

        privacy = self.client.get("/privacy")
        self.assertEqual(privacy.status_code, 200)
        self.assertIn("VendorVerdict privacy notice", privacy.text)

        disclaimer = self.client.get("/disclaimer")
        self.assertEqual(disclaimer.status_code, 200)
        self.assertIn("VendorVerdict disclaimer", disclaimer.text)

    def test_public_navigation_keeps_admin_links_out_until_logged_in(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Pilot package", response.text)
        self.assertIn("Trust", response.text)
        self.assertNotIn('href="/docs"', response.text)
        self.assertNotIn('href="/health"', response.text)

    def test_public_pilot_request_form_renders(self) -> None:
        response = self.client.get("/pilot")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Request a pilot", response.text)
        self.assertIn("Vendors you are considering", response.text)
        self.assertIn("from £1,500", response.text)

    def test_demo_page_contains_lead_capture_form(self) -> None:
        response = self.client.get("/demo")
        self.assertEqual(response.status_code, 200)
        self.assertIn('action="/leads/request"', response.text)
        self.assertIn("Request pilot", response.text)

    def test_lead_form_saves_request_and_dashboard_lists_it(self) -> None:
        response = self.client.post(
            "/leads/request",
            data={
                "name": "Alex Buyer",
                "email": "alex@example.com",
                "company": "Example Consulting",
                "vendors": "Notion, Airtable",
                "use_case": "storing client project data",
                "message": "We want a pilot.",
                "source": "demo",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["location"].startswith("/pilot/thanks"))

        thanks = self.client.get(response.headers["location"])
        self.assertEqual(thanks.status_code, 200)
        self.assertIn("pilot request was saved", thanks.text)

        leads = self.client.get("/dashboard/leads")
        self.assertEqual(leads.status_code, 200)
        self.assertIn("Alex Buyer", leads.text)
        self.assertIn("alex@example.com", leads.text)
        self.assertIn("Example Consulting", leads.text)

    def test_invalid_lead_form_returns_errors(self) -> None:
        response = self.client.post("/leads/request", data={"name": "A", "email": "bad"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Enter a valid email address", response.text)

    def test_lead_inbox_can_update_status_notes_and_export_csv(self) -> None:
        response = self.client.post(
            "/leads/request",
            data={
                "name": "Jordan Ops",
                "email": "jordan@example.com",
                "company": "Ops Co",
                "vendors": "Slack, Teams",
                "use_case": "internal collaboration",
                "message": "Please follow up next week.",
                "source": "pilot",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

        inbox = self.client.get("/dashboard/leads")
        self.assertEqual(inbox.status_code, 200)
        self.assertIn("Jordan Ops", inbox.text)
        self.assertIn("new", inbox.text)
        self.assertIn("Export CSV", inbox.text)
        self.assertIn("Add follow-up notes", inbox.text)

        import re
        match = re.search(r'action="(/dashboard/leads/[^"]+/status)"', inbox.text)
        self.assertIsNotNone(match)

        update = self.client.post(
            match.group(1),
            data={"status": "qualified", "notes": "Good fit for a founding pilot."},
            follow_redirects=False,
        )
        self.assertEqual(update.status_code, 303)
        self.assertEqual(update.headers["location"], "/dashboard/leads")

        updated = self.client.get("/dashboard/leads")
        self.assertEqual(updated.status_code, 200)
        self.assertIn("qualified", updated.text)
        self.assertIn("Good fit for a founding pilot.", updated.text)

        csv_export = self.client.get("/dashboard/leads.csv")
        self.assertEqual(csv_export.status_code, 200)
        self.assertIn("text/csv", csv_export.headers["content-type"])
        self.assertIn("vendorverdict-leads.csv", csv_export.headers["content-disposition"])
        self.assertIn("Jordan Ops", csv_export.text)
        self.assertIn("qualified", csv_export.text)
        self.assertIn("Good fit for a founding pilot.", csv_export.text)

        detail_path = match.group(1).replace("/status", "")
        detail = self.client.get(detail_path)
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Pilot lead", detail.text)
        self.assertIn("Copy / paste follow-up", detail.text)
        self.assertIn("First reply", detail.text)
        self.assertIn("Qualification questions", detail.text)
        self.assertIn("Pilot package", detail.text)
        self.assertIn("mailto:jordan%40example.com", detail.text)

        detail_update = self.client.post(
            match.group(1),
            data={"status": "contacted", "notes": "Replied using first template.", "next": detail_path},
            follow_redirects=False,
        )
        self.assertEqual(detail_update.status_code, 303)
        self.assertEqual(detail_update.headers["location"], detail_path)

        updated_detail = self.client.get(detail_path)
        self.assertEqual(updated_detail.status_code, 200)
        self.assertIn("Replied using first template.", updated_detail.text)

    def test_lead_can_be_converted_to_pilot_workspace(self) -> None:
        response = self.client.post(
            "/leads/request",
            data={
                "name": "Casey Buyer",
                "email": "casey@example.com",
                "company": "Pilot Co",
                "vendors": "Notion, Airtable",
                "use_case": "client delivery records",
                "source": "pilot",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

        inbox = self.client.get("/dashboard/leads")
        self.assertEqual(inbox.status_code, 200)
        import re
        match = re.search(r'href="(/dashboard/leads/[^"]+)"[^>]*><strong>Casey Buyer</strong>', inbox.text)
        self.assertIsNotNone(match)
        detail_path = match.group(1)

        detail = self.client.get(detail_path)
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Create pilot workspace", detail.text)

        convert = self.client.post(
            f"{detail_path}/pilot",
            data={"package": "founding", "review_target": "20", "objective": "client delivery records"},
            follow_redirects=False,
        )
        self.assertEqual(convert.status_code, 303)
        self.assertTrue(convert.headers["location"].startswith("/dashboard/pilots/"))

        pilot = self.client.get(convert.headers["location"])
        self.assertEqual(pilot.status_code, 200)
        self.assertIn("Pilot workspace", pilot.text)
        self.assertIn("Pilot Co", pilot.text)
        self.assertIn("Onboarding checklist", pilot.text)
        self.assertIn("Book pilot scope call", pilot.text)
        self.assertIn("Run and track vendor reviews", pilot.text)

        run_review = self.client.post(
            convert.headers["location"] + "/reviews/run",
            data={
                "label": "Client data shortlist",
                "vendors": "Notion, Airtable",
                "use_case": "client delivery records",
                "team_size": "10",
                "region": "UK",
                "data_sensitivity": "medium",
                "export_markdown": "1",
                "export_pdf": "1",
            },
            follow_redirects=False,
        )
        self.assertEqual(run_review.status_code, 303)
        self.assertEqual(run_review.headers["location"], convert.headers["location"])

        pilot_with_review = self.client.get(convert.headers["location"])
        self.assertEqual(pilot_with_review.status_code, 200)
        self.assertIn("Client data shortlist", pilot_with_review.text)
        self.assertIn("View report", pilot_with_review.text)
        self.assertIn("PDF", pilot_with_review.text)
        self.assertIn("1/20", pilot_with_review.text)

        reviews_csv = self.client.get(convert.headers["location"] + "/reviews.csv")
        self.assertEqual(reviews_csv.status_code, 200)
        self.assertIn("text/csv", reviews_csv.headers["content-type"])
        self.assertIn("Client data shortlist", reviews_csv.text)

        outcome = self.client.get(convert.headers["location"] + "/outcome")
        self.assertEqual(outcome.status_code, 200)
        self.assertIn("Pilot outcome", outcome.text)
        self.assertIn("Client data shortlist", outcome.text)
        self.assertIn("Download Markdown", outcome.text)

        outcome_md = self.client.get(convert.headers["location"] + "/outcome.md")
        self.assertEqual(outcome_md.status_code, 200)
        self.assertIn("text/markdown", outcome_md.headers["content-type"])
        self.assertIn("VendorVerdict pilot outcome", outcome_md.text)

        proposal_create = self.client.post(convert.headers["location"] + "/proposal", follow_redirects=False)
        self.assertEqual(proposal_create.status_code, 303)
        self.assertTrue(proposal_create.headers["location"].startswith("/dashboard/proposals/"))

        proposal_detail = self.client.get(proposal_create.headers["location"])
        self.assertEqual(proposal_detail.status_code, 200)
        self.assertIn("Commercial proposal", proposal_detail.text)
        self.assertIn("Commercial follow-up", proposal_detail.text)
        self.assertIn("Pilot Co", proposal_detail.text)
        self.assertIn("Save proposal", proposal_detail.text)
        self.assertIn("Download customer PDF", proposal_detail.text)
        self.assertIn("Proposal delivery", proposal_detail.text)
        self.assertIn("Open proposal email", proposal_detail.text)
        self.assertIn("Direct email sending", proposal_detail.text)
        self.assertIn("SMTP sending is not configured yet", proposal_detail.text)
        self.assertIn("Payment tracking", proposal_detail.text)
        self.assertIn("Payment email", proposal_detail.text)
        self.assertIn("Open payment request email", proposal_detail.text)
        self.assertIn("Open payment reminder", proposal_detail.text)
        self.assertIn("Mark invoice/payment link sent", proposal_detail.text)

        proposal_update = self.client.post(
            proposal_create.headers["location"] + "/update",
            data={
                "status": "sent",
                "package": "starter",
                "proposed_price": "£750/month",
                "billing": "Monthly after pilot.",
                "scope": "Recurring vendor reviews.",
                "success_criteria": "Decision-ready vendor reviews before adoption.",
                "next_step": "Book a close-out call.",
                "notes": "Sent to buyer.",
            },
            follow_redirects=False,
        )
        self.assertEqual(proposal_update.status_code, 303)
        self.assertEqual(proposal_update.headers["location"], proposal_create.headers["location"])

        updated_proposal = self.client.get(proposal_create.headers["location"])
        self.assertEqual(updated_proposal.status_code, 200)
        self.assertIn("£750/month", updated_proposal.text)
        self.assertIn("Sent to buyer.", updated_proposal.text)

        send_without_smtp = self.client.post(
            proposal_create.headers["location"] + "/send",
            data={"follow_up_due": "2026-07-16"},
            follow_redirects=False,
        )
        self.assertEqual(send_without_smtp.status_code, 303)
        self.assertTrue(send_without_smtp.headers["location"].endswith("?delivery=not_configured"))
        send_notice = self.client.get(send_without_smtp.headers["location"])
        self.assertEqual(send_notice.status_code, 200)
        self.assertIn("SMTP email sending is not configured", send_notice.text)

        delivery_update = self.client.post(
            proposal_create.headers["location"] + "/delivery",
            data={"action": "mark_sent", "follow_up_due": "2026-07-15"},
            follow_redirects=False,
        )
        self.assertEqual(delivery_update.status_code, 303)
        self.assertEqual(delivery_update.headers["location"], proposal_create.headers["location"])

        delivered_proposal = self.client.get(proposal_create.headers["location"])
        self.assertEqual(delivered_proposal.status_code, 200)
        self.assertIn("follow-up due 2026-07-15", delivered_proposal.text)
        self.assertIn("Mark followed up", delivered_proposal.text)

        payment_update = self.client.post(
            proposal_create.headers["location"] + "/payment",
            data={
                "action": "mark_invoice_sent",
                "payment_due": "2026-07-30",
                "invoice_reference": "INV-VV-001",
                "payment_url": "https://pay.example.com/vendorverdict",
            },
            follow_redirects=False,
        )
        self.assertEqual(payment_update.status_code, 303)
        self.assertEqual(payment_update.headers["location"], proposal_create.headers["location"])

        payment_page = self.client.get(proposal_create.headers["location"])
        self.assertEqual(payment_page.status_code, 200)
        self.assertIn("invoice sent", payment_page.text)
        self.assertIn("INV-VV-001", payment_page.text)
        self.assertIn("https://pay.example.com/vendorverdict", payment_page.text)
        self.assertIn("VendorVerdict payment details", payment_page.text)

        payment_send_without_smtp = self.client.post(
            proposal_create.headers["location"] + "/payment/send",
            data={
                "action": "request",
                "payment_due": "2026-07-30",
                "invoice_reference": "INV-VV-001",
                "payment_url": "https://pay.example.com/vendorverdict",
            },
            follow_redirects=False,
        )
        self.assertEqual(payment_send_without_smtp.status_code, 303)
        self.assertTrue(payment_send_without_smtp.headers["location"].endswith("?payment_delivery=not_configured"))
        payment_send_notice = self.client.get(payment_send_without_smtp.headers["location"])
        self.assertEqual(payment_send_notice.status_code, 200)
        self.assertIn("SMTP email sending is not configured", payment_send_notice.text)

        paid_update = self.client.post(
            proposal_create.headers["location"] + "/payment",
            data={"action": "mark_paid"},
            follow_redirects=False,
        )
        self.assertEqual(paid_update.status_code, 303)

        proposal_md = self.client.get(proposal_create.headers["location"] + ".md")
        self.assertEqual(proposal_md.status_code, 200)
        self.assertIn("text/markdown", proposal_md.headers["content-type"])
        self.assertIn("VendorVerdict proposal", proposal_md.text)
        self.assertIn("Payment link", proposal_md.text)

        proposal_pdf = self.client.get(proposal_create.headers["location"] + ".pdf")
        self.assertEqual(proposal_pdf.status_code, 200)
        self.assertIn("application/pdf", proposal_pdf.headers["content-type"])
        self.assertTrue(proposal_pdf.content.startswith(b"%PDF"))

        proposals = self.client.get("/dashboard/proposals")
        self.assertEqual(proposals.status_code, 200)
        self.assertIn("Pilot Co", proposals.text)
        self.assertIn("Open proposal", proposals.text)
        self.assertIn("PDF", proposals.text)
        self.assertIn("follow-up due", proposals.text)
        self.assertIn("Payment:", proposals.text)
        self.assertIn("paid", proposals.text)

        proposals_csv = self.client.get("/dashboard/proposals.csv")
        self.assertEqual(proposals_csv.status_code, 200)
        self.assertIn("text/csv", proposals_csv.headers["content-type"])
        self.assertIn("Pilot Co", proposals_csv.text)
        self.assertIn("follow_up_due", proposals_csv.text)
        self.assertIn("payment_status", proposals_csv.text)
        self.assertIn("INV-VV-001", proposals_csv.text)
        self.assertIn("2026-07-15", proposals_csv.text)

        complete = self.client.post(convert.headers["location"] + "/complete", follow_redirects=False)
        self.assertEqual(complete.status_code, 303)
        self.assertTrue(complete.headers["location"].endswith("/outcome"))

        task_update = self.client.post(
            convert.headers["location"] + "/tasks/scope_call",
            data={"completed": "1"},
            follow_redirects=False,
        )
        self.assertEqual(task_update.status_code, 303)

        updated = self.client.get(convert.headers["location"])
        self.assertEqual(updated.status_code, 200)
        self.assertIn("Mark open", updated.text)

        pilots = self.client.get("/dashboard/pilots")
        self.assertEqual(pilots.status_code, 200)
        self.assertIn("Pilot Co", pilots.text)
        self.assertIn("Open workspace", pilots.text)

    def test_dashboard_can_run_sample_review(self) -> None:
        response = self.client.post("/reviews/sample", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["location"].startswith("/dashboard/reports/"))

        detail = self.client.get(response.headers["location"])
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Notion vs Airtable vs Coda", detail.text)
        self.assertIn("Download PDF", detail.text)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Run sample review", dashboard.text)

    def test_dashboard_renders_empty_state(self) -> None:
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("VendorVerdict Dashboard", response.text)
        self.assertIn("No saved reports yet", response.text)
        self.assertIn("Start new vendor review", response.text)

    def test_new_review_form_renders(self) -> None:
        response = self.client.get("/reviews/new")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Create a vendor-risk report", response.text)
        self.assertIn("Generate report", response.text)
        self.assertIn("Vendors", response.text)
        self.assertIn("Use case", response.text)
        self.assertIn("medium-high", response.text)

    def test_dashboard_can_create_and_view_report(self) -> None:
        response = self.client.post(
            "/reviews/run",
            data={
                "query": "Compare Notion and Airtable for storing client project data for a 10-person consulting startup in the UK.",
                "export_markdown": "1",
                "export_pdf": "1",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        location = response.headers["location"]
        self.assertTrue(location.startswith("/dashboard/reports/"))

        detail = self.client.get(location)
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Notion vs Airtable", detail.text)
        self.assertIn("Recommendation: Notion", detail.text)
        self.assertIn("Download PDF", detail.text)
        self.assertIn("Multi-agent workflow", detail.text)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Notion vs Airtable", dashboard.text)


    def test_dashboard_guided_form_builds_review_query(self) -> None:
        response = self.client.post(
            "/reviews/run",
            data={
                "vendors": "Notion, Airtable",
                "use_case": "storing client project data",
                "team_size": "10",
                "region": "UK",
                "data_sensitivity": "medium-high",
                "export_pdf": "1",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        detail = self.client.get(response.headers["location"])
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Evidence-backed findings", detail.text)
        self.assertIn("Official-source snapshot", detail.text)

    def test_dashboard_shows_clarification_instead_of_saving_incomplete_request(self) -> None:
        response = self.client.post(
            "/reviews/run",
            data={"query": "Compare Notion and Airtable"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("needs clarification", response.text.lower())
        self.assertIn("Clarification response", response.text)


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()

class ContrastCssTests(unittest.TestCase):
    def test_demo_and_lead_capture_contrast_rules_are_present(self):
        css = Path("src/vendorverdict/web/static/style.css").read_text(encoding="utf-8")
        self.assertIn("--vv-action-bg", css)
        self.assertIn("--vv-field-bg", css)
        self.assertIn("--vv-field-placeholder", css)
        self.assertIn("html body .container a.button", css)
        self.assertIn("html body .form-card textarea", css)
        self.assertIn("html body .callout", css)
        self.assertIn(".site-footer", css)
        self.assertIn(".trust-strip", css)
        self.assertIn(".lead-admin-form", css)
        self.assertIn("--vv-login-field-bg", css)
        self.assertIn("html body .auth-card input", css)
        self.assertIn("input:-webkit-autofill", css)

    def test_stylesheet_is_versioned_to_break_browser_cache(self):
        template = Path("src/vendorverdict/web/templates/base.html").read_text(encoding="utf-8")
        self.assertIn("style.css?v=20260709-business-metrics", template)

class PilotReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("VENDORVERDICT_API_DB_PATH")
        self.old_export = os.environ.get("VENDORVERDICT_API_EXPORT_DIR")
        self.old_live = os.environ.get("VENDORVERDICT_API_LIVE_EVIDENCE")
        self.old_email_send = os.environ.get("VENDORVERDICT_EMAIL_SEND_ENABLED")
        os.environ["VENDORVERDICT_API_DB_PATH"] = os.path.join(self.tmp.name, "readiness.sqlite3")
        os.environ["VENDORVERDICT_API_EXPORT_DIR"] = os.path.join(self.tmp.name, "reports")
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        os.environ["VENDORVERDICT_EMAIL_SEND_ENABLED"] = "0"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        _restore_env("VENDORVERDICT_API_DB_PATH", self.old_db)
        _restore_env("VENDORVERDICT_API_EXPORT_DIR", self.old_export)
        _restore_env("VENDORVERDICT_API_LIVE_EVIDENCE", self.old_live)
        _restore_env("VENDORVERDICT_EMAIL_SEND_ENABLED", self.old_email_send)

    def test_pilot_readiness_page_renders_next_actions(self) -> None:
        response = self.client.get("/dashboard/readiness")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Final pilot-readiness check", response.text)
        self.assertIn("Production pilot-readiness checklist", response.text)
        self.assertIn("Lead capture workflow", response.text)
        self.assertIn("Customer share links", response.text)
        self.assertIn("Submit one test pilot request", response.text)
        self.assertIn("status_vendorverdict.sh", response.text)

    def test_dashboard_links_to_pilot_readiness_page(self) -> None:
        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Readiness check", dashboard.text)
        self.assertIn('/dashboard/readiness', dashboard.text)

        template = Path("src/vendorverdict/web/templates/base.html").read_text(encoding="utf-8")
        self.assertIn('/dashboard/readiness', template)
        self.assertIn('style.css?v=20260709-business-metrics', template)
