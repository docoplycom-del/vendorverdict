# Lead management

VendorVerdict includes a lightweight protected lead workflow for turning public demo and pilot requests into follow-up actions.

## Protected inbox

Open:

```text
https://vendorverdict.docoply.com/dashboard/leads
```

The inbox shows:

- lead name, email, company, source, vendors, use case, and message
- notification delivery status
- lead workflow status
- internal follow-up notes
- summary counts by status

## Lead statuses

Supported statuses:

```text
new
contacted
qualified
won
lost
```

Use these to track outreach after someone submits the public demo or pilot request form.

## CSV export

Open:

```text
https://vendorverdict.docoply.com/dashboard/leads.csv
```

The CSV export includes created date, contact details, request details, source, status, internal notes, and notification status.

## Deployment

Deploy normally with:

```bash
cd /tmp/vendorverdict
sudo scripts/deploy_gcp_vm.sh
```

The existing SQLite database is migrated automatically. Existing leads remain intact and receive an empty `notes` field by default.
