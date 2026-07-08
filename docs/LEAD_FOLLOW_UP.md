# Lead follow-up workflow

VendorVerdict now includes a lightweight follow-up workflow for captured pilot leads.

## Routes

Protected admin routes:

- `/dashboard/leads` — lead inbox
- `/dashboard/leads/{lead_id}` — lead detail page
- `/dashboard/leads.csv` — CSV export

## Lead detail page

The detail page shows:

- lead contact details
- company
- vendors under consideration
- use case
- message
- notification status
- workflow status
- internal notes
- copy/paste follow-up email templates

## Follow-up templates

Each lead gets deterministic follow-up templates:

1. First reply
2. Qualification questions
3. Pilot package

The templates are copy/paste only. VendorVerdict does not send them automatically from the admin page.

## Suggested process

1. Open `/dashboard/leads`.
2. Click `View lead`.
3. Review the request.
4. Copy the first-reply email or open it via `mailto:`.
5. Set status to `contacted`.
6. Add notes such as next call date, budget, buyer role, and use case fit.
7. Move to `qualified`, `won`, or `lost` as the conversation progresses.
