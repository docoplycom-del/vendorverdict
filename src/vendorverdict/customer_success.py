from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote

from vendorverdict.customers import CustomerRecord, CustomerReview


@dataclass(frozen=True)
class CustomerSuccessSnapshot:
    customer_id: str
    health_status: str
    health_label: str
    renewal_days_remaining: int | None
    usage_percent: int
    reviews_used: int
    reviews_remaining: int
    next_best_action: str
    risks: tuple[str, ...]
    opportunities: tuple[str, ...]


@dataclass(frozen=True)
class CustomerSuccessEmail:
    subject: str
    body: str
    mailto_url: str


def build_customer_success_snapshot(customer: CustomerRecord, reviews: list[CustomerReview] | tuple[CustomerReview, ...] = ()) -> CustomerSuccessSnapshot:
    renewal_days = _days_until(customer.renewal_date)
    risks: list[str] = []
    opportunities: list[str] = []
    health = customer.health_status or _infer_health_status(customer, renewal_days)

    if customer.billing_status in {"payment_due", "overdue"}:
        risks.append(f"Billing status is {customer.billing_status.replace('_', ' ')}.")
    if customer.status in {"paused", "churned"}:
        risks.append(f"Account status is {customer.status.replace('_', ' ')}.")
    if renewal_days is not None and renewal_days <= 14:
        risks.append(f"Renewal is due in {max(0, renewal_days)} day(s).")
    if customer.review_allowance > 0 and customer.usage_percent >= 80:
        opportunities.append("High usage: discuss additional review volume or a higher package.")
    if customer.review_count == 0:
        risks.append("No recurring customer reviews have been delivered yet.")
    if reviews:
        recommended = sorted({review.recommended_vendor for review in reviews if review.recommended_vendor})
        if recommended:
            opportunities.append("Recent recommendation themes: " + ", ".join(recommended[:3]) + ".")

    next_action = _next_best_action(customer, health, renewal_days)
    return CustomerSuccessSnapshot(
        customer_id=customer.customer_id,
        health_status=health,
        health_label=health.replace("_", " "),
        renewal_days_remaining=renewal_days,
        usage_percent=customer.usage_percent,
        reviews_used=customer.review_count,
        reviews_remaining=customer.reviews_remaining,
        next_best_action=next_action,
        risks=tuple(risks),
        opportunities=tuple(opportunities),
    )


def build_customer_success_emails(customer: CustomerRecord, snapshot: CustomerSuccessSnapshot) -> dict[str, CustomerSuccessEmail]:
    check_in_subject = f"VendorVerdict check-in for {customer.company}"
    check_in_body = _clean_body(
        f"""
        Hi {customer.contact_name or 'there'},

        I wanted to check in on the VendorVerdict rollout for {customer.company}.

        Current account snapshot:
        - Package: {customer.package_label}
        - Reviews used this cycle: {snapshot.reviews_used}/{customer.review_allowance}
        - Reviews remaining: {snapshot.reviews_remaining}
        - Billing status: {customer.billing_status.replace('_', ' ')}
        - Renewal date: {customer.renewal_date or 'to be confirmed'}

        Suggested next step:
        {snapshot.next_best_action}

        Would it be useful to schedule a short review call and agree the next batch of vendor reviews?

        Best,
        Vladimir
        """
    )

    renewal_subject = f"VendorVerdict renewal next step for {customer.company}"
    renewal_body = _clean_body(
        f"""
        Hi {customer.contact_name or 'there'},

        As the next VendorVerdict renewal point approaches, I suggest we review the account and agree the next period.

        Renewal context:
        - Package: {customer.package_label}
        - Renewal date: {customer.renewal_date or 'to be confirmed'}
        - Current monthly review allowance: {customer.review_allowance}
        - Reviews used this cycle: {snapshot.reviews_used}
        - Health status: {snapshot.health_label}

        Proposed agenda:
        1. Review the SaaS decisions supported so far.
        2. Confirm recurring review volume and stakeholder needs.
        3. Agree any package, billing, or support changes.

        Would a 30-minute renewal review call work?

        Best,
        Vladimir
        """
    )

    return {
        "check_in": CustomerSuccessEmail(
            subject=check_in_subject,
            body=check_in_body,
            mailto_url=_mailto(customer.contact_email, check_in_subject, check_in_body),
        ),
        "renewal": CustomerSuccessEmail(
            subject=renewal_subject,
            body=renewal_body,
            mailto_url=_mailto(customer.contact_email, renewal_subject, renewal_body),
        ),
    }


