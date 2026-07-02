from __future__ import annotations

from .models import VendorRequest, VendorScore


def build_due_diligence_email(winner: VendorScore | None, request: VendorRequest) -> str:
    vendor = winner.vendor if winner else "[Vendor]"
    region_line = (
        f"We operate in {request.region} and need to understand data protection obligations."
        if request.region
        else "We need to understand data protection obligations before rollout."
    )
    team_line = f"We are a {request.team_size} team" if request.team_size else "We are a small team"
    business_line = f" at a {request.business_type}" if request.business_type else ""

    return f"""Subject: Security and data-protection questions before vendor selection

Hi {vendor} team,

{team_line}{business_line}, and we are evaluating your platform for {request.use_case}. {region_line}

Could you please confirm:

1. Where customer data is hosted and processed?
2. Whether you support SSO, MFA, role-based access controls, and audit logs on the plan suitable for us?
3. Whether customer data is used for AI model training or product analytics beyond service delivery?
4. Your current SOC 2, ISO 27001, GDPR, DPA, and subprocessor posture, if applicable?
5. Your data retention, deletion, and account-closure policy?
6. What export options are available if we later migrate away?
7. Whether there are pricing thresholds or plan limits we should know about as our team grows?

Thanks,
[Your Name]""".strip()
