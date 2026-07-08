# Proposal delivery tracking

VendorVerdict can now track the commercial follow-up after a customer proposal has been generated.

## What it adds

- A proposal delivery panel on `/dashboard/proposals/{proposal_id}`.
- A pre-filled `mailto:` proposal email using the current proposal subject and body.
- A `Mark proposal sent` action.
- A `Mark followed up` action.
- A follow-up due date field.
- Delivery state labels in the proposal list.
- Delivery counts on `/dashboard/proposals`.
- CSV export fields for `sent_at`, `follow_up_due`, and `last_follow_up_at`.

## Workflow

1. Open a proposal from `/dashboard/proposals`.
2. Download the customer PDF.
3. Click **Open proposal email** to prepare the outbound email.
4. Send the email manually from the email client.
5. Return to VendorVerdict and click **Mark proposal sent**.
6. Set the next follow-up date.
7. Use **Mark followed up** after each follow-up.

## Why this matters

The proposal workflow now covers the post-pilot commercial loop:

`pilot outcome → customer proposal → sent proposal → scheduled follow-up → accepted / lost`

This keeps the lightweight SaaS pilot pipeline inside VendorVerdict without adding a full CRM dependency.
