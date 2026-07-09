# Operator briefing

VendorVerdict includes a protected daily operator briefing at `/dashboard/briefing`.

The briefing combines the business metrics dashboard and the activity timeline into one pre-call view for the founder/operator.

## Routes

- `/dashboard/briefing` - HTML briefing page.
- `/dashboard/briefing.md` - Markdown export for copying into notes, investor updates, or a daily operating log.

## What it shows

The briefing highlights:

- leads, pilots, proposals, paid proposals, and customers;
- urgent proposal follow-ups;
- payment or invoice actions;
- at-risk customers;
- renewal-due customers;
- customer check-ins due;
- active pilot workspaces;
- recent activity across the workflow;
- call-prep talking points.

## Priority levels

The priority queue is deliberately simple:

- `high` - commercial follow-up, payment, overdue payment, or at-risk customer actions;
- `medium` - new or qualified leads, renewal due, customer check-ins due;
- `low` - active pilots and delivery tasks that should keep moving.

## Data source

The briefing is read-only. It uses existing SQLite tables for reports, leads, pilots, proposals, share links, and customer accounts. No extra background worker is required.

## Recommended use

Open `/dashboard/briefing` before each prospect or customer working session and use the first three priority actions as the day’s operating queue.
