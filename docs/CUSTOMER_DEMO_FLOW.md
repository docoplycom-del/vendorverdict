# Customer demo flow

VendorVerdict now includes a short customer-facing demo flow for pilot calls and early sales conversations.

## Public sample report

Open:

```text
https://vendorverdict.docoply.com/demo
```

The page is public and does not require authentication. It shows a deterministic sample report for the default Notion, Airtable, and Coda scenario. The sample uses offline fallback evidence so it is fast, stable, and safe to show during calls.

The page demonstrates:

- the buyer's input,
- the winning recommendation,
- the scorecard,
- assumptions,
- due-diligence email questions,
- the full report text.

## Protected sample report generation

Authenticated users can create a real saved sample report from the dashboard.

In the dashboard, click **Run sample review**.

This posts to:

```text
POST /reviews/sample
```

The endpoint creates a persistent report using the deterministic sample query, exports Markdown and PDF, then redirects to the saved report detail page.

## Why this exists

Before this step, a visitor had to log in and understand the report builder before seeing the product outcome. The demo flow makes the value obvious in about 30 seconds while preserving the protected dashboard and report-management flow.

## Deploy

Use the safe deployment script:

```bash
cd /tmp/vendorverdict
sudo scripts/deploy_gcp_vm.sh
```

Then test:

```bash
curl -i https://vendorverdict.docoply.com/demo
curl -i https://vendorverdict.docoply.com/dashboard
```

Expected:

```text
/demo      -> 200 OK
/dashboard -> 303 See Other when not logged in
```


## Lead capture

The public demo now includes a compact pilot-request form. Users can also open the full form at `/pilot`. Saved requests are visible in the protected lead inbox at `/dashboard/leads`.
