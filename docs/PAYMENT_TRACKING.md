# Proposal payment tracking

VendorVerdict can now track the payment state for commercial proposals after a pilot.

## What it tracks

Each proposal can store:

- payment status: `not_requested`, `invoice_sent`, `paid`, `overdue`, or `waived`
- payment due date
- invoice or payment reference
- optional payment / checkout link
- paid timestamp

This is designed to support a lightweight paid-pilot workflow before adding a full billing provider integration.

## Dashboard workflow

Open a proposal at `/dashboard/proposals/{proposal_id}` and use the **Payment tracking** section to:

1. add an invoice reference or payment link;
2. mark the invoice/payment link as sent;
3. mark payment as received;
4. update payment status manually;
5. see overdue payment warnings.

The proposal list at `/dashboard/proposals` shows payment counts and payment labels.

## Customer-facing exports

Customer PDF, Markdown, and shared proposal pages include invoice reference, payment due date, and payment link only when those fields are set.

Internal payment status, paid timestamp, and pipeline notes remain in the protected dashboard.

## Settings

The admin settings page supports non-secret payment defaults:

- default payment due days
- default payment link

Do not put API keys or payment-provider secrets in dashboard settings. Keep those in `/etc/vendorverdict/vendorverdict.env` if you later add a live payment provider integration.
