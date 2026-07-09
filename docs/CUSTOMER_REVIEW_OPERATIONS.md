# Customer review operations

VendorVerdict can now continue after a proposal becomes a customer account.

## What this adds

- Run recurring vendor reviews from `/dashboard/customers/{customer_id}`.
- Save each review as a normal VendorVerdict report.
- Link each saved report back to the customer account.
- Track usage against the customer's monthly review allowance.
- Export customer review history as CSV from `/dashboard/customers/{customer_id}/reviews.csv`.
- Keep the original proposal, pilot workspace, and customer workspace linked.

## Workflow

1. Convert a paid or accepted proposal into a customer account.
2. Open the customer workspace.
3. Run recurring reviews for new vendor choices, renewals, replacements, or evidence refreshes.
4. Use PDF, Markdown, and share links from each saved report.
5. Watch reviews used vs monthly allowance before renewal or expansion discussions.

## Data model

The `customer_reviews` table stores the customer-to-report relationship:

- customer ID
- report ID
- label
- status
- notes
- created timestamp

The report itself stays in the existing `reports` table, so exports, share links, evidence snapshots, and dashboard report views continue to work.

## Operations

Customer review links and usage counters are stored in the same SQLite database as the rest of VendorVerdict. Existing backup and restore scripts include this data automatically.
