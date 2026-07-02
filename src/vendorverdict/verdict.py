from __future__ import annotations

from .emailer import build_due_diligence_email
from .models import VendorRequest, VendorVerdict
from .parser import parse_vendor_request
from .scoring import rank_vendors
from .tools.evidence import EvidenceCollector


MISSING_VENDOR_PROMPT = (
    "Which vendors should I compare? For example: Notion, Airtable, Coda, Asana, Monday.com, or ClickUp."
)
MISSING_USE_CASE_PROMPT = (
    "What will you use them for: client project data, internal docs, CRM, project management, or something else?"
)


def build_vendor_verdict(raw_query: str, collector: EvidenceCollector | None = None) -> VendorVerdict:
    collector = collector or EvidenceCollector()
    request = parse_vendor_request(raw_query, collector.known_vendor_names)
    evidences = collector.get_many(request.vendors)
    scores = rank_vendors(evidences, request) if evidences else tuple()
    recommendation = scores[0] if scores else None
    assumptions = _build_assumptions(request)
    email = build_due_diligence_email(recommendation, request)
    confidence = _overall_confidence(scores)
    return VendorVerdict(
        request=request,
        scores=scores,
        recommendation=recommendation,
        assumptions=assumptions,
        due_diligence_email=email,
        confidence=confidence,
    )


def render_response(raw_query: str, use_live_evidence: bool | None = None) -> str:
    collector = EvidenceCollector(use_live_checks=use_live_evidence)
    verdict = build_vendor_verdict(raw_query, collector=collector)
    request = verdict.request

    if request.missing_fields:
        prompts = []
        if "vendors" in request.missing_fields:
            prompts.append(MISSING_VENDOR_PROMPT)
        if "use_case" in request.missing_fields:
            prompts.append(MISSING_USE_CASE_PROMPT)
        return "\n".join(prompts)

    winner = verdict.recommendation
    if not winner:
        return "I could not identify enough vendors to compare. Please name 2–5 vendors and the use case."

    lines: list[str] = []
    lines.append("🧾 VendorVerdict: SaaS Procurement Review")
    lines.append("")
    lines.append("I understood your goal:")
    lines.append(f"Compare {', '.join(request.vendors)} for {request.use_case}.")
    lines.append("")
    lines.append("Assumptions:")
    for assumption in verdict.assumptions:
        lines.append(f"- {assumption}")
    lines.append("")
    lines.append("🏆 Recommendation:")
    lines.append(
        f"{winner.vendor} is the safest MVP choice because it has the strongest overall balance "
        f"for this use case in the current rubric."
    )
    lines.append("")
    lines.append("Ranked verdict:")
    lines.append(
        "| Rank | Vendor | Overall | Security | Privacy | Pricing predictability | Portability / low lock-in | SME fit | Confidence |"
    )
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---|")
    for idx, score in enumerate(verdict.scores, start=1):
        lines.append(
            f"| {idx} | {score.vendor} | {score.overall} | {score.security} | {score.privacy} | "
            f"{score.pricing_predictability} | {score.lock_in} | {score.sme_fit} | {score.confidence} |"
        )
    lines.append("")
    lines.append("Vendor-by-vendor notes:")
    for score in verdict.scores:
        lines.append(f"\n{score.vendor}")
        lines.append("- Strengths:")
        for strength in score.strengths[:3] or ("No curated strengths available yet.",):
            lines.append(f"  - {strength}")
        lines.append("- Risks to check:")
        for risk in score.risks[:3] or ("No curated risk notes available yet.",):
            lines.append(f"  - {risk}")
        if score.live_findings:
            lines.append("- Live evidence:")
            for finding in score.live_findings:
                lines.append(f"  - {finding}")
    lines.append("")
    lines.append("Due-diligence email:")
    lines.append("```text")
    lines.append(verdict.due_diligence_email)
    lines.append("```")
    lines.append("")
    lines.append("Sources and confidence:")
    for score in verdict.scores:
        if score.source_checks:
            lines.append(f"- {score.vendor} official-source checks:")
            for check in score.source_checks:
                status = "reachable" if check.ok else "not reachable"
                status_code = f" HTTP {check.status_code}" if check.status_code is not None else ""
                redirected = f" (redirected to {check.final_url})" if check.final_url else ""
                lines.append(f"  - {check.label}: {status}{status_code} — {check.url}{redirected}")
        elif score.evidence_urls:
            joined_urls = ", ".join(score.evidence_urls)
            lines.append(f"- {score.vendor}: fallback official-source targets: {joined_urls}")
        else:
            lines.append(f"- {score.vendor}: no curated official-source URLs yet; low confidence.")
    lines.append(
        f"- Overall confidence: {verdict.confidence}. This is procurement guidance based on public/fallback evidence, not legal or security-audit advice."
    )
    lines.append("")
    lines.append("Next step:")
    lines.append(f"Send the due-diligence email to {winner.vendor}, then rerun VendorVerdict with the vendor's answers.")
    return "\n".join(lines)


def _build_assumptions(request: VendorRequest) -> tuple[str, ...]:
    assumptions = []
    assumptions.append(f"Data sensitivity is treated as {request.data_sensitivity} based on the wording of the request.")
    if request.team_size:
        assumptions.append(f"Team size: {request.team_size}.")
    else:
        assumptions.append("Team size was not specified, so I assume a small SME/team context.")
    if request.region:
        assumptions.append(f"Region: {request.region}.")
    else:
        assumptions.append("Region was not specified, so regulatory analysis is general rather than jurisdiction-specific.")
    return tuple(assumptions)


def _overall_confidence(scores) -> str:
    if not scores:
        return "Low"
    if all(score.confidence == "High" for score in scores):
        return "High"
    if any(score.confidence == "Medium" for score in scores):
        return "Medium"
    return "Low"
