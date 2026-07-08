# Pilot outcome reporting

VendorVerdict now includes a protected pilot close-out workflow for turning a delivered pilot into a concise outcome summary.

## Pages

- `/dashboard/pilots/{pilot_id}/outcome` — HTML pilot outcome summary.
- `/dashboard/pilots/{pilot_id}/outcome.md` — Markdown export for customer follow-up, CRM notes, or internal records.
- `/dashboard/pilots/{pilot_id}/complete` — marks the pilot as completed and completes the final review checklist task.

## What the outcome page includes

- Reviews delivered vs review target.
- Delivery checklist progress.
- Most frequent recommended vendor across linked reviews.
- Success signals based on completed reports and checklist progress.
- Open actions before close-out.
- Linked review evidence with report, PDF, and Markdown actions.
- Suggested next steps.
- Copy/paste follow-up email draft.

## Design principles

The summary is deterministic. It does not invent financial ROI, time saved, risk reduction, or customer impact that has not been recorded. It only summarizes the pilot workspace, linked VendorVerdict reports, and checklist status.

## Deployment check

After deploy, open a pilot workspace and click **Outcome summary**. The page should render with a Markdown download and a follow-up email template.
