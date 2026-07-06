from __future__ import annotations

from .agents import VendorVerdictMultiAgentOrchestrator
from .models import VendorVerdict
from .tools.evidence import EvidenceCollector


MISSING_VENDOR_PROMPT = (
    "Which vendors should I compare? For example: Notion, Airtable, Coda, Asana, Monday.com, or ClickUp."
)
MISSING_USE_CASE_PROMPT = (
    "What will you use them for: client project data, internal docs, CRM, project management, or something else?"
)


def build_vendor_verdict(raw_query: str, collector: EvidenceCollector | None = None) -> VendorVerdict:
    """Build a VendorVerdict through specialist worker-agent collaboration."""
    orchestrator = VendorVerdictMultiAgentOrchestrator(collector=collector or EvidenceCollector())
    return orchestrator.run(raw_query)


def render_response(raw_query: str, use_live_evidence: bool | None = None) -> str:
    collector = EvidenceCollector(use_live_checks=use_live_evidence)
    verdict = build_vendor_verdict(raw_query, collector=collector)
    return render_verdict(verdict)


def render_verdict(verdict: VendorVerdict) -> str:
    """Render an already-built verdict.

    Production paths use this to save exactly the same verdict that was shown to
    the user, avoiding duplicate live source checks or drift between persisted
    and displayed reports.
    """

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
        return "I could not identify a vendor to review. Please name at least one vendor and the use case."

    is_single_vendor_audit = len(request.vendors) == 1

    lines: list[str] = []
    if is_single_vendor_audit:
        lines.append("🧾 VendorVerdict: SaaS Vendor Risk Review")
        lines.append("")
        lines.append("I understood your goal:")
        lines.append(f"Review {request.vendors[0]} for {request.use_case}.")
    else:
        lines.append("🧾 VendorVerdict: SaaS Procurement Review")
        lines.append("")
        lines.append("I understood your goal:")
        lines.append(f"Compare {', '.join(request.vendors)} for {request.use_case}.")
    lines.append("")
    lines.append("Assumptions:")
    for assumption in verdict.assumptions:
        lines.append(f"- {assumption}")
    lines.append("")
    lines.append("Multi-agent collaboration completed:")
    for idx, step in enumerate(verdict.collaboration_steps, start=1):
        lines.append(f"{idx}. {step}")
    lines.append("")

    if is_single_vendor_audit:
        decision, decision_reason = _single_vendor_decision(winner)
        lines.append("🏁 Vendor decision:")
        lines.append(f"{decision}: {winner.vendor} {decision_reason}")
        lines.append("")
        lines.append("Risk scorecard:")
        lines.append(
            "| Vendor | Overall | Security | Privacy | Pricing predictability | Portability / low lock-in | SME fit | Confidence |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
        lines.append(
            f"| {winner.vendor} | {winner.overall} | {winner.security} | {winner.privacy} | "
            f"{winner.pricing_predictability} | {winner.lock_in} | {winner.sme_fit} | {winner.confidence} |"
        )
    else:
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
    lines.append("Vendor-by-vendor notes:" if not is_single_vendor_audit else "Vendor notes:")
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
        if score.extracted_findings:
            lines.append("- Evidence-backed findings:")
            for finding in score.extracted_findings[:6]:
                snippet = _shorten(finding.snippet, 180)
                lines.append(
                    f"  - {finding.label} [{finding.source_label}, {finding.confidence} confidence]: {snippet}"
                )
            remaining = len(score.extracted_findings) - 6
            if remaining > 0:
                lines.append(f"  - +{remaining} more extracted finding(s) in the stored report.")
    lines.append("")
    lines.append("Due-diligence email:")
    lines.append("```text")
    lines.append(verdict.due_diligence_email)
    lines.append("```")
    lines.append("")
    if verdict.critic_warnings:
        lines.append("Critic Agent notes:")
        for warning in verdict.critic_warnings:
            lines.append(f"- {warning}")
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
    if is_single_vendor_audit:
        lines.append(f"Send the due-diligence email to {winner.vendor}, then rerun VendorVerdict with the vendor's answers before rollout.")
    else:
        lines.append(f"Send the due-diligence email to {winner.vendor}, then rerun VendorVerdict with the vendor's answers.")
    return "\n".join(lines)


def _shorten(text: str, limit: int) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def _single_vendor_decision(score) -> tuple[str, str]:
    """Return a concise go/caution/avoid-style decision for audit mode."""
    if score.overall >= 80 and score.security >= 75 and score.privacy >= 75:
        return (
            "Good candidate",
            "looks suitable for this use case, subject to confirming the due-diligence questions below.",
        )
    if score.overall >= 70:
        return (
            "Proceed with caution",
            "may be usable, but security, privacy, pricing, and portability answers should be confirmed before storing sensitive business data.",
        )
    return (
        "Needs further review",
        "should not be selected for this use case until the key risk questions are answered.",
    )
