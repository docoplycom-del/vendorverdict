from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReadinessItem:
    key: str
    label: str
    status: str
    detail: str
    action: str
    url: str
    required: bool = True

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"

    @property
    def is_warning(self) -> bool:
        return self.status == "warning"


@dataclass(frozen=True)
class ReadinessSnapshot:
    items: list[ReadinessItem]
    report_count: int
    lead_count: int
    pilot_count: int
    proposal_count: int
    share_count: int
    public_url: str = ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @property
    def required_items(self) -> list[ReadinessItem]:
        return [item for item in self.items if item.required]

    @property
    def ready_required_count(self) -> int:
        return sum(1 for item in self.required_items if item.is_ready)

    @property
    def required_count(self) -> int:
        return len(self.required_items)

    @property
    def readiness_percent(self) -> int:
        if not self.required_count:
            return 100
        return round((self.ready_required_count / self.required_count) * 100)

    @property
    def is_pilot_ready(self) -> bool:
        return self.ready_required_count == self.required_count

    @property
    def headline(self) -> str:
        if self.is_pilot_ready:
            return "Pilot-ready"
        if self.readiness_percent >= 80:
            return "Almost pilot-ready"
        return "Setup in progress"

    @property
    def next_actions(self) -> list[ReadinessItem]:
        return [item for item in self.required_items if not item.is_ready][:5]


def build_readiness_snapshot(
    *,
    report_count: int,
    lead_count: int,
    pilot_count: int,
    proposal_count: int,
    share_count: int,
    public_url: str = "",
) -> ReadinessSnapshot:
    """Return a customer-pilot readiness checklist for the admin dashboard.

    The checklist deliberately blends feature availability with light operational data. A new
    deployment can still show the full workflow, while real usage progressively flips the
    operational checks from warning to ready as the first lead, pilot, proposal, and share link
    are created.
    """

    clean_public_url = (public_url or "").strip().rstrip("/")
    items = [
        ReadinessItem(
            key="public_pages",
            label="Public product pages",
            status="ready",
            detail="Home, demo, pricing, pilot request, trust, privacy, and disclaimer pages are available.",
            action="Review the public pages before outreach.",
            url="/",
        ),
        ReadinessItem(
            key="lead_capture",
            label="Lead capture workflow",
            status="ready" if lead_count > 0 else "warning",
            detail=(
                f"{lead_count} pilot request(s) captured."
                if lead_count > 0
                else "Lead capture is installed. Submit one test pilot request before real outreach."
            ),
            action="Submit a test request from the pilot page." if lead_count == 0 else "Open the lead inbox.",
            url="/pilot" if lead_count == 0 else "/dashboard/leads",
        ),
        ReadinessItem(
            key="reports",
            label="Vendor review reports",
            status="ready" if report_count > 0 else "warning",
            detail=(
                f"{report_count} saved report(s) available."
                if report_count > 0
                else "Run one sample or custom review to confirm report generation and exports."
            ),
            action="Run a sample review." if report_count == 0 else "Open saved reports.",
            url="/dashboard" if report_count > 0 else "/reviews/new",
        ),
        ReadinessItem(
            key="pilot_workspace",
            label="Pilot delivery workspace",
            status="ready" if pilot_count > 0 else "warning",
            detail=(
                f"{pilot_count} pilot workspace(s) created."
                if pilot_count > 0
                else "Pilot workspaces are installed. Convert a lead into a workspace to test delivery."
            ),
            action="Open pilot workspaces." if pilot_count > 0 else "Create a pilot from a lead detail page.",
            url="/dashboard/pilots" if pilot_count > 0 else "/dashboard/leads",
        ),
        ReadinessItem(
            key="proposals",
            label="Commercial proposal workflow",
            status="ready" if proposal_count > 0 else "warning",
            detail=(
                f"{proposal_count} proposal(s) tracked."
                if proposal_count > 0
                else "Proposal pipeline is installed. Create a proposal from a pilot outcome before a sales call."
            ),
            action="Open proposal pipeline." if proposal_count > 0 else "Create a proposal from a pilot workspace.",
            url="/dashboard/proposals" if proposal_count > 0 else "/dashboard/pilots",
        ),
        ReadinessItem(
            key="share_links",
            label="Customer share links",
            status="ready" if share_count > 0 else "warning",
            detail=(
                f"{share_count} customer share link(s) created."
                if share_count > 0
                else "Share-link feature is installed. Create one link for a report or proposal and test it in incognito."
            ),
            action="Open reports or proposals and create a share link." if share_count == 0 else "Review customer share links from report/proposal pages.",
            url="/dashboard" if share_count == 0 else "/dashboard/proposals",
        ),
        ReadinessItem(
            key="settings",
            label="Admin settings",
            status="ready" if clean_public_url else "warning",
            detail=(
                f"Public URL is set to {clean_public_url}."
                if clean_public_url
                else "Public URL is not set in admin settings; share and follow-up links will fall back to the request host."
            ),
            action="Open settings and confirm public URL, default price, and follow-up days.",
            url="/dashboard/settings",
        ),
        ReadinessItem(
            key="ops",
            label="Production operations",
            status="ready",
            detail="Authentication, safe deploy, backups, monitoring, and health checks are included in the production bundle.",
            action="Run the VM status script after each deploy.",
            url="/health",
            required=False,
        ),
    ]
    return ReadinessSnapshot(
        items=items,
        report_count=report_count,
        lead_count=lead_count,
        pilot_count=pilot_count,
        proposal_count=proposal_count,
        share_count=share_count,
        public_url=clean_public_url,
    )
