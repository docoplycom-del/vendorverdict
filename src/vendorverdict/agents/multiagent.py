from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from vendorverdict.emailer import build_due_diligence_email
from vendorverdict.models import Confidence, VendorEvidence, VendorRequest, VendorScore, VendorVerdict
from vendorverdict.parser import parse_vendor_request
from vendorverdict.scoring import rank_vendors
from vendorverdict.tools.evidence import EvidenceCollector


@dataclass(frozen=True)
class CollaborationResult:
    """A small trace object returned by each specialist worker agent."""

    step: str
    warnings: tuple[str, ...] = ()


class ProcurementIntentAgent:
    """Extracts vendors, use case, team size, region, and sensitivity."""

    def parse(self, raw_query: str, known_vendor_names: Iterable[str]) -> tuple[VendorRequest, CollaborationResult]:
        request = parse_vendor_request(raw_query, known_vendor_names)
        if request.missing_fields:
            missing = ", ".join(request.missing_fields)
            return request, CollaborationResult(
                step=f"Procurement Intent Agent parsed the request and flagged missing fields: {missing}.",
                warnings=(f"Missing required field(s): {missing}.",),
            )
        vendor_word = "vendor" if len(request.vendors) == 1 else "vendors"
        return request, CollaborationResult(
            step=(
                f"Procurement Intent Agent extracted {len(request.vendors)} {vendor_word}, "
                f"the use case, team size, region, and data sensitivity."
            )
        )


class EvidenceAgent:
    """Collects fallback evidence and live official-source checks."""

    def collect(self, request: VendorRequest, collector: EvidenceCollector) -> tuple[list[VendorEvidence], CollaborationResult]:
        evidence = collector.get_many(request.vendors)
        total_checks = sum(len(item.source_checks) for item in evidence)
        reachable_checks = sum(1 for item in evidence for check in item.source_checks if check.ok)

        if collector.use_live_checks and total_checks:
            step = (
                f"Evidence Agent checked official vendor sources and found "
                f"{reachable_checks}/{total_checks} reachable configured sources."
            )
        elif collector.use_live_checks:
            step = "Evidence Agent attempted live source checks and used fallback evidence where live targets were unavailable."
        else:
            step = "Evidence Agent used the curated fallback evidence layer for a deterministic review."

        warnings: list[str] = []
        for item in evidence:
            if collector.use_live_checks and item.source_checks and not any(check.ok for check in item.source_checks):
                warnings.append(f"No configured official sources were reachable for {item.name}; fallback evidence was used.")
        return evidence, CollaborationResult(step=step, warnings=tuple(warnings))


class RiskScoringAgent:
    """Applies VendorVerdict's procurement-risk scoring rubric."""

    def score(self, evidence: list[VendorEvidence], request: VendorRequest) -> tuple[tuple[VendorScore, ...], CollaborationResult]:
        scores = rank_vendors(evidence, request) if evidence else tuple()
        if len(scores) == 1:
            step = "Risk Scoring Agent produced a single-vendor risk scorecard."
        else:
            step = "Risk Scoring Agent scored and ranked vendors with the weighted procurement-risk rubric."
        return scores, CollaborationResult(step=step)


class RecommendationAgent:
    """Chooses the recommended vendor or classifies a single-vendor audit."""

    def choose(self, scores: tuple[VendorScore, ...], request: VendorRequest) -> tuple[VendorScore | None, CollaborationResult]:
        recommendation = scores[0] if scores else None
        if recommendation is None:
            return None, CollaborationResult(
                step="Recommendation Agent could not choose a vendor because no scores were available.",
                warnings=("No scored vendor was available for recommendation.",),
            )
        if len(request.vendors) == 1:
            step = f"Recommendation Agent classified {recommendation.vendor}'s practical procurement risk."
        else:
            step = f"Recommendation Agent selected {recommendation.vendor} as the strongest practical choice."
        return recommendation, CollaborationResult(step=step)


class EmailAgent:
    """Generates the ready-to-send vendor due-diligence email."""

    def draft(self, recommendation: VendorScore | None, request: VendorRequest) -> tuple[str, CollaborationResult]:
        email = build_due_diligence_email(recommendation, request)
        vendor = recommendation.vendor if recommendation else "the selected vendor"
        return email, CollaborationResult(step=f"Email Agent drafted the due-diligence email for {vendor}.")


