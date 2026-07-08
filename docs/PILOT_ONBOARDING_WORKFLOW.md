# Pilot onboarding workflow

VendorVerdict now includes a protected pilot workspace for turning qualified leads into a tracked paid pilot.

## Flow

1. A prospect submits the public demo or pilot form.
2. The lead appears in `/dashboard/leads`.
3. Open the lead detail page.
4. Click **Create pilot workspace**.
5. Track the pilot from `/dashboard/pilots`.

## Pilot workspace

Each workspace stores:

- lead link
- company
- contact name and email
- package type: founding, team, or advisor
- pilot status: planned, active, paused, completed, cancelled
- review target
- start and end dates
- objective
- internal notes
- onboarding checklist progress

## Default checklist

The default checklist covers:

- Book pilot scope call
- Confirm package, duration, and success criteria
- Define risk priorities and scoring emphasis
- Collect first vendor list and use cases
- Run first 3–5 vendor reviews
- Review due-diligence questions with customer
- Export PDF/Markdown reports for decision records
- Hold end-of-pilot review and next-step decision

## URLs

Protected pages:

```text
/dashboard/pilots
/dashboard/pilots/{pilot_id}
/dashboard/pilots.csv
```

Lead conversion:

```text
POST /dashboard/leads/{lead_id}/pilot
```

## Deployment

Deploy with the safe script:

```bash
cd /tmp/vendorverdict
sudo scripts/deploy_gcp_vm.sh
```
