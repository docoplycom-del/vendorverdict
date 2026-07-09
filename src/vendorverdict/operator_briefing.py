from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Sequence

from vendorverdict.activity import ActivityItem
from vendorverdict.business_metrics import BusinessMetricsSnapshot


@dataclass(frozen=True)
class BriefingAction:
    priority: str
    category: str
    title: str
    detail: str
    href: str = ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class BriefingSnapshot:
    generated_at: str
    headline: str
    health_label: str
    metrics: BusinessMetricsSnapshot
    priority_actions: tuple[BriefingAction, ...]
    recent_activity: tuple[ActivityItem, ...]
    talking_points: tuple[str, ...]

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @property
    def generated_date(self) -> str:
        return self.generated_at[:10]

    @property
    def urgent_count(self) -> int:
        return sum(1 for action in self.priority_actions if action.priority == "high")



def build_operator_briefing(
    *,
    metrics: BusinessMetricsSnapshot,
    activity_items: Sequence[ActivityItem] = (),
    leads: Sequence[Any] = (),
    pilots: Sequence[Any] = (),
    proposals: Sequence[Any] = (),
    customers: Sequence[Any] = (),
) -> BriefingSnapshot:
    """Build a daily founder/operator briefing from current VendorVerdict state."""

    actions = _priority_actions(
        metrics=metrics,
        leads=leads,
        pilots=pilots,
        proposals=proposals,
        customers=customers,
    )
    health = _health_label(metrics, actions)
    headline = _headline(metrics, actions, health)
    talking_points = _talking_points(metrics)
    return BriefingSnapshot(
        generated_at=datetime.now(UTC).isoformat(),
        headline=headline,
        health_label=health,
        metrics=metrics,
        priority_actions=tuple(actions),
        recent_activity=tuple(activity_items[:12]),
        talking_points=tuple(talking_points),
    )



def render_operator_briefing_markdown(snapshot: BriefingSnapshot) -> str:
    lines = [
        "# VendorVerdict operator briefing",
        "",
        f"Generated: {snapshot.generated_at}",
        f"Health: {snapshot.health_label}",
        f"Headline: {snapshot.headline}",
        "",
        "## Funnel snapshot",
        f"- Leads: {snapshot.metrics.lead_count}",
        f"- Pilots: {snapshot.metrics.pilot_count}",
        f"- Proposals: {snapshot.metrics.proposal_count}",
        f"- Paid proposals: {snapshot.metrics.paid_proposal_count}",
        f"- Customers: {snapshot.metrics.customer_count}",
        f"- Customer reviews: {snapshot.metrics.customer_review_count}/{snapshot.metrics.review_allowance_total}",
        "",
        "## Priority actions",
    ]
    if snapshot.priority_actions:
        for action in snapshot.priority_actions:
            lines.append(f"- [{action.priority}] {action.title} — {action.detail}")
    else:
        lines.append("- No urgent action queue yet. Keep prospecting and running vendor reviews.")

    lines.extend(["", "## Call talking points"])
    for point in snapshot.talking_points:
        lines.append(f"- {point}")

    lines.extend(["", "## Recent activity"])
    if snapshot.recent_activity:
        for item in snapshot.recent_activity:
            lines.append(f"- {item.occurred_at} · {item.title} — {item.detail}")
    else:
        lines.append("- No recent activity yet.")
    lines.append("")
    return "\n".join(lines)



