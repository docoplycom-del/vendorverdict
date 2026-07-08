from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from vendorverdict.leads import LeadRecord


@dataclass(frozen=True)
class LeadFollowUpTemplate:
    """Copy/paste follow-up email for a captured pilot lead."""

    key: str
    label: str
    subject: str
    body: str

    @property
    def mailto_url(self) -> str:
        return ""


def build_lead_followup_templates(lead: LeadRecord, *, app_base_url: str = "") -> list[dict[str, str]]:
    """Return practical follow-up emails for a pilot lead.

    The templates are intentionally deterministic and copy/paste friendly. They
    do not send email; they help the founder follow up quickly from the protected
    lead inbox without needing a CRM.
    """

    base_url = app_base_url.rstrip("/")
    first_name = _first_name(lead.name)
    company = lead.company or "your team"
    vendors = lead.vendors or "the vendors you are considering"
    use_case = lead.use_case or "your SaaS procurement decision"
    demo_url = f"{base_url}/demo" if base_url else "/demo"
    pricing_url = f"{base_url}/pricing" if base_url else "/pricing"

    templates = [
        LeadFollowUpTemplate(
            key="first_reply",
            label="First reply",
            subject=f"VendorVerdict pilot request - {company}",
            body=(
                f"Hi {first_name},\n\n"
                "Thanks for requesting a VendorVerdict pilot.\n\n"
                f"I saw you are looking at: {vendors}.\n"
                f"Use case: {use_case}.\n\n"
                "A good next step is a 20-minute call. I can show how VendorVerdict would turn this into "
                "a ranked vendor-risk report, PDF export, and due-diligence email for the chosen vendor.\n\n"
                "Would Tuesday or Wednesday work for a quick call?\n\n"
                "Best,\n"
                "Vladimir\n"
                f"VendorVerdict demo: {demo_url}"
            ),
        ),
        LeadFollowUpTemplate(
            key="qualification",
            label="Qualification questions",
            subject=f"A few questions for the VendorVerdict pilot - {company}",
            body=(
                f"Hi {first_name},\n\n"
                "To shape the pilot around your real workflow, could you share a few details?\n\n"
                "1. How many vendor decisions do you expect in the next month?\n"
                "2. Who usually approves SaaS tools: operations, procurement, IT/security, finance, or founders?\n"
                "3. Will the tools hold client data, employee data, financial data, or internal project data?\n"
                "4. Which outputs would be most useful: scorecard, PDF report, due-diligence email, or evidence snapshot?\n"
                "5. Is there a deadline for the current decision?\n\n"
                f"Based on your note, I would start with: {vendors} for {use_case}.\n\n"
                "Best,\n"
                "Vladimir"
            ),
        ),
        LeadFollowUpTemplate(
            key="pilot_package",
            label="Pilot package",
            subject="VendorVerdict founding pilot package",
            body=(
                f"Hi {first_name},\n\n"
                "Here is the simple founding pilot package for VendorVerdict:\n\n"
                "- From £1,500\n"
                "- 4 weeks\n"
                "- 10-20 vendor reviews\n"
                "- Guided setup and review session\n"
                "- Outputs: ranked scorecards, PDF reports, evidence snapshots, and due-diligence emails\n\n"
                "It is designed for agencies, consultancies, startup ops teams, and SMEs choosing SaaS tools "
                "for client or business data.\n\n"
                f"Pilot package: {pricing_url}\n\n"
                "Best,\n"
                "Vladimir"
            ),
        ),
    ]
    return [
        {
            "key": template.key,
            "label": template.label,
            "subject": template.subject,
            "body": template.body,
            "mailto_url": _mailto_url(lead.email, template.subject, template.body),
        }
        for template in templates
    ]


def _first_name(name: str) -> str:
    cleaned = (name or "there").strip()
    if not cleaned:
        return "there"
    return cleaned.split()[0]


def _mailto_url(email: str, subject: str, body: str) -> str:
    return f"mailto:{quote(email.strip())}?subject={quote(subject)}&body={quote(body)}"
