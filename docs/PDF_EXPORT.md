# PDF Export

VendorVerdict can export saved vendor-risk reports to a client-ready PDF artifact.

PDF export is intended for production users who need to share a report with a founder, manager, client, or procurement reviewer. It complements the existing Markdown export.

## What the PDF includes

The exported PDF contains:

- title page and report metadata,
- executive summary,
- structured vendor scorecard,
- multi-agent workflow summary,
- Critic Agent notes,
- evidence-backed findings with source URLs and snippets,
- source snapshot,
- due-diligence email,
- procurement guidance disclaimer.

## Save and export a report to PDF

```bash
vendorverdict --demo --save-report --export-pdf --db-path ./data/vendorverdict.sqlite3 --export-dir ./reports
```

You can also export both Markdown and PDF:

```bash
vendorverdict --demo --save-report --export-markdown --export-pdf --db-path ./data/vendorverdict.sqlite3 --export-dir ./reports
```

## Export an existing saved report

```bash
vendorverdict --show-report REPORT_ID --export-pdf --db-path ./data/vendorverdict.sqlite3 --export-dir ./reports
```

The output path is:

```text
reports/vendorverdict-report-REPORT_ID.pdf
```

## Dependency

PDF generation uses ReportLab and is included in the production dependencies.

## Safety note

The PDF is procurement guidance based on public evidence and configured fallback sources. It is not legal advice, financial advice, or a formal security audit.
