# Pilot review delivery workflow

VendorVerdict pilot workspaces can now create and track the vendor reviews delivered during a paid pilot.

## What it adds

- Run a VendorVerdict review from `/dashboard/pilots/{pilot_id}`.
- Save the report with pilot metadata.
- Link the saved report back to the pilot workspace.
- Export Markdown and PDF artifacts for each pilot review.
- Track review count against the pilot target.
- Export pilot reviews as CSV from `/dashboard/pilots/{pilot_id}/reviews.csv`.

## Operator flow

1. Open `/dashboard/pilots`.
2. Open a pilot workspace.
3. Use **Run and track vendor reviews**.
4. Enter vendors and the use case.
5. Choose whether to run live official-source checks.
6. Export Markdown/PDF as needed.
7. Open the saved report from the pilot workspace.

When the first pilot review is run, the onboarding checklist item **Run first 3–5 vendor reviews** is marked done. If Markdown or PDF export is selected, **Export PDF/Markdown reports for decision records** is also marked done.

## CSV export

Use:

```text
/dashboard/pilots/{pilot_id}/reviews.csv
```

The export includes created date, label, status, report id, vendors, use case, recommendation, confidence, and notes.
