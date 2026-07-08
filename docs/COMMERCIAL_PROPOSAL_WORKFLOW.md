# Commercial proposal workflow

VendorVerdict can now turn a completed pilot outcome into a tracked commercial proposal.

## Routes

Protected dashboard routes:

- `/dashboard/proposals` — proposal pipeline
- `/dashboard/proposals.csv` — CSV export
- `/dashboard/proposals/{proposal_id}` — proposal detail and editor
- `/dashboard/proposals/{proposal_id}.md` — Markdown export
- `POST /dashboard/pilots/{pilot_id}/proposal` — create or open a proposal from a pilot

## Workflow

1. Open a pilot workspace or pilot outcome page.
2. Click **Commercial proposal** or **Create commercial proposal**.
3. Review the generated package, price, scope, success criteria, and next step.
4. Copy the email draft or download the Markdown proposal.
5. Track proposal status as `draft`, `sent`, `negotiation`, `accepted`, or `lost`.

## Default packages

- `starter` — default after a founding pilot.
- `team` — default after a team pilot.
- `advisor` — default after an advisor / agency pilot.
- `custom` — fallback for bespoke commercial terms.

The generated text is intentionally conservative. It summarizes pilot delivery and suggested commercial terms, but it does not invent ROI, customer savings, or legal conclusions.