def _priority_actions(
    *,
    metrics: BusinessMetricsSnapshot,
    leads: Sequence[Any],
    pilots: Sequence[Any],
    proposals: Sequence[Any],
    customers: Sequence[Any],
) -> list[BriefingAction]:
    actions: list[BriefingAction] = []

    for proposal in proposals:
        company = _field(proposal, "company") or _field(proposal, "contact_name") or "Prospect"
        proposal_id = _field(proposal, "proposal_id") or _field(proposal, "id")
        href = f"/dashboard/proposals/{proposal_id}" if proposal_id else "/dashboard/proposals"
        if bool(_field(proposal, "is_payment_overdue")) or _field(proposal, "payment_status") == "overdue":
            actions.append(BriefingAction(
                priority="high",
                category="Payment",
                title=f"Resolve overdue payment for {company}",
                detail=_field(proposal, "payment_label") or "Payment is overdue or blocked.",
                href=href,
            ))
        elif _field(proposal, "payment_status") == "invoice_sent":
            actions.append(BriefingAction(
                priority="high",
                category="Payment",
                title=f"Check payment status for {company}",
                detail=_field(proposal, "payment_label") or "Invoice/payment link has been sent.",
                href=href,
            ))
        if bool(_field(proposal, "is_follow_up_due")):
            actions.append(BriefingAction(
                priority="high",
                category="Proposal",
                title=f"Follow up proposal with {company}",
                detail=_field(proposal, "delivery_label") or "Commercial follow-up is due.",
                href=href,
            ))

    for customer in customers:
        company = _field(customer, "company") or _field(customer, "contact_name") or "Customer"
        customer_id = _field(customer, "customer_id") or _field(customer, "id")
        href = f"/dashboard/customers/{customer_id}" if customer_id else "/dashboard/customers"
        health = _field(customer, "health_status")
        if health == "at_risk":
            actions.append(BriefingAction(
                priority="high",
                category="Customer",
                title=f"Recover at-risk customer {company}",
                detail=f"Health: at risk · next check-in { _field(customer, 'next_check_in_due') or 'not scheduled' }",
                href=href,
            ))
        elif health == "renewal_due":
            actions.append(BriefingAction(
                priority="medium",
                category="Customer",
                title=f"Prepare renewal conversation for {company}",
                detail=f"Renewal date: { _field(customer, 'renewal_date') or 'not set' }",
                href=href,
            ))
        if _date_due(_field(customer, "next_check_in_due")):
            actions.append(BriefingAction(
                priority="medium",
                category="Customer",
                title=f"Send customer check-in to {company}",
                detail=f"Check-in due { _field(customer, 'next_check_in_due') } · usage { _field(customer, 'review_count', 0) }/{ _field(customer, 'review_allowance', 0) }",
                href=href,
            ))

    for lead in leads:
        if _field(lead, "status") not in {"new", "qualified"}:
            continue
        company = _field(lead, "company") or _field(lead, "name") or _field(lead, "email") or "Lead"
        lead_id = _field(lead, "lead_id") or _field(lead, "id")
        href = f"/dashboard/leads/{lead_id}" if lead_id else "/dashboard/leads"
        if _field(lead, "status") == "new":
            actions.append(BriefingAction(
                priority="medium",
                category="Lead",
                title=f"Reply to new pilot request from {company}",
                detail=f"Use case: { _field(lead, 'use_case') or 'not specified' } · vendors: { _field(lead, 'vendors') or 'not specified' }",
                href=href,
            ))
        else:
            actions.append(BriefingAction(
                priority="medium",
                category="Lead",
                title=f"Convert qualified lead {company} into a pilot",
                detail="Create a pilot workspace and set a review target.",
                href=href,
            ))

    for pilot in pilots:
        if _field(pilot, "status") not in {"planned", "active"}:
            continue
        pilot_id = _field(pilot, "pilot_id") or _field(pilot, "id")
        company = _field(pilot, "company") or _field(pilot, "contact_name") or "Pilot"
        review_target = _field(pilot, "review_target") or "20"
        actions.append(BriefingAction(
            priority="low",
            category="Pilot",
            title=f"Progress pilot workspace for {company}",
            detail=f"Target: {review_target} reviews · objective: { _field(pilot, 'objective') or 'not set' }",
            href=f"/dashboard/pilots/{pilot_id}" if pilot_id else "/dashboard/pilots",
        ))

    if not actions:
        actions.extend([
            BriefingAction(
                priority="medium",
                category="Growth",
                title="Create the next serious pilot conversation",
                detail="Use the public demo, share links, and pilot package page in outbound messages.",
                href="/pricing",
            ),
            BriefingAction(
                priority="low",
                category="Delivery",
                title="Run another high-quality vendor review",
                detail="Build proof points from real SaaS decisions and evidence gaps.",
                href="/reviews/new",
            ),
        ])

    priority_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda action: (priority_order.get(action.priority, 9), action.category, action.title))
    return actions[:12]



def _headline(metrics: BusinessMetricsSnapshot, actions: Sequence[BriefingAction], health: str) -> str:
    if any(action.priority == "high" for action in actions):
        return "Focus today on commercial follow-up, payment, or at-risk customer actions."
    if metrics.customer_count:
        return "Customer delivery is active; keep usage and renewals moving."
    if metrics.proposal_count:
        return "Proposal pipeline exists; push the next commercial step."
    if metrics.pilot_count:
        return "Pilot workspaces exist; move them toward outcome reports."
    return "No urgent blockers. Use the demo and pilot package to create the next prospect conversation."



def _health_label(metrics: BusinessMetricsSnapshot, actions: Sequence[BriefingAction]) -> str:
    high = sum(1 for action in actions if action.priority == "high")
    if high or metrics.payment_due_count or metrics.at_risk_customer_count:
        return "Needs attention"
    if metrics.follow_up_due_count or metrics.check_ins_due_count or metrics.renewal_due_customer_count:
        return "Action due"
    if metrics.customer_count or metrics.paid_proposal_count:
        return "Customer motion active"
    if metrics.lead_count or metrics.pilot_count or metrics.proposal_count:
        return "Pipeline active"
    return "Build pipeline"



def _talking_points(metrics: BusinessMetricsSnapshot) -> list[str]:
    points = [
        f"VendorVerdict has generated {metrics.report_count} saved vendor review report(s) and {metrics.share_count} customer share link(s).",
        f"Current funnel: {metrics.lead_count} lead(s), {metrics.pilot_count} pilot workspace(s), {metrics.proposal_count} proposal(s), {metrics.customer_count} customer account(s).",
    ]
    if metrics.top_recommendations:
        vendor, count = metrics.top_recommendations[0]
        points.append(f"Most frequent recommendation theme so far: {vendor} ({count} report(s)).")
    if metrics.customer_count:
        points.append(f"Recurring customer review usage: {metrics.customer_review_count}/{metrics.review_allowance_total} monthly allowance used.")
    if metrics.next_actions:
        points.append(f"Main next action: {metrics.next_actions[0]}")
    return points



def _field(record: Any, key: str, default: Any = "") -> Any:
    if hasattr(record, "get"):
        try:
            return record.get(key, default)
        except TypeError:
            pass
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)



def _date_due(value: Any) -> bool:
    date_value = str(value or "").strip()[:10]
    if not date_value:
        return False
    return date_value <= datetime.now(UTC).date().isoformat()
