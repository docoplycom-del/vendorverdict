# Production Reporting MVP

This production step makes VendorVerdict stateful and repeatable.

The hackathon version produced a strong ASI:One response, but it did not retain a report history. Production users need to store, revisit, export, and compare vendor-risk reports over time.

## What was added

- SQLite-backed report persistence for local/Azure operation.
- A report ID for each saved VendorVerdict review.
- Stored request context, scores, source records, collaboration steps, critic notes, and final report text.
- Markdown export for sharing or archiving reports.
- CLI commands for saving, listing, showing, and exporting reports.

SQLite is used for this first production increment because it has no extra infrastructure dependency. The schema is intentionally simple and can be migrated to PostgreSQL when the web dashboard and multi-user accounts are added.

## Commands

Save a deterministic fallback report:

```bash
vendorverdict --demo --no-live-evidence --save-report
```

Save with live evidence checks:

```bash
vendorverdict --demo --save-report
```

Use a custom local database path:

```bash
vendorverdict --demo --no-live-evidence --save-report --db-path ./data/vendorverdict.sqlite3
```

List recent reports:

```bash
vendorverdict --list-reports --db-path ./data/vendorverdict.sqlite3
```

Show one report:

```bash
vendorverdict --show-report REPORT_ID --db-path ./data/vendorverdict.sqlite3
```

Export one report to Markdown:

```bash
vendorverdict --show-report REPORT_ID --export-markdown --export-dir ./exports --db-path ./data/vendorverdict.sqlite3
```

## Tables

- `reports`: final report text and structured request/report metadata.
- `report_scores`: normalized vendor score rows.
- `report_sources`: live source checks or fallback official-source targets.

## Next production step

Replace simple source reachability with evidence extraction:

- detect SOC 2, ISO 27001, GDPR, DPA, subprocessor pages, SSO, MFA, RBAC, audit logs, data export, AI-training policies, and status pages;
- store each finding as a cited evidence item;
- update the scoring model to use evidence items instead of fallback-only scoring.

## PDF export

Saved reports can also be exported as PDF:

```bash
vendorverdict --demo --save-report --export-pdf --db-path ./data/vendorverdict.sqlite3 --export-dir ./reports
vendorverdict --show-report REPORT_ID --export-pdf --db-path ./data/vendorverdict.sqlite3 --export-dir ./reports
```

PDF exports are designed for client-ready or manager-ready sharing and include metadata, scorecard, evidence findings, source snapshot, due-diligence email, and disclaimer.

See `docs/PDF_EXPORT.md` for details.
