from __future__ import annotations

import argparse
import json
from pathlib import Path

from .payment.premium_report import render_premium_dossier
from .reporting import export_report_markdown
from .storage import ReportStore
from .tools.evidence import EvidenceCollector
from .verdict import build_vendor_verdict, render_response, render_verdict

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


def _print_report_list(store: ReportStore, limit: int) -> None:
    reports = store.list_reports(limit=limit)
    if not reports:
        print("No stored reports yet.")
        return
    for report in reports:
        vendors = ", ".join(json.loads(report["vendors_json"]))
        print(
            f"{report['id']} | {report['created_at']} | {report['report_type']} | "
            f"{vendors} | recommendation={report['recommendation']} | confidence={report['confidence']}"
        )


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
    parser.add_argument("--save-report", action="store_true", help="Persist the generated report to the local report store.")
    parser.add_argument("--db-path", help="SQLite report database path. Defaults to VENDORVERDICT_DB_PATH or ~/.vendorverdict/vendorverdict.sqlite3.")
    parser.add_argument("--export-markdown", action="store_true", help="Export a saved report to Markdown.")
    parser.add_argument("--export-dir", default="reports", help="Directory for Markdown report exports.")
    parser.add_argument("--list-reports", action="store_true", help="List recently saved reports.")
    parser.add_argument("--limit", type=int, default=10, help="Number of reports to list.")
    parser.add_argument("--show-report", help="Print a stored report's rendered response by report ID.")
    args = parser.parse_args()

    store = ReportStore(args.db_path) if args.db_path or args.save_report or args.list_reports or args.show_report or args.export_markdown else None

    if args.health:
        raise SystemExit(run_health_check(use_live_evidence=args.live_health))

    if args.list_reports:
        _print_report_list(store or ReportStore(), args.limit)
        return

    if args.show_report:
        report = (store or ReportStore()).get_report(args.show_report)
        if report is None:
            raise SystemExit(f"Report not found: {args.show_report}")
        print(report["rendered_response"])
        return

    query = DEMO_QUERY if args.demo or args.premium_demo or not args.query else " ".join(args.query)
    if args.premium_demo:
        print(render_premium_dossier(query, use_live_evidence=not args.no_live_evidence))
        return

    if args.save_report:
        collector = EvidenceCollector(use_live_checks=not args.no_live_evidence)
        verdict = build_vendor_verdict(query, collector=collector)
        rendered = render_verdict(verdict)
        print(rendered)
        if verdict.request.missing_fields:
            raise SystemExit("Report was not saved because the request is missing required fields.")
        report_store = store or ReportStore()
        report_id = report_store.save_report(
            verdict,
            rendered,
            raw_query=query,
            metadata={"live_evidence": not args.no_live_evidence, "client": "vendorverdict-cli"},
        )
        print("")
        print(f"Saved report: {report_id}")
        print(f"Report database: {report_store.db_path}")
        if args.export_markdown:
            export_path = export_report_markdown(report_id, output_dir=Path(args.export_dir), store=report_store)
            print(f"Exported Markdown: {export_path}")
        return

    print(render_response(query, use_live_evidence=not args.no_live_evidence))


if __name__ == "__main__":
    main()
