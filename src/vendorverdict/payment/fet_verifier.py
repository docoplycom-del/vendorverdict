from __future__ import annotations

import os
from decimal import Decimal
from typing import Any


def demo_payment_mode_enabled() -> bool:
    """Return True when hackathon/demo mode should accept committed payments.

    Real chain verification can be enabled by setting VENDORVERDICT_PAYMENT_DEMO_MODE=0.
    """

    return os.getenv("VENDORVERDICT_PAYMENT_DEMO_MODE", "1").lower() in {"1", "true", "yes", "on"}


def fet_to_attofet(amount_fet: str) -> int:
    return int(Decimal(amount_fet) * Decimal(10**18))


def verify_fet_payment_to_agent(
    transaction_id: str,
    expected_amount_fet: str,
    sender_fet_address: str | None,
    recipient_wallet: Any,
    logger: Any | None = None,
) -> bool:
    """Verify a direct FET payment to the agent wallet.

    In demo mode this returns True for any non-empty transaction id, letting judges
    see the Payment Protocol flow without requiring real funds. In production mode
    it queries the Fetch.ai ledger through cosmpy and checks recipient/amount/sender.
    """

    if demo_payment_mode_enabled():
        if logger:
            logger.info("Payment demo mode is enabled; accepting committed payment for demo flow.")
        return bool(transaction_id)

    if not transaction_id or not sender_fet_address or recipient_wallet is None:
        if logger:
            logger.error("Missing transaction id, sender wallet, or recipient wallet for payment verification.")
        return False

    try:
        from cosmpy.aerial.client import LedgerClient, NetworkConfig
    except Exception as exc:  # pragma: no cover - depends on optional runtime imports
        if logger:
            logger.error(f"cosmpy import failed during payment verification: {exc}")
        return False

    use_testnet = os.getenv("FET_USE_TESTNET", "true").lower() in {"1", "true", "yes", "on"}
    network_config = NetworkConfig.fetchai_stable_testnet() if use_testnet else NetworkConfig.fetchai_mainnet()
    denom = "atestfet" if use_testnet else "afet"

    try:  # pragma: no cover - chain access is not used in unit tests
        ledger = LedgerClient(network_config)
        tx_response = ledger.query_tx(transaction_id)
        if not tx_response.is_successful():
            if logger:
                logger.error("Payment transaction was not successful.")
            return False

        expected_recipient = str(recipient_wallet.address())
        expected_amount = fet_to_attofet(expected_amount_fet)
        recipient_found = False
        sender_found = False
        amount_found = False

        for event_type, attrs in tx_response.events.items():
            if event_type != "transfer":
                continue
            if attrs.get("recipient") == expected_recipient:
                recipient_found = True
            if attrs.get("sender") == sender_fet_address:
                sender_found = True
            amount_str = attrs.get("amount", "")
            if amount_str.endswith(denom):
                amount_value = int(amount_str.replace(denom, ""))
                if amount_value >= expected_amount:
                    amount_found = True

        return recipient_found and sender_found and amount_found
    except Exception as exc:
        if logger:
            logger.error(f"Payment verification failed: {exc}")
        return False