def render_customer_success_markdown(customer: CustomerRecord, snapshot: CustomerSuccessSnapshot, reviews: list[CustomerReview] | tuple[CustomerReview, ...]) -> str:
    lines = [
        f"# VendorVerdict customer success summary: {customer.company}",
        "",
        f"**Contact:** {customer.contact_name} <{customer.contact_email}>",
        f"**Package:** {customer.package_label}",
        f"**Account status:** {customer.status.replace('_', ' ')}",
        f"**Billing status:** {customer.billing_status.replace('_', ' ')}",
        f"**Health status:** {snapshot.health_label}",
        f"**Renewal date:** {customer.renewal_date or 'To be confirmed'}",
        f"**Reviews used:** {snapshot.reviews_used}/{customer.review_allowance}",
        f"**Reviews remaining:** {snapshot.reviews_remaining}",
        "",
        "## Next best action",
        snapshot.next_best_action,
        "",
        "## Risks",
    ]
    lines.extend([f"- {risk}" for risk in snapshot.risks] or ["- No immediate risk flags recorded."])
    lines.extend(["", "## Opportunities"])
    lines.extend([f"- {item}" for item in snapshot.opportunities] or ["- Continue recurring review delivery and collect usage evidence."])
    lines.extend(["", "## Recent reviews"])
    if reviews:
        for review in reviews[:10]:
            lines.append(
                f"- {review.created_at[:10]} · {review.label} · {review.recommended_vendor or 'No recommendation'} · {review.overall_confidence or 'confidence not stated'}"
            )
    else:
        lines.append("- No recurring reviews delivered yet.")
    lines.append("")
    return "\n".join(lines)


def default_next_check_in_date(days: int = 14) -> str:
    return (datetime.now(UTC).date() + timedelta(days=days)).isoformat()


def _infer_health_status(customer: CustomerRecord, renewal_days: int | None) -> str:
    if customer.status in {"paused", "churned"} or customer.billing_status in {"overdue", "payment_due"}:
        return "at_risk"
    if renewal_days is not None and renewal_days <= 14:
        return "renewal_due"
    if customer.review_allowance > 0 and customer.usage_percent >= 80:
        return "expansion"
    if customer.review_count == 0 or customer.status == "onboarding":
        return "watch"
    return "healthy"


def _next_best_action(customer: CustomerRecord, health: str, renewal_days: int | None) -> str:
    if customer.billing_status in {"payment_due", "overdue"}:
        return "Confirm payment status and agree whether recurring review delivery should continue."
    if health == "renewal_due" or (renewal_days is not None and renewal_days <= 14):
        return "Book a renewal review call and agree the next billing period, review allowance, and support cadence."
    if health == "expansion":
        return "Discuss higher review volume, additional stakeholders, or a larger package."
    if customer.review_count == 0:
        return "Run the first recurring customer review and agree the reporting cadence."
    return "Send a customer check-in and confirm the next review batch."


def _days_until(value: str) -> int | None:
    if not value:
        return None
    try:
        target = date.fromisoformat(value[:10])
    except ValueError:
        return None
    return (target - datetime.now(UTC).date()).days


def _clean_body(value: str) -> str:
    lines = [line.strip() for line in value.strip().splitlines()]
    return "\n".join(lines)


def _mailto(to_email: str, subject: str, body: str) -> str:
    return f"mailto:{quote(to_email or '', safe='@')}?subject={quote(subject)}&body={quote(body)}"