class CriticAgent:
    """Reviews confidence and evidence gaps before the final ASI:One response."""

    def review(
        self,
        request: VendorRequest,
        scores: tuple[VendorScore, ...],
        evidence: list[VendorEvidence],
    ) -> tuple[Confidence, CollaborationResult]:
        warnings: list[str] = []
        if not scores:
            return "Low", CollaborationResult(
                step="Critic Agent reviewed the response and downgraded confidence because no scores were available.",
                warnings=("No scored vendors were available.",),
            )

        for score in scores:
            if score.confidence == "Low":
                warnings.append(f"{score.vendor} has low-confidence evidence and should be manually reviewed.")
            if not score.source_checks and score.evidence_urls:
                warnings.append(f"{score.vendor} used fallback official-source targets instead of live source checks.")

        if request.data_sensitivity == "medium-high" and any(score.privacy < 75 for score in scores):
            warnings.append("At least one vendor has privacy risk below the preferred threshold for client/business data.")

        if all(score.confidence == "High" for score in scores):
            confidence: Confidence = "High"
        elif any(score.confidence == "Medium" for score in scores):
            confidence = "Medium"
        else:
            confidence = "Low"

        step = "Critic Agent reviewed confidence, evidence gaps, and sensitive-data risk before final output."
        return confidence, CollaborationResult(step=step, warnings=tuple(warnings))


class VendorVerdictMultiAgentOrchestrator:
    """Coordinates specialist worker agents behind the public ASI:One uAgent.

    This gives the project real, visible multi-agent collaboration without
    risking the public Agentverse/ASI:One chat path.  Each worker is isolated,
    testable, and has a single responsibility.
    """

    def __init__(self, collector: EvidenceCollector | None = None) -> None:
        self.collector = collector or EvidenceCollector()
        self.intent_agent = ProcurementIntentAgent()
        self.evidence_agent = EvidenceAgent()
        self.scoring_agent = RiskScoringAgent()
        self.recommendation_agent = RecommendationAgent()
        self.email_agent = EmailAgent()
        self.critic_agent = CriticAgent()

    def run(self, raw_query: str) -> VendorVerdict:
        steps: list[str] = []
        warnings: list[str] = []

        request, intent_result = self.intent_agent.parse(raw_query, self.collector.known_vendor_names)
        steps.append(intent_result.step)
        warnings.extend(intent_result.warnings)

        if request.missing_fields:
            return VendorVerdict(
                request=request,
                scores=tuple(),
                recommendation=None,
                assumptions=_build_assumptions(request),
                due_diligence_email="",
                confidence="Low",
                collaboration_steps=tuple(steps),
                critic_warnings=tuple(warnings),
            )

        evidence, evidence_result = self.evidence_agent.collect(request, self.collector)
        steps.append(evidence_result.step)
        warnings.extend(evidence_result.warnings)

        scores, scoring_result = self.scoring_agent.score(evidence, request)
        steps.append(scoring_result.step)
        warnings.extend(scoring_result.warnings)

        recommendation, recommendation_result = self.recommendation_agent.choose(scores, request)
        steps.append(recommendation_result.step)
        warnings.extend(recommendation_result.warnings)

        email, email_result = self.email_agent.draft(recommendation, request)
        steps.append(email_result.step)
        warnings.extend(email_result.warnings)

        confidence, critic_result = self.critic_agent.review(request, scores, evidence)
        steps.append(critic_result.step)
        warnings.extend(critic_result.warnings)

        return VendorVerdict(
            request=request,
            scores=scores,
            recommendation=recommendation,
            assumptions=_build_assumptions(request),
            due_diligence_email=email,
            confidence=confidence,
            collaboration_steps=tuple(steps),
            critic_warnings=tuple(dict.fromkeys(warnings)),
        )


def _build_assumptions(request: VendorRequest) -> tuple[str, ...]:
    assumptions = [f"Data sensitivity is treated as {request.data_sensitivity} based on the wording of the request."]
    if request.team_size:
        assumptions.append(f"Team size: {request.team_size}.")
    else:
        assumptions.append("Team size was not specified, so I assume a small SME/team context.")
    if request.region:
        assumptions.append(f"Region: {request.region}.")
    else:
        assumptions.append("Region was not specified, so regulatory analysis is general rather than jurisdiction-specific.")
    return tuple(assumptions)
