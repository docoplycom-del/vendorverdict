"""Payment Protocol support for VendorVerdict premium reports."""

from .pricing import PREMIUM_VENDOR_DOSSIER, PaidProduct
from .premium_report import (
    render_payment_offer,
    render_premium_dossier,
    render_upgrade_cta,
    wants_premium_report,
)

__all__ = [
    "PaidProduct",
    "PREMIUM_VENDOR_DOSSIER",
    "render_payment_offer",
    "render_premium_dossier",
    "render_upgrade_cta",
    "wants_premium_report",
]
