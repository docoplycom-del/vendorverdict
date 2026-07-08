from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from vendorverdict.pilots import PilotRecord, PilotReview, PilotTask


@dataclass(frozen=True)
class PilotOutcomeReview:
    label: str
    use_case: str
    vendors: tuple[str, ...]
    recommended_vendor: str
    confidence: str
    report_id: str
    created_at: str

    def __getitem__(self, key: str):
        return getattr(self, key)


@dataclass(frozen=True)
class PilotOutcome:
    pilot_id: str
    company: str
    contact_name: str
    contact_email: str
    status: str
    package: str
    objective: str
    review_count: int
    review_target: int
    review_progress_percent: int
    checklist_percent: int
    completed_tasks: int
    total_tasks: int
    top_recommended_vendor: str
    confidence_summary: dict[str, int]
    reviewed_use_cases: tuple[str, ...]
    reviews: tuple[PilotOutcomeReview, ...]
    success_signals: tuple[str, ...]
    open_actions: tuple[str, ...]
    suggested_next_steps: tuple[str, ...]
    followup_email_subject: str
    followup_email_body: str

    def __getitem__(self, key: str):
        return getattr(self, key)


def build_pilot_outcome(
    pilot: PilotRecord,
    tasks: Iterable[PilotTask],
    reviews: Iterable[PilotReview],
) -> PilotOutcome:
    """Build a close-out summary for a pilot workspace.

    The outcome is deliberately deterministic and evidence-light: it summarizes
    the pilot workspace state and linked VendorVerdict reports without inventing
    customer impact or financial ROI.
    """

    task_list = list(tasks)
    review_list = list(reviews)
    review_count = len(review_list)
    review_target = max(1, int(pilot.review_target or 1))
    review_progress = min(100, round((review_count / review_target) * 100))

    recommendations = Counter(
        review.recommended_vendor for review in review_list if review.recommended_vendor
    )
    top_vendor = recommendations.most_common(1)[0][0] if recommendations else ""

    confidence_counts: Counter[str] = Counter(
        (review.overall_confidence or "unknown").strip() or "unknown"
        for review in review_list
    )

    use_cases = tuple(
        dict.fromkeys(review.use_case for review in review_list if review.use_case)
    )

    outcome_reviews = tuple(
        PilotOutcomeReview(
            label=review.label,
            use_case=review.use_case,
            vendors=review.vendors,
            recommended_vendor=review.recommended_vendor,
            confidence=review.overall_confidence or "unknown",
            report_id=review.report_id,
            created_at=review.created_at,
        )
        for review in review_list
    )

    success_signals = _success_signals(pilot, review_count, review_progress, top_vendor)
    open_actions = _open_actions(pilot, task_list, review_count, review_target)
    next_steps = _suggested_next_steps(pilot, review_count, review_target, top_vendor)
    subject, body = _followup_email(pilot, review_count, review_target, top_vendor, next_steps)

    return PilotOutcome(
        pilot_id=pilot.pilot_id,
        company=pilot.company or pilot.contact_name,
        contact_name=pilot.contact_name,
        contact_email=pilot.contact_email,
        status=pilot.status,
        package=pilot.package,
        objective=pilot.objective,
        review_count=review_count,
        review_target=review_target,
        review_progress_percent=review_progress,
        checklist_percent=pilot.progress_percent,
        completed_tasks=pilot.completed_tasks,
        total_tasks=pilot.total_tasks,
        top_recommended_vendor=top_vendor,
        confidence_summary=dict(confidence_counts),
        reviewed_use_cases=use_cases,
        reviews=outcome_reviews,
        success_signals=success_signals,
        open_actions=open_actions,
        suggested_next_steps=next_steps,
        followup_email_subject=subject,
        followup_email_body=body,
    )


