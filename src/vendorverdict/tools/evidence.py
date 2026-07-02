from __future__ import annotations

from dataclasses import replace

from vendorverdict.data_loader import load_fallback_vendors
from vendorverdict.models import VendorEvidence


class EvidenceCollector:
    """Collect vendor evidence.

    Current MVP behavior: use curated fallback evidence for reliability.
    Next iteration: add live search/fetching and merge official-source findings
    into the returned VendorEvidence object.
    """

    def __init__(self) -> None:
        self._vendors = load_fallback_vendors()

    @property
    def known_vendor_names(self) -> list[str]:
        return sorted((vendor.name for vendor in self._vendors.values()), key=str.lower)

    def get(self, vendor_name: str) -> VendorEvidence:
        vendor = self._vendors.get(vendor_name.lower())
        if vendor:
            return vendor
        return self._unknown_vendor(vendor_name)

    def get_many(self, vendor_names: list[str] | tuple[str, ...]) -> list[VendorEvidence]:
        return [self.get(name) for name in vendor_names]

    def _unknown_vendor(self, vendor_name: str) -> VendorEvidence:
        # Unknown vendors should still produce a usable output with low confidence.
        return VendorEvidence(
            name=vendor_name.strip(),
            category="unknown SaaS",
            known_strengths=("Public evidence not yet collected; manual review recommended.",),
            known_risks=("No curated fallback data is available yet, so confidence is low.",),
            fallback_scores={
                "security": 60,
                "privacy": 60,
                "pricing_predictability": 60,
                "lock_in": 55,
                "sme_fit": 60,
                "operational_maturity": 55,
            },
        )

    def with_live_evidence_placeholder(self, evidence: VendorEvidence) -> VendorEvidence:
        """Reserved extension point for live web research."""
        return replace(evidence)
