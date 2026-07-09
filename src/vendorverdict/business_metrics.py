from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class BusinessMetricCard:
    label: str
    value: str
    detail: str = ""

    def __getitem__(self, key: str) -> str:
        return getattr(self, key)


@dataclass(frozen=True)
class BusinessMetricsSnapshot:
    report_count: int
    lead_count: int
    pilot_count: int
    proposal_count: int
    customer_count: int
    share_count: int
    active_pilot_count: int
    accepted_proposal_count: int
    paid_proposal_count: int
    current_customer_count: int
    at_risk_customer_count: int
    renewal_due_customer_count: int
    check_ins_due_count: int
    follow_up_due_count: int
    payment_due_count: int
    customer_review_count: int
    review_allowance_total: int
    usage_percent: int
    lead_to_pilot_rate: int
    pilot_to_proposal_rate: int
    proposal_to_customer_rate: int
    paid_to_customer_rate: int
    top_recommendations: tuple[tuple[str, int], ...]
    cards: tuple[BusinessMetricCard, ...]
    next_actions: tuple[str, ...]

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


def build_business_metrics_snapshot(
    *,
    reports: Sequence[Any],
    leads: Sequence[Any],
    pilots: Sequence[Any],
    proposals: Sequence[Any],
    customers: Sequence[Any],
    share_count: int = 0,
    check_ins_due_count: int = 0,
) -> BusinessMetricsSnapshot:
    """Build one executive snapshot across the full VendorVerdict funnel.

    The function accepts store records rather than querying SQLite directly so it can be tested with
    lightweight fixtures and reused from the FastAPI dashboard.
    """

    report_count = len(reports)
    lead_count = len(leads)
    pilot_count = len(pilots)
    proposal_count = len(proposals)
    customer_count = len(customers)

    active_pilots = [pilot for pilot in pilots if _field(pilot, "status") in {"planned", "active"}]
    accepted_proposals = [proposal for proposal in proposals if _field(proposal, "status") == "accepted"]
    paid_proposals = [proposal for proposal in proposals if _field(proposal, "payment_status") == "paid"]
    current_customers = [customer for customer in customers if _field(customer, "billing_status") == "current"]
    at_risk_customers = [customer for customer in customers if _field(customer, "health_status") == "at_risk"]
    renewal_due_customers = [customer for customer in customers if _field(customer, "health_status") == "renewal_due"]
    follow_up_due = [proposal for proposal in proposals if bool(_field(proposal, "is_follow_up_due"))]
    payment_due = [proposal for proposal in proposals if _field(proposal, "payment_status") in {"invoice_sent", "overdue"} or bool(_field(proposal, "is_payment_overdue"))]

    customer_review_count = sum(_int_field(customer, "review_count") for customer in customers)
    review_allowance_total = sum(_int_field(customer, "review_allowance") for customer in customers)
    usage_percent = _rate(customer_review_count, review_allowance_total)

    recommendation_counts = Counter(
        str(_field(report, "recommended_vendor") or _field(report, "recommendation") or "").strip()
        for report in reports
    )
    recommendation_counts.pop("", None)
    top_recommendations = tuple(recommendation_counts.most_common(5))

    lead_to_pilot_rate = _rate(pilot_count, lead_count)
    pilot_to_proposal_rate = _rate(proposal_count, pilot_count)
    proposal_to_customer_rate = _rate(customer_count, proposal_count)
    paid_to_customer_rate = _rate(customer_count, len(paid_proposals))

    cards = (
        BusinessMetricCard("Leads → pilots", f"{lead_to_pilot_rate}%", f"{pilot_count}/{lead_count} leads converted to pilot workspaces"),
        BusinessMetricCard("Pilots → proposals", f"{pilot_to_proposal_rate}%", f"{proposal_count}/{pilot_count} pilots have proposal drafts"),
        BusinessMetricCard("Proposals → customers", f"{proposal_to_customer_rate}%", f"{customer_count}/{proposal_count} proposals activated as customers"),
        BusinessMetricCard("Paid → customers", f"{paid_to_customer_rate}%", f"{customer_count}/{len(paid_proposals)} paid proposals have customer accounts"),
        BusinessMetricCard("Customer usage", f"{usage_percent}%", f"{customer_review_count}/{review_allowance_total} recurring reviews used"),
        BusinessMetricCard("Share links", str(share_count), "customer-safe report/proposal links created"),
    )

    actions = _next_actions(
        leads=leads,
        active_pilot_count=len(active_pilots),
        proposal_count=proposal_count,
        accepted_proposal_count=len(accepted_proposals),
        paid_proposal_count=len(paid_proposals),
        customer_count=customer_count,
        follow_up_due_count=len(follow_up_due),
        payment_due_count=len(payment_due),
        at_risk_count=len(at_risk_customers),
        renewal_due_count=len(renewal_due_customers),
        check_ins_due_count=check_ins_due_count,
        customer_review_count=customer_review_count,
    )

    return BusinessMetricsSnapshot(
        report_count=report_count,
        lead_count=lead_count,
        pilot_count=pilot_count,
        proposal_count=proposal_count,
        customer_count=customer_count,
        share_count=share_count,
        active_pilot_count=len(active_pilots),
        accepted_proposal_count=len(accepted_proposals),
        paid_proposal_count=len(paid_proposals),
        current_customer_count=len(current_customers),
        at_risk_customer_count=len(at_risk_customers),
        renewal_due_customer_count=len(renewal_due_customers),
        check_ins_due_count=check_ins_due_count,
        follow_up_due_count=len(follow_up_due),
        payment_due_count=len(payment_due),
        customer_review_count=customer_review_count,
        review_allowance_total=review_allowance_total,
        usage_percent=usage_percent,
        lead_to_pilot_rate=lead_to_pilot_rate,
        pilot_to_proposal_rate=pilot_to_proposal_rate,
        proposal_to_customer_rate=proposal_to_customer_rate,
        paid_to_customer_rate=paid_to_customer_rate,
        top_recommendations=top_recommendations,
        cards=cards,
        next_actions=tuple(actions),
    )


