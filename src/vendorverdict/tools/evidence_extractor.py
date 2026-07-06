from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from typing import Iterable

from vendorverdict.models import Confidence, EvidenceFinding


# Production V1 is deliberately deterministic: no LLM dependency is required to
# extract common vendor-risk signals from public source pages. The extractor is
# conservative: a finding means "this public page mentions this signal", not
# "the vendor is certified/compliant/safe".
SIGNAL_PATTERNS: dict[str, tuple[str, str, Confidence, tuple[str, ...]]] = {
    "soc_2": (
        "SOC 2",
        "security",
        "High",
        (r"\bSOC\s*2\b", r"\bSOC\s*II\b"),
    ),
    "iso_27001": (
        "ISO 27001",
        "security",
        "High",
        (r"\bISO(?:/IEC)?\s*27001\b", r"\bISO\s*27001\b"),
    ),
    "gdpr": (
        "GDPR",
        "privacy",
        "High",
        (r"\bGDPR\b", r"General Data Protection Regulation"),
    ),
    "dpa": (
        "Data Processing Agreement / DPA",
        "privacy",
        "High",
        (r"\bDPA\b", r"Data Processing (?:Addendum|Agreement)"),
    ),
    "subprocessors": (
        "Subprocessors",
        "privacy",
        "High",
        (r"\bsub[- ]?processors?\b",),
    ),
    "sso": (
        "Single sign-on / SSO",
        "security",
        "Medium",
        (r"\bSSO\b", r"single sign[- ]?on"),
    ),
    "mfa": (
        "Multi-factor authentication / MFA",
        "security",
        "Medium",
        (r"\bMFA\b", r"multi[- ]?factor authentication", r"two[- ]?factor authentication", r"\b2FA\b"),
    ),
    "rbac": (
        "Role-based access control / RBAC",
        "security",
        "Medium",
        (r"\bRBAC\b", r"role[- ]?based access control", r"role based access control", r"user permissions"),
    ),
    "audit_logs": (
        "Audit logs",
        "security",
        "Medium",
        (r"audit logs?", r"audit trail", r"activity logs?"),
    ),
    "encryption": (
        "Encryption",
        "security",
        "Medium",
        (r"encryption", r"encrypted", r"\bTLS\b", r"at rest", r"in transit"),
    ),
    "data_export": (
        "Data export / portability",
        "portability",
        "Medium",
        (r"data export", r"export your data", r"\bexport\b", r"download your data"),
    ),
    "data_retention": (
        "Data retention / deletion",
        "privacy",
        "Medium",
        (r"data retention", r"retention", r"deletion", r"delete your data", r"account closure"),
    ),
    "ai_training_policy": (
        "AI training policy",
        "privacy",
        "Medium",
        (r"model training", r"train(?:ing)? (?:our )?(?:AI|models)", r"used to train", r"artificial intelligence"),
    ),
    "status_page": (
        "Status / uptime signal",
        "operational",
        "Medium",
        (r"status page", r"uptime", r"incidents?", r"service status"),
    ),
}


def extract_evidence_findings(
    html_or_text: str,
    *,
    vendor: str,
    source_url: str,
    source_label: str,
    checked_at: str | None = None,
) -> tuple[EvidenceFinding, ...]:
    """Extract concrete vendor-risk signals from an official source page.

    The extraction is regex-based by design so the first production version is
    fast, testable, deterministic, and cheap. It can later be paired with an LLM
    summarizer, but the stored finding schema should remain stable.
    """
    text = normalize_text(html_or_text)
    if not text:
        return ()

    timestamp = checked_at or datetime.now(UTC).isoformat()
    findings: list[EvidenceFinding] = []
    seen_signals: set[str] = set()

    for signal, (label, _category, confidence, patterns) in SIGNAL_PATTERNS.items():
        match = _first_match(text, patterns)
        if not match or signal in seen_signals:
            continue
        seen_signals.add(signal)
        findings.append(
            EvidenceFinding(
                vendor=vendor,
                signal=signal,
                label=label,
                source_label=source_label,
                source_url=source_url,
                snippet=_snippet_around(text, match.start(), match.end()),
                confidence=confidence,
                checked_at=timestamp,
            )
        )
    return tuple(findings)


def summarize_findings(findings: Iterable[EvidenceFinding]) -> str:
    findings = tuple(findings)
    if not findings:
        return "No concrete compliance/security signals were extracted from reachable source pages."
    labels = ", ".join(sorted({finding.label for finding in findings}))
    return f"Extracted {len(findings)} evidence-backed signal(s): {labels}."


def normalize_text(html_or_text: str) -> str:
    text = html_or_text or ""
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _first_match(text: str, patterns: tuple[str, ...]) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match
    return None


def _snippet_around(text: str, start: int, end: int, radius: int = 120) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].strip()
    if left > 0:
        snippet = "..." + snippet
    if right < len(text):
        snippet = snippet + "..."
    return snippet
