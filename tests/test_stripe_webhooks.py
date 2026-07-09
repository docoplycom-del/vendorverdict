from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from vendorverdict.api import app
from vendorverdict.leads import LeadStore
from vendorverdict.pilots import PilotStore
from vendorverdict.proposals import ProposalStore
from vendorverdict.stripe_webhooks import (
    StripeWebhookSettings,
    get_stripe_webhook_settings,
    process_stripe_webhook_event,
    verify_stripe_signature,
)


class StripeWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_env = {key: os.environ.get(key) for key in ENV_KEYS}
        self.db_path = os.path.join(self.tmp.name, "webhooks.sqlite3")
        os.environ["VENDORVERDICT_API_DB_PATH"] = self.db_path
        os.environ["VENDORVERDICT_API_EXPORT_DIR"] = os.path.join(self.tmp.name, "reports")
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        os.environ["VENDORVERDICT_STRIPE_WEBHOOK_ENABLED"] = "1"
        os.environ["VENDORVERDICT_STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"
        os.environ["VENDORVERDICT_AUTH_ENABLED"] = "1"
        os.environ["VENDORVERDICT_AUTH_USERNAME"] = "admin"
        os.environ["VENDORVERDICT_AUTH_PASSWORD"] = "secret-password"
        os.environ["VENDORVERDICT_AUTH_SECRET"] = "auth-secret"
        self.client = TestClient(app)
        self.proposals = ProposalStore(self.db_path)
        self.proposal_id = _create_proposal(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_signature_verification_accepts_valid_and_rejects_invalid(self) -> None:
        payload = b'{"id":"evt_test"}'
        now = int(time.time())
        header = _stripe_signature_header(payload, "whsec_test_secret", timestamp=now)
        self.assertTrue(verify_stripe_signature(payload, header, "whsec_test_secret", now=now))
        self.assertFalse(verify_stripe_signature(payload, header, "wrong", now=now))
        self.assertFalse(verify_stripe_signature(payload, header, "whsec_test_secret", now=now + 1000, tolerance_seconds=300))

    def test_settings_report_missing_secret_when_webhook_not_configured(self) -> None:
        os.environ["VENDORVERDICT_STRIPE_WEBHOOK_ENABLED"] = "1"
        os.environ["VENDORVERDICT_STRIPE_WEBHOOK_SECRET"] = ""
        settings = get_stripe_webhook_settings()
        self.assertFalse(settings.is_configured)
        self.assertIn("VENDORVERDICT_STRIPE_WEBHOOK_SECRET", settings.missing_fields)

    def test_process_checkout_completed_marks_proposal_paid(self) -> None:
        event = _checkout_completed_event(self.proposal_id)
        result = process_stripe_webhook_event(event, self.proposals)
        self.assertTrue(result.processed)
        proposal = self.proposals.get_proposal(self.proposal_id)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.payment_status, "paid")
        self.assertEqual(proposal.invoice_reference, "cs_test_paid")
        self.assertTrue(proposal.paid_at)
        events = self.proposals.list_payment_events(self.proposal_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].status, "paid")

    def test_webhook_endpoint_is_public_and_marks_payment_paid(self) -> None:
        payload = json.dumps(_checkout_completed_event(self.proposal_id), separators=(",", ":")).encode("utf-8")
        header = _stripe_signature_header(payload, "whsec_test_secret")
        response = self.client.post(
            "/webhooks/stripe",
            content=payload,
            headers={"Stripe-Signature": header, "Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "processed")
        proposal = self.proposals.get_proposal(self.proposal_id)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.payment_status, "paid")

    def test_webhook_endpoint_rejects_bad_signature(self) -> None:
        payload = json.dumps(_checkout_completed_event(self.proposal_id)).encode("utf-8")
        response = self.client.post(
            "/webhooks/stripe",
            content=payload,
            headers={"Stripe-Signature": "t=1,v1=bad", "Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "invalid_signature")


def _create_proposal(db_path: str) -> str:
    leads = LeadStore(db_path)
    pilots = PilotStore(db_path)
    proposals = ProposalStore(db_path)
    lead_id = leads.save_lead(
        name="Sam Buyer",
        email="sam@example.com",
        company="Stripe Co",
        vendors="Notion, Airtable",
        use_case="storing client data",
    )
    lead = leads.get_lead(lead_id)
    assert lead is not None
    pilot_id = pilots.create_from_lead(lead, package="team", review_target=10)
    pilot = pilots.get_pilot(pilot_id)
    assert pilot is not None
    return proposals.create_from_pilot(pilot)


def _checkout_completed_event(proposal_id: str) -> dict[str, object]:
    return {
        "id": "evt_checkout_paid",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_paid",
                "client_reference_id": proposal_id,
                "payment_status": "paid",
                "metadata": {"proposal_id": proposal_id},
            }
        },
    }


def _stripe_signature_header(payload: bytes, secret: str, *, timestamp: int | None = None) -> str:
    ts = int(time.time()) if timestamp is None else timestamp
    signed_payload = f"{ts}.".encode("utf-8") + payload
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


ENV_KEYS = [
    "VENDORVERDICT_API_DB_PATH",
    "VENDORVERDICT_API_EXPORT_DIR",
    "VENDORVERDICT_API_LIVE_EVIDENCE",
    "VENDORVERDICT_STRIPE_WEBHOOK_ENABLED",
    "VENDORVERDICT_STRIPE_WEBHOOK_SECRET",
    "VENDORVERDICT_STRIPE_WEBHOOK_TOLERANCE_SECONDS",
    "VENDORVERDICT_AUTH_ENABLED",
    "VENDORVERDICT_AUTH_USERNAME",
    "VENDORVERDICT_AUTH_PASSWORD",
    "VENDORVERDICT_AUTH_SECRET",
]


if __name__ == "__main__":
    unittest.main()
