from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from vendorverdict.leads import LeadStore
from vendorverdict.pilots import PilotStore
from vendorverdict.proposal_email_delivery import (
    ProposalEmailSettings,
    build_customer_proposal_email,
    get_proposal_email_settings,
    send_customer_proposal_email,
)
from vendorverdict.proposals import ProposalStore


class ProposalEmailDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "email-delivery.sqlite3")
        lead_id = LeadStore(self.db_path).save_lead(
            name="Sam Buyer",
            email="sam@example.com",
            company="Email Co",
            vendors="Notion, Airtable",
            use_case="client data",
        )
        lead = LeadStore(self.db_path).get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = PilotStore(self.db_path).create_from_lead(lead, package="team", review_target=20)
        pilot = PilotStore(self.db_path).get_pilot(pilot_id)
        self.assertIsNotNone(pilot)
        self.proposals = ProposalStore(self.db_path)
        self.proposal_id = self.proposals.create_from_pilot(pilot)
        proposal = self.proposals.get_proposal(self.proposal_id)
        self.assertIsNotNone(proposal)
        self.proposal = proposal

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_settings_require_explicit_enablement_and_smtp_host(self) -> None:
        old_env = {key: os.environ.get(key) for key in SMTP_ENV_KEYS}
        try:
            for key in SMTP_ENV_KEYS:
                os.environ.pop(key, None)
            settings = get_proposal_email_settings()
            self.assertFalse(settings.is_configured)
            self.assertIn("VENDORVERDICT_EMAIL_SEND_ENABLED", settings.missing_fields)
            self.assertIn("VENDORVERDICT_SMTP_HOST", settings.missing_fields)

            os.environ["VENDORVERDICT_EMAIL_SEND_ENABLED"] = "1"
            os.environ["VENDORVERDICT_SMTP_HOST"] = "smtp.example.com"
            os.environ["VENDORVERDICT_SMTP_FROM"] = "hello@example.com"
            configured = get_proposal_email_settings()
            self.assertTrue(configured.is_configured)
            self.assertEqual(configured.port, 587)
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_build_customer_email_includes_share_link_and_attachment_note(self) -> None:
        email = build_customer_proposal_email(
            self.proposal,
            share_url="https://vendorverdict.docoply.com/share/proposal/token123",
        )
        self.assertIn("VendorVerdict next step", email.subject)
        self.assertIn("https://vendorverdict.docoply.com/share/proposal/token123", email.body)
        self.assertIn("attached the customer proposal PDF", email.body)

    def test_send_skips_when_not_configured(self) -> None:
        result = send_customer_proposal_email(
            self.proposal,
            settings=ProposalEmailSettings(enabled=False),
        )
        self.assertFalse(result.sent)
        self.assertIn("not configured", result.detail)

    def test_send_uses_smtp_and_attachment_when_configured(self) -> None:
        pdf_path = Path(self.tmp.name) / "proposal.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 sample")
        settings = ProposalEmailSettings(
            enabled=True,
            host="smtp.example.com",
            port=587,
            username="user",
            password="password",
            from_email="hello@example.com",
            from_name="VendorVerdict",
            starttls=True,
        )
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        smtp.send_message.return_value = {}
        with patch("vendorverdict.proposal_email_delivery.smtplib.SMTP", return_value=smtp) as smtp_cls:
            result = send_customer_proposal_email(
                self.proposal,
                pdf_path=pdf_path,
                share_url="https://vendorverdict.docoply.com/share/proposal/token123",
                settings=settings,
            )
        self.assertTrue(result.sent)
        smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=15)
        self.assertTrue(smtp.starttls.called)
        smtp.login.assert_called_once_with("user", "password")
        self.assertTrue(smtp.send_message.called)
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message["To"], "sam@example.com")
        self.assertIn("VendorVerdict next step", message["Subject"])
        self.assertTrue(message.is_multipart())


SMTP_ENV_KEYS = [
    "VENDORVERDICT_EMAIL_SEND_ENABLED",
    "VENDORVERDICT_SMTP_HOST",
    "VENDORVERDICT_SMTP_PORT",
    "VENDORVERDICT_SMTP_USERNAME",
    "VENDORVERDICT_SMTP_PASSWORD",
    "VENDORVERDICT_SMTP_FROM",
    "VENDORVERDICT_SMTP_FROM_NAME",
    "VENDORVERDICT_SMTP_STARTTLS",
    "VENDORVERDICT_SMTP_TIMEOUT_SECONDS",
]


if __name__ == "__main__":
    unittest.main()
