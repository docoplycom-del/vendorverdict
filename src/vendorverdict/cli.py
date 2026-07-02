from __future__ import annotations

import argparse

from .payment.premium_report import render_premium_dossier
from .verdict import render_response

DEMO_QUERY = (
    "Compare Notion, Airtable, and Coda for storing client project data for a "
    "10-person consulting startup in the UK. Rank them by privacy, security, "
    "pricing risk, lock-in, and SME suitability. Give me the safest recommendation "
    "and draft an email I can send to the chosen vendor."
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run VendorVerdict locally without Agentverse.")
    parser.add_argument("query", nargs="*", help="Natural-language vendor comparison request.")
    parser.add_argument("--demo", action="store_true", help="Run the default Notion/Airtable/Coda demo.")
    parser.add_argument("--premium-demo", action="store_true", help="Run the paid Premium Vendor Dossier demo.")
    parser.add_argument(
        "--no-live-evidence",
        action="store_true",
        help="Disable live official-source checks and use fallback evidence only.",
    )
    args = parser.parse_args()

    query = DEMO_QUERY if args.demo or args.premium_demo or not args.query else " ".join(args.query)
    if args.premium_demo:
        print(render_premium_dossier(query, use_live_evidence=not args.no_live_evidence))
    else:
        print(render_response(query, use_live_evidence=not args.no_live_evidence))


if __name__ == "__main__":
    main()
