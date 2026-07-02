from __future__ import annotations

import re

from .models import VendorRequest

SENSITIVE_TERMS = (
    "client",
    "customer",
    "employee",
    "payroll",
    "financial",
    "finance",
    "health",
    "patient",
    "legal",
    "contract",
    "confidential",
    "personal data",
    "pii",
)

LOW_SENSITIVITY_TERMS = (
    "public",
    "marketing",
    "social media",
    "blog",
    "website content",
)

REGION_PATTERNS = {
    "UK": r"\b(uk|united kingdom|britain|london)\b",
    "EU": r"\b(eu|europe|european union|gdpr)\b",
    "US": r"\b(us|usa|united states|america)\b",
}


def parse_vendor_request(raw_query: str, known_vendor_names: list[str]) -> VendorRequest:
    """Extract vendors and use-case hints from a natural-language query.

    This is deliberately deterministic for the skeleton. Later we can replace or
    augment it with an LLM parser, but a deterministic parser gives us reliable
    demo behavior and easier tests.
    """
    query = " ".join(raw_query.strip().split())
    query_lower = query.lower()

    vendors = _extract_known_vendors(query, known_vendor_names)
    use_case = _extract_use_case(query)
    team_size = _extract_team_size(query)
    business_type = _extract_business_type(query)
    region = _extract_region(query_lower)
    data_sensitivity = _infer_data_sensitivity(query_lower)

    missing: list[str] = []
    # A single named vendor is a valid request: VendorVerdict should run a
    # one-vendor risk audit instead of forcing every interaction to be a
    # comparison. Zero vendors still requires a clarifying question.
    if len(vendors) == 0:
        missing.append("vendors")
    if not use_case:
        missing.append("use_case")
        use_case = "the described business workflow"

    return VendorRequest(
        vendors=tuple(vendors),
        use_case=use_case,
        raw_query=raw_query,
        team_size=team_size,
        business_type=business_type,
        region=region,
        data_sensitivity=data_sensitivity,
        missing_fields=tuple(missing),
    )


def _extract_known_vendors(query: str, known_vendor_names: list[str]) -> list[str]:
    """Find known vendors while preserving the order used by the user.

    We collect match positions first rather than iterating alphabetically, so
    "Compare Notion, Airtable, and Coda" returns that exact order. Overlap
    protection keeps longer names such as "Google Workspace" intact.
    """
    matches: list[tuple[int, int, str]] = []
    for name in known_vendor_names:
        pattern = rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])"
        for match in re.finditer(pattern, query, flags=re.IGNORECASE):
            matches.append((match.start(), match.end(), _canonical_case(name, known_vendor_names)))

    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    found: list[str] = []
    occupied_spans: list[tuple[int, int]] = []
    for start, end, canonical in matches:
        overlaps = any(not (end <= used_start or start >= used_end) for used_start, used_end in occupied_spans)
        if overlaps or canonical in found:
            continue
        found.append(canonical)
        occupied_spans.append((start, end))
    return found


def _canonical_case(name: str, known_vendor_names: list[str]) -> str:
    for candidate in known_vendor_names:
        if candidate.lower() == name.lower():
            return candidate
    return name


def _extract_use_case(query: str) -> str:
    patterns = [
        r"\bfor\s+(.+?)(?:\.\s|\.?$|\s+rank\b|\s+compare\b|\s+give\b)",
        r"\bto\s+(.+?)(?:\.\s|\.?$|\s+rank\b|\s+compare\b|\s+give\b)",
        r"\buse(?: them| it)?\s+for\s+(.+?)(?:\.\s|\.?$|\s+rank\b|\s+compare\b|\s+give\b)",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            value = _clean_use_case(match.group(1).strip(" ."))
            return value[:1].lower() + value[1:] if value else ""
    return ""


def _clean_use_case(value: str) -> str:
    # Keep the actual job-to-be-done, not team/location context.
    stop_patterns = [
        r"\s+for\s+(?:a|an|the)?\s*\d+\s*[- ]?(?:person|people)\b.*$",
        r"\s+for\s+(?:a|an|the)?\s*(?:consulting startup|startup|small business|student society|agency|nonprofit|charity|freelance team)\b.*$",
        r"\s+in\s+(?:the\s+)?(?:UK|United Kingdom|EU|Europe|US|USA|United States)\b.*$",
    ]
    cleaned = value
    for pattern in stop_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" .")


def _extract_team_size(query: str) -> str | None:
    patterns = [
        r"\b(\d+)\s*[- ]?person\b",
        r"\b(\d+)\s*[- ]?people\b",
        r"\bteam of\s+(\d+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return f"{match.group(1)} people"
    return None


def _extract_business_type(query: str) -> str | None:
    patterns = [
        r"\b(consulting startup|startup|small business|student society|agency|nonprofit|charity|freelance team)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None


def _extract_region(query_lower: str) -> str | None:
    for region, pattern in REGION_PATTERNS.items():
        if re.search(pattern, query_lower, flags=re.IGNORECASE):
            return region
    return None


def _infer_data_sensitivity(query_lower: str) -> str:
    if any(term in query_lower for term in SENSITIVE_TERMS):
        return "medium-high"
    if any(term in query_lower for term in LOW_SENSITIVITY_TERMS):
        return "low"
    return "medium"
