from __future__ import annotations

import argparse
import sys

from .payment.premium_report import render_premium_dossier
from .verdict import render_response

DEMO_QUERY = (
    "Compare Notion, Airtable, and Coda for storing client project data for a "
    "10-person consulting startup in the UK. Rank them by privacy, security, "
    "pricing risk, lock-in, and SME suitability. Give me the safest recommendation "
    "and draft an email I can send to the chosen vendor."
)


def run_health_check(use_live_evidence: bool = False) -> int:
    """Run a deterministic local health check for hosted deployments.

    The health check deliberately uses the normal rendering path so it verifies
    the parser, multi-agent orchestration layer, evidence/fallback path, scoring,
    recommendation, email generation, and final renderer. By default it avoids
    live HTTP calls so a vendor website outage does not make the container look
    unhealthy.
    """
    output = render_response(DEMO_QUERY, use_live_evidence=use_live_evidence)
    required_markers = [
        "VendorVerdict: SaaS Procurement Review",
        "Multi-agent collaboration completed",
        "Procurement Intent Agent",
        "Evidence Agent",
        "Risk Scoring Agent",
        "Recommendation Agent",
        "Email Agent",
        "Critic Agent",
        "Due-diligence email",
    ]
    missing = [marker for marker in required_markers if marker not in output]
    if missing:
        print("VendorVerdict health check: FAIL")
        print("Missing markers:")
        for marker in missing:
            print(f"- {marker}")
        return 1

    print("VendorVerdict health check: OK")
    print("Validated parser, specialist-agent workflow, scoring, recommendation, and email rendering.")
    return 0



def main() -> None:
    parser = argparse.ArgumentParser(description="Run VendorVerdict locally without Agentverse.")
    parser.add_argument("query", nargs="*", help="Natural-language vendor comparison request.")
    parser.add_argument("--demo", action="store_true", help="Run the default Notion/Airtable/Coda demo.")
    parser.add_argument("--premium-demo", action="store_true", help="Run the paid Premium Vendor Dossier demo.")
    parser.add_argument("--health", action="store_true", help="Run a deterministic local health check for hosted deployments.")
    parser.add_argument("--live-health", action="store_true", help="Allow the health check to use live official-source checks.")
    parser.add_argument(
        "--no-live-evidence",
        action="store_true",
        help="Disable live official-source checks and use fallback evidence only.",
    )
    args = parser.parse_args()

    if args.health:
        raise SystemExit(run_health_check(use_live_evidence=args.live_health))

    query = DEMO_QUERY if args.demo or args.premium_demo or not args.query else " ".join(args.query)
    if args.premium_demo:
        print(render_premium_dossier(query, use_live_evidence=not args.no_live_evidence))
    else:
        print(render_response(query, use_live_evidence=not args.no_live_evidence))


if __name__ == "__main__":
    main()