def render_business_metrics_markdown(snapshot: BusinessMetricsSnapshot) -> str:
    lines = [
        "# VendorVerdict business metrics",
        "",
        f"Generated {datetime.now(UTC).date().isoformat()}",
        "",
        "## Funnel",
        f"- Leads: {snapshot.lead_count}",
        f"- Pilot workspaces: {snapshot.pilot_count}",
        f"- Commercial proposals: {snapshot.proposal_count}",
        f"- Customer accounts: {snapshot.customer_count}",
        f"- Saved vendor reports: {snapshot.report_count}",
        "",
        "## Conversion rates",
    ]
    for card in snapshot.cards:
        lines.append(f"- {card.label}: {card.value} — {card.detail}")
    lines.extend(["", "## Commercial and customer success signals"])
    lines.extend([
        f"- Accepted proposals: {snapshot.accepted_proposal_count}",
        f"- Paid proposals: {snapshot.paid_proposal_count}",
        f"- Proposal follow-ups due: {snapshot.follow_up_due_count}",
        f"- Payment actions due: {snapshot.payment_due_count}",
        f"- Current customers: {snapshot.current_customer_count}",
        f"- At-risk customers: {snapshot.at_risk_customer_count}",
        f"- Renewal-due customers: {snapshot.renewal_due_customer_count}",
        f"- Customer check-ins due: {snapshot.check_ins_due_count}",
    ])
    lines.extend(["", "## Recommendation themes"])
    if snapshot.top_recommendations:
        lines.extend([f"- {vendor}: {count}" for vendor, count in snapshot.top_recommendations])
    else:
        lines.append("- No recommendation themes yet.")
    lines.extend(["", "## Next actions"])
    lines.extend([f"- {action}" for action in snapshot.next_actions] or ["- Keep running the full lead-to-customer workflow."])
    lines.append("")
    return "\n".join(lines)


def _next_actions(
    *,
    leads: Sequence[Any],
    active_pilot_count: int,
    proposal_count: int,
    accepted_proposal_count: int,
    paid_proposal_count: int,
    customer_count: int,
    follow_up_due_count: int,
    payment_due_count: int,
    at_risk_count: int,
    renewal_due_count: int,
    check_ins_due_count: int,
    customer_review_count: int,
) -> list[str]:
    actions: list[str] = []
    new_leads = sum(1 for lead in leads if _field(lead, "status") == "new")
    qualified_leads = sum(1 for lead in leads if _field(lead, "status") == "qualified")
    if new_leads:
        actions.append(f"Reply to {new_leads} new lead(s) and qualify the pilot fit.")
    if qualified_leads:
        actions.append(f"Convert {qualified_leads} qualified lead(s) into pilot workspaces.")
    if active_pilot_count:
        actions.append(f"Progress {active_pilot_count} active/planned pilot workspace(s) toward outcome and proposal.")
    if proposal_count == 0 and active_pilot_count:
        actions.append("Create the first commercial proposal from a completed pilot outcome.")
    if follow_up_due_count:
        actions.append(f"Follow up on {follow_up_due_count} proposal(s) due for commercial next step.")
    if payment_due_count:
        actions.append(f"Resolve {payment_due_count} payment/invoice action(s).")
    if accepted_proposal_count + paid_proposal_count > customer_count:
        actions.append("Create customer accounts for accepted or paid proposals that have not been activated yet.")
    if at_risk_count:
        actions.append(f"Review {at_risk_count} at-risk customer account(s) and send a check-in.")
    if renewal_due_count:
        actions.append(f"Prepare renewal conversations for {renewal_due_count} renewal-due customer(s).")
    if check_ins_due_count:
        actions.append(f"Send {check_ins_due_count} customer check-in(s) due today or overdue.")
    if customer_count and customer_review_count == 0:
        actions.append("Run the first recurring review for each activated customer.")
    if not actions:
        actions.append("Keep prospecting, running vendor reviews, and collecting evidence from customer conversations.")
    return actions


def _field(record: Any, key: str, default: Any = "") -> Any:
    if hasattr(record, "get"):
        try:
            return record.get(key, default)
        except TypeError:
            pass
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _int_field(record: Any, key: str) -> int:
    try:
        return int(_field(record, key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _rate(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return max(0, min(100, round((numerator / denominator) * 100)))
