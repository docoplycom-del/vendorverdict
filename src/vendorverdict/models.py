from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Confidence = Literal["High", "Medium", "Low"]


@dataclass(frozen=True)
class EvidenceFinding:
    """A concrete finding extracted from an official vendor source page.

    Findings are intentionally conservative. They mean VendorVerdict found a
    public signal in a source page, not that the vendor is definitively
    compliant or safe. This makes production reports more trustworthy by
    backing scoring notes with source URLs, snippets, confidence, and timestamps.
    """

    vendor: str
    signal: str
    label: str
    source_label: str
    source_url: str
    snippet: str
    confidence: Confidence
    checked_at: str | None = None


@dataclass(frozen=True)
class SourceCheck:
    """Result of checking an official vendor source URL.

    This keeps live evidence separate from fallback evidence, so the demo can
    degrade gracefully if a vendor page or network request fails. Live checks can
    also carry extracted findings for production-grade report citations.
    """

    label: str
    # The URL we intended to check from our official-source registry.
    url: str
    ok: bool
    status_code: int | None = None
    note: str = ""
    # Final URL after redirects, if different. This avoids making a
    # redirected vendor page look like the original configured source.
    final_url: str | None = None
    findings: tuple[EvidenceFinding, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvidenceItem:
    """Production-oriented evidence record used for stored reports.

    EvidenceItem is intentionally small and serializable.  It gives each report
    a repeatable evidence appendix with a claim, source URL, retrieval status,
    confidence, and timestamp.  Later production versions can enrich this with
    page excerpts and LLM-extracted compliance signals.
    """

    vendor: str
    label: str
    claim: str
    source_url: str
    source_type: Literal["live", "fallback"]
    confidence: Confidence
    ok: bool | None = None
    status_code: int | None = None
    final_url: str | None = None
    note: str = ""
    checked_at: str | None = None


@dataclass(frozen=True)
class VendorEvidence:
    """Public evidence and fallback facts for a vendor.

    Fallback evidence keeps the demo reliable. Live source checks add visible
    tool use when internet access is available.
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
    source_checks: tuple[SourceCheck, ...] = field(default_factory=tuple)
    live_findings: tuple[str, ...] = field(default_factory=tuple)
    extracted_findings: tuple[EvidenceFinding, ...] = field(default_factory=tuple)


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
    source_checks: tuple[SourceCheck, ...] = field(default_factory=tuple)
    live_findings: tuple[str, ...] = field(default_factory=tuple)
    extracted_findings: tuple[EvidenceFinding, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class VendorVerdict:
    request: VendorRequest
    scores: tuple[VendorScore, ...]
    recommendation: VendorScore | None
    assumptions: tuple[str, ...]
    due_diligence_email: str
    confidence: Confidence
    collaboration_steps: tuple[str, ...] = field(default_factory=tuple)
    critic_warnings: tuple[str, ...] = field(default_factory=tuple)
