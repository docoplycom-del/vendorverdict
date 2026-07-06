# VendorVerdict Production V1: Report Persistence

This production step moves VendorVerdict from a pure chat/demo response toward a repeatable reporting product.

## What this adds

VendorVerdict can now persist generated procurement reviews to a local SQLite report store and export stored reports as Markdown artifacts.

This is intentionally dependency-free so it works in local development, CI, Azure Container Apps, and Docker. The schema is designed so it can later be migrated to PostgreSQL for the production web app.

## Why this matters

A production procurement assistant needs report history and evidence traceability. Users should be able to answer:

- What did we review?
- When was the vendor checked?
- Which vendors were scored?
- What sources were used?
- What recommendation was produced?
- Can we export a report for a manager, client, or internal approval?

## New persistence model

Tables:

- `reports`
- `report_vendors`
- `evidence_items`

Each stored report includes:

- report ID
- created timestamp
- raw query
- use case
- vendor list
- recommendation
- confidence
- rendered response
- vendor scorecards
- evidence appendix items

Evidence items include:

- vendor
- evidence label, such as security, pricing, privacy, docs
- claim
- source URL
- source type: live or fallback
- status code when available
- redirect target when available
- confidence
- checked timestamp

## Local usage

Save a deterministic fallback report:

```bash
vendorverdict --demo --no-live-evidence --save-report --export-markdown
```

Save a live evidence report:

```bash
vendorverdict --demo --save-report --export-markdown
```

List recent reports:

```bash
vendorverdict --list-reports
```

Show a report response:

```bash
vendorverdict --show-report <REPORT_ID>
```

Use a custom database path:

```bash
vendorverdict --demo --save-report --db-path data/vendorverdict.sqlite3
```

Or set:

```env
VENDORVERDICT_DB_PATH=/data/vendorverdict.sqlite3
```

## Next production step

The next production milestone is evidence extraction:

- fetch page content,
- extract compliance/security signals,
- store source snippets,
- cite claims with source excerpts,
- move SQLite schema to PostgreSQL.
