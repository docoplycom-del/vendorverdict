from __future__ import annotations

import os
import tempfile
import unittest

from vendorverdict.leads import LeadStore
from vendorverdict.pilots import PilotStore
from vendorverdict.proposals import ProposalStore
from vendorverdict.stripe_checkout import (
    StripeCheckoutSettings,
    amount_from_price_text,
    amount_to_minor_units,
    create_stripe_checkout_session,
    get_stripe_checkout_settings,
)


class FakeStripeResponse:
    def __init__(self, payload: dict[str, str]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return self.payload


class StripeCheckoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "stripe.sqlite3")
        leads = LeadStore(self.db_path)
        pilots = PilotStore(self.db_path)
        self.proposals = ProposalStore(self.db_path)
        lead_id = leads.save_lead(
            name="Sam Buyer",
            email="sam@example.com",
            company="Stripe Co",
            vendors="Notion, Airtable",
            use_case="storing client data",
        )
        lead = leads.get_lead(lead_id)
        self.assertIsNotNone(lead)
        pilot_id = pilots.create_from_lead(lead, package="team", review_target=10)
        pilot = pilots.get_pilot(pilot_id)
        self.assertIsNotNone(pilot)
        self.proposal_id = self.proposals.create_from_pilot(pilot)
        proposal = self.proposals.get_proposal(self.proposal_id)
        self.assertIsNotNone(proposal)
        self.proposal = proposal

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_amount_helpers_prepare_checkout_amounts(self) -> None:
        self.assertEqual(amount_to_minor_units("1500"), 150000)
        self.assertEqual(amount_to_minor_units("1,500.50"), 150050)
        self.assertEqual(amount_to_minor_units("£1,000"), 100000)
        self.assertEqual(amount_from_price_text("From £1,000/month after pilot"), "1000")
        self.assertEqual(amount_from_price_text("Custom"), "1500")
        with self.assertRaises(ValueError):
            amount_to_minor_units("bad")

    def test_settings_report_missing_secret_when_not_configured(self) -> None:
        old_enabled = os.environ.get("VENDORVERDICT_STRIPE_CHECKOUT_ENABLED")
        old_secret = os.environ.get("VENDORVERDICT_STRIPE_SECRET_KEY")
        try:
            os.environ["VENDORVERDICT_STRIPE_CHECKOUT_ENABLED"] = "1"
            os.environ["VENDORVERDICT_STRIPE_SECRET_KEY"] = ""
            settings = get_stripe_checkout_settings()
            self.assertFalse(settings.is_configured)
            self.assertIn("VENDORVERDICT_STRIPE_SECRET_KEY", settings.missing_fields)
        finally:
            _restore_env("VENDORVERDICT_STRIPE_CHECKOUT_ENABLED", old_enabled)
            _restore_env("VENDORVERDICT_STRIPE_SECRET_KEY", old_secret)

    def test_create_checkout_session_posts_customer_proposal_details(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_post(url: str, *, data: dict[str, object], headers: dict[str, str], timeout: int):
            calls.append({"url": url, "data": data, "headers": headers, "timeout": timeout})
            return FakeStripeResponse({"id": "cs_test_123", "url": "https://checkout.stripe.com/c/pay/test"})

        settings = StripeCheckoutSettings(
            enabled=True,
            secret_key="sk_test_123",
            currency="gbp",
            success_url="https://vendorverdict.example/success",
            cancel_url="https://vendorverdict.example/cancel",
            timeout_seconds=9,
        )
        result = create_stripe_checkout_session(self.proposal, amount="1250", settings=settings, post=fake_post)

        self.assertTrue(result.created)
        self.assertEqual(result.session_id, "cs_test_123")
        self.assertEqual(result.url, "https://checkout.stripe.com/c/pay/test")
        self.assertEqual(len(calls), 1)
        payload = calls[0]["data"]
        self.assertEqual(payload["line_items[0][price_data][unit_amount]"], 125000)
        self.assertEqual(payload["customer_email"], "sam@example.com")
        self.assertEqual(payload["metadata[proposal_id]"], self.proposal.proposal_id)
        self.assertEqual(calls[0]["headers"], {"Authorization": "Bearer sk_test_123"})

    def test_create_checkout_session_requires_configuration_and_valid_amount(self) -> None:
        settings = StripeCheckoutSettings(
            enabled=False,
            secret_key="",
            currency="gbp",
            success_url="",
            cancel_url="",
            timeout_seconds=15,
        )
        not_configured = create_stripe_checkout_session(self.proposal, amount="1500", settings=settings)
        self.assertFalse(not_configured.created)
        self.assertIn("not configured", not_configured.detail)

        configured = StripeCheckoutSettings(
            enabled=True,
            secret_key="sk_test_123",
            currency="gbp",
            success_url="https://vendorverdict.example/success",
            cancel_url="https://vendorverdict.example/cancel",
            timeout_seconds=15,
        )
        invalid = create_stripe_checkout_session(self.proposal, amount="bad", settings=configured)
        self.assertFalse(invalid.created)
        self.assertIn("valid payment amount", invalid.detail)


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
