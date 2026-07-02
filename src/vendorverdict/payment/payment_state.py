from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PendingPremiumPayment:
    reference: str
    buyer: str
    prompt: str
    sku: str
    amount_fet: str
