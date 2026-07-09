# Customer success and renewal workflow

This production step adds a lightweight customer-success layer after customer activation and recurring review operations.

## What it adds

- Customer health status: healthy, watch, expansion, renewal due, or at risk.
- Automatic customer-success snapshot based on billing, renewal date, review usage, and delivered reviews.
- Next-best-action guidance for each customer account.
- Check-in and renewal email templates with `mailto:` links.
- `Mark check-in sent` action that records the last check-in timestamp and the next due date.
- Customer success Markdown export for account review and renewal calls.
- Customer list metrics for at-risk accounts, renewals due, and check-ins due.

## Operator flow

1. Open `/dashboard/customers`.
2. Open a customer account.
3. Review the health status and next-best-action panel.
4. Send a check-in or renewal email using the provided template.
5. Mark the check-in sent and set the next check-in date.
6. Download the customer success summary before a renewal or account review call.

## Customer lifecycle covered

VendorVerdict now supports:

`lead → pilot → reviews → outcome → proposal → payment → customer account → recurring reviews → renewal follow-up`

## Notes

Health status can be stored manually, or left as `auto` so the customer success snapshot derives it from billing, renewal, and usage signals.
