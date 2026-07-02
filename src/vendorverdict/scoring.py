from __future__ import annotations

from .models import VendorEvidence, VendorRequest, VendorScore

WEIGHTS = {
    "security": 25,
    "privacy": 20,
    "pricing_predictability": 15,
    "lock_in": 15,
    "sme_fit": 15,
    "operational_maturity": 10,
}

DEFAULT_SCORE = 60


def score_vendor(evidence: VendorEvidence, request: VendorRequest) -> VendorScore:
    """Score a vendor using the MVP's transparent weighted rubric."""
    scores = evidence.fallback_scores
    security = _bounded(scores.get("security", DEFAULT_SCORE))
    privacy = _bounded(scores.get("privacy", DEFAULT_SCORE))
    pricing = _bounded(scores.get("pricing_predictability", DEFAULT_SCORE))
    lock_in = _bounded(scores.get("lock_in", DEFAULT_SCORE))
    sme_fit = _bounded(scores.get("sme_fit", DEFAULT_SCORE))
    maturity = _bounded(scores.get("operational_maturity", DEFAULT_SCORE))

    # Use live official-source checks as small evidence nudges, not as a full
    # audit. This keeps the rubric transparent and avoids overclaiming.
    if _source_ok(evidence, "security"):
        security += 2
        maturity += 1
    if _source_ok(evidence, "privacy"):
        privacy += 2
    if _source_ok(evidence, "pricing"):
        pricing += 1
    if _source_ok(evidence, "docs"):
        maturity += 1

    # Nudge the scoring for sensitive data: security/privacy matter more in the
    # explanation, but keep weights simple for the MVP. This preserves the fixed
    # rubric while penalizing obviously weaker sensitive-data fit.
    if request.data_sensitivity == "medium-high":
        if security < 75:
            security -= 3
        if privacy < 75:
            privacy -= 3

    component_scores = {
        "security": _bounded(security),
        "privacy": _bounded(privacy),
        "pricing_predictability": _bounded(pricing),
        "lock_in": lock_in,
        "sme_fit": sme_fit,
        "operational_maturity": _bounded(maturity),
    }
    weighted = sum(component_scores[key] * weight for key, weight in WEIGHTS.items()) / 100
    confidence = _confidence_for(evidence)

    urls = tuple(
        url
        for url in (
            evidence.security_url,
            evidence.pricing_url,
            evidence.privacy_url,
            evidence.docs_url,
        )
        if url
    )

    return VendorScore(
        vendor=evidence.name,
        security=component_scores["security"],
        privacy=component_scores["privacy"],
        pricing_predictability=component_scores["pricing_predictability"],
        lock_in=component_scores["lock_in"],
        sme_fit=component_scores["sme_fit"],
        operational_maturity=component_scores["operational_maturity"],
        overall=round(weighted),
        confidence=confidence,
        evidence_urls=urls,
        strengths=evidence.known_strengths,
        risks=evidence.known_risks,
        source_checks=evidence.source_checks,
        live_findings=evidence.live_findings,
    )


def rank_vendors(vendors: list[VendorEvidence], request: VendorRequest) -> tuple[VendorScore, ...]:
    scores = [score_vendor(vendor, request) for vendor in vendors]
    return tuple(sorted(scores, key=lambda score: score.overall, reverse=True))


def _confidence_for(evidence: VendorEvidence) -> str:
    reachable_count = sum(1 for check in evidence.source_checks if check.ok)
    official_url_count = sum(
        1 for url in (evidence.security_url, evidence.pricing_url, evidence.privacy_url, evidence.docs_url) if url
    )
    if reachable_count >= 3:
        return "High"
    if reachable_count >= 1 or (official_url_count >= 3 and evidence.fallback_scores):
        return "Medium"
    return "Low"


def _source_ok(evidence: VendorEvidence, label: str) -> bool:
    return any(check.label == label and check.ok for check in evidence.source_checks)


def _bounded(value: int) -> int:
    return max(0, min(100, int(value)))