def render_pilot_outcome_markdown(outcome: PilotOutcome) -> str:
    lines = [
        f"# VendorVerdict pilot outcome: {outcome.company}",
        "",
        "## Executive summary",
        f"- Pilot status: {outcome.status}",
        f"- Package: {outcome.package}",
        f"- Reviews completed: {outcome.review_count}/{outcome.review_target} ({outcome.review_progress_percent}%)",
        f"- Delivery checklist: {outcome.completed_tasks}/{outcome.total_tasks} ({outcome.checklist_percent}%)",
    ]
    if outcome.top_recommended_vendor:
        lines.append(f"- Most frequent recommendation: {outcome.top_recommended_vendor}")
    if outcome.objective:
        lines.extend(["", "## Pilot objective", outcome.objective])

    lines.extend(["", "## Success signals"])
    lines.extend(f"- {signal}" for signal in outcome.success_signals)

    lines.extend(["", "## Reviews delivered"])
    if outcome.reviews:
        for review in outcome.reviews:
            vendors = ", ".join(review.vendors) if review.vendors else "Not recorded"
            recommendation = review.recommended_vendor or "No recommendation recorded"
            lines.extend(
                [
                    f"### {review.label}",
                    f"- Use case: {review.use_case or 'Not recorded'}",
                    f"- Vendors: {vendors}",
                    f"- Recommendation: {recommendation}",
                    f"- Confidence: {review.confidence}",
                    f"- Report ID: {review.report_id}",
                ]
            )
    else:
        lines.append("No linked VendorVerdict reviews yet.")

    lines.extend(["", "## Open actions"])
    lines.extend(f"- {action}" for action in outcome.open_actions)

    lines.extend(["", "## Suggested next steps"])
    lines.extend(f"- {step}" for step in outcome.suggested_next_steps)

    lines.extend(
        [
            "",
            "## Follow-up email draft",
            f"Subject: {outcome.followup_email_subject}",
            "",
            outcome.followup_email_body,
            "",
        ]
    )
    return "\n".join(lines)


def _success_signals(
    pilot: PilotRecord,
    review_count: int,
    review_progress: int,
    top_vendor: str,
) -> tuple[str, ...]:
    signals = [
        f"{review_count} decision-ready VendorVerdict report{'s' if review_count != 1 else ''} created.",
        f"{pilot.progress_percent}% of the pilot delivery checklist is complete.",
    ]
    if review_progress >= 100:
        signals.append("The review target has been met or exceeded.")
    elif review_count:
        signals.append(f"{review_progress}% of the review target has been delivered.")
    else:
        signals.append("No pilot reviews have been linked yet, so outcome evidence is not ready.")
    if top_vendor:
        signals.append(f"{top_vendor} appears most often as the recommended vendor across completed reviews.")
    return tuple(signals)


def _open_actions(
    pilot: PilotRecord,
    tasks: list[PilotTask],
    review_count: int,
    review_target: int,
) -> tuple[str, ...]:
    actions: list[str] = []
    remaining_reviews = max(0, review_target - review_count)
    if remaining_reviews:
        actions.append(f"Run {remaining_reviews} more vendor review{'s' if remaining_reviews != 1 else ''} to hit the pilot target.")
    open_tasks = [task.label for task in tasks if not task.completed]
    actions.extend(open_tasks[:5])
    if len(open_tasks) > 5:
        actions.append(f"Complete {len(open_tasks) - 5} more checklist task{'s' if len(open_tasks) - 5 != 1 else ''}.")
    if pilot.status != "completed":
        actions.append("Mark the pilot completed once the close-out review has happened.")
    return tuple(actions) or ("No major open actions recorded.",)


def _suggested_next_steps(
    pilot: PilotRecord,
    review_count: int,
    review_target: int,
    top_vendor: str,
) -> tuple[str, ...]:
    steps: list[str] = []
    if review_count == 0:
        steps.append("Run the first vendor review with the customer’s highest-priority SaaS decision.")
    elif review_count < review_target:
        steps.append("Agree the remaining vendor decisions to review before the pilot close-out.")
    else:
        steps.append("Use the close-out call to agree whether this becomes a recurring procurement-control workflow.")
    if top_vendor:
        steps.append(f"Review why {top_vendor} scored best and decide what vendor evidence the customer still needs.")
    steps.append("Send the pilot outcome summary and ask for a renewal, expansion, or referral decision.")
    return tuple(steps)


def _followup_email(
    pilot: PilotRecord,
    review_count: int,
    review_target: int,
    top_vendor: str,
    next_steps: tuple[str, ...],
) -> tuple[str, str]:
    company = pilot.company or "your team"
    subject = f"VendorVerdict pilot outcome for {company}"
    greeting_name = pilot.contact_name.split()[0] if pilot.contact_name else "there"
    top_vendor_line = (
        f" The most frequent recommendation so far is {top_vendor}." if top_vendor else ""
    )
    steps_text = "\n".join(f"- {step}" for step in next_steps)
    body = (
        f"Hi {greeting_name},\n\n"
        f"Here is the current VendorVerdict pilot outcome for {company}.\n\n"
        f"We have completed {review_count} of the planned {review_target} vendor reviews."
        f"{top_vendor_line}\n\n"
        f"Suggested next steps:\n{steps_text}\n\n"
        "Would it be useful to book a short close-out call to decide whether this should become "
        "a recurring vendor review workflow for your team?\n\n"
        "Best,\n"
        "Vladimir"
    )
    return subject, body
