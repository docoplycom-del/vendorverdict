# Customer share links

VendorVerdict can create tokenized public links for customer-safe report and proposal views.

## Why this matters

Before this step, reports and proposals were mainly internal dashboard artifacts with PDF/Markdown downloads. Customer share links make it easier to send a prospect a browser-viewable page without giving dashboard access.

## Protected admin actions

Authenticated users can create links from:

```text
/dashboard/reports/{report_id}
/dashboard/proposals/{proposal_id}
```

The admin page shows the generated share URL, public PDF link, public Markdown link, view count, and last-viewed timestamp.

## Public customer URLs

Reports:

```text
/share/report/{token}
/share/report/{token}.pdf
/share/report/{token}.md
```

Proposals:

```text
/share/proposal/{token}
/share/proposal/{token}.pdf
/share/proposal/{token}.md
```

These URLs are public but tokenized. They do not expose the dashboard, internal notes, proposal status, pilot IDs, or admin workflows.

## Storage

Share links are stored in SQLite in the `share_links` table. Each record stores:

```text
token
resource_type
resource_id
created_at
updated_at
label
is_active
view_count
last_viewed_at
```

Existing databases migrate automatically when the app starts or when the first share link is created.

## Customer-facing boundary

The public report view includes report summary, scorecard, evidence findings, source snapshot, full report text, and public PDF/Markdown downloads.

The public proposal view includes package, price, billing, scope, customer-facing success criteria, suggested next step, contact details, disclaimer, and public PDF/Markdown downloads.

Internal notes, follow-up drafts, delivery status, proposal pipeline status, and pilot workspace details remain protected inside the dashboard.
