from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Confidence = Literal["High", "Medium", "Low"]


@dataclass(frozen=True)
class VendorEvidence:
    """Public evidence and fallback facts for a vendor.

    MVP note: live evidence collection will later populate/override these fields.
    For the first skeleton, we use curated fallback URLs and notes so the demo
    remains reliable even without internet or third-party API keys.
    """

    name: str
    category: str
    security_url: str = ""
    pricing_url: str = ""
    privacy_url: str = ""
    docs_url: str = ""
    known_strengths: tuple[str, ...] = field(default_factory=tuple)
    known_risks: tuple[str, ...] = field(default_factory=tuple)
    fallback_scores: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class VendorRequest:
    vendors: tuple[str, ...]
    use_case: str
    raw_query: str
    team_size: str | None = None
    business_type: str | None = None
    region: str | None = None
    data_sensitivity: str = "medium"
    missing_fields: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class VendorScore:
    vendor: str
    security: int
    privacy: int
    pricing_predictability: int
    lock_in: int
    sme_fit: int
    operational_maturity: int
    overall: int
    confidence: Confidence
    evidence_urls: tuple[str, ...] = field(default_factory=tuple)
    strengths: tuple[str, ...] = field(default_factory=tuple)
    risks: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class VendorVerdict:
    request: VendorRequest
    scores: tuple[VendorScore, ...]
    recommendation: VendorScore | None
    assumptions: tuple[str, ...]
    due_diligence_email: str
    confidence: Confidence
