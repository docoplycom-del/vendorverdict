# Customer activation workflow

VendorVerdict now includes a protected customer account tracker for the step after a proposal is accepted or paid.

## What it adds

- `/dashboard/customers` — customer account pipeline.
- `/dashboard/customers/{customer_id}` — customer workspace.
- `/dashboard/customers.csv` — customer export.
- `Create customer account` from `/dashboard/proposals/{proposal_id}`.

Customer accounts store:

- company and contact;
- linked proposal and pilot;
- package;
- account status;
- billing status;
- review allowance;
- renewal date;
- onboarding notes;
- internal notes.

## Typical workflow

1. Create or send a commercial proposal.
2. Track payment manually or through Stripe webhook reconciliation.
3. When the proposal is accepted or paid, click **Create customer account**.
4. Open the customer workspace.
5. Confirm onboarding notes, recurring review allowance, renewal date, and billing status.

This keeps the commercial handoff separate from the protected lead, pilot, and proposal workflows while preserving the audit trail from lead to paid customer.
