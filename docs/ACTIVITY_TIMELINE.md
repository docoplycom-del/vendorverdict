# VendorVerdict activity timeline

The activity timeline gives the operator a single protected view of recent events across the production workflow.

## Protected routes

- `/dashboard/activity` — HTML timeline for the operator dashboard.
- `/dashboard/activity.md` — Markdown export for operating notes.
- `/dashboard/activity.csv` — CSV export for audit/review work.

## Event sources

The timeline is read-only and is built from existing SQLite tables. It does not create a separate event stream, so it is safe to add to existing deployments.

Included event types:

- saved vendor reports
- captured pilot leads
- lead notifications
- pilot workspaces
- completed pilot checklist tasks
- pilot vendor reviews
- commercial proposals
- proposal sent/follow-up events
- payment received and Stripe payment events
- customer share links and customer views
- customer accounts
- customer reviews
- customer check-ins

## Why it matters

Use the page before customer calls or founder operating reviews to quickly answer:

- What changed recently?
- Which proposals or payments moved?
- Which share links were viewed?
- Which customer reviews were delivered?
- What should be followed up next?

The page is protected by the same dashboard authentication as the rest of the internal VendorVerdict app.
