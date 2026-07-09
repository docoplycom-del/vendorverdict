# Business metrics dashboard

VendorVerdict includes an authenticated business metrics page for tracking the whole operating funnel:

```text
lead → pilot → reviews → outcome → proposal → payment → customer account → renewal
```

## URLs

```text
/dashboard/metrics
/dashboard/metrics.md
```

The page is protected by the existing dashboard authentication.

## What it shows

The snapshot includes:

- leads, pilot workspaces, proposals, customers, reports, and share links
- lead-to-pilot, pilot-to-proposal, proposal-to-customer, and paid-to-customer conversion rates
- accepted proposals and paid proposals
- proposal follow-ups due
- payment actions due
- at-risk, renewal-due, and check-in-due customer accounts
- recurring customer review usage against monthly review allowance
- most frequent vendor recommendations
- next-best-action guidance

## Markdown export

Use `/dashboard/metrics.md` to download a lightweight Markdown summary for weekly founder review, advisor updates, or sales pipeline notes.

## Notes

The dashboard deliberately avoids pretending to be an accounting system. It tracks operating signals from VendorVerdict workflow records. Use Stripe, invoices, or accounting software as the source of truth for recognized revenue.
