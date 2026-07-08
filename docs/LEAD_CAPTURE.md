# Demo-to-lead capture

VendorVerdict now converts the public demo into saved pilot requests.

## Public pages

- `/demo` shows the public 30-second sample report and includes a compact lead form.
- `/pilot` shows the full pilot request form.
- `/pilot/thanks` confirms that a request was saved.

## Protected admin page

- `/dashboard/leads` shows saved pilot requests for authenticated users.

The dashboard also shows a pilot request count next to the report workflow.

## Stored fields

Pilot requests are stored in the same SQLite database as reports, in the `lead_requests` table:

- name
- email
- company
- vendors
- use case
- message
- source
- status
- created timestamp

## Validation

The public form requires:

- name
- valid-looking email
- either a use case or vendor list

## Deployment

Use the safe deployment script:

```bash
cd /tmp/vendorverdict
sudo scripts/deploy_gcp_vm.sh
```

Then test:

```bash
curl -i https://vendorverdict.docoply.com/pilot
curl -i https://vendorverdict.docoply.com/demo
```

A browser test should submit the form and then show the saved request inside `/dashboard/leads`.
