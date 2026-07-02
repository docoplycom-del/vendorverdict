from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PaidProduct:
    """A monetizable VendorVerdict product."""

    sku: str
    name: str
    price_fet: str
    description: str


def _premium_price() -> str:
    return os.getenv("VENDORVERDICT_PREMIUM_PRICE_FET", "0.05")


PREMIUM_VENDOR_DOSSIER = PaidProduct(
    sku="premium_vendor_dossier",
    name="Premium Vendor Dossier",
    price_fet=_premium_price(),
    description=(
        "Expanded procurement memo, approval conditions, risk register, rollout checklist, "
        "extended due-diligence questionnaire, and evidence appendix."
    ),
)
