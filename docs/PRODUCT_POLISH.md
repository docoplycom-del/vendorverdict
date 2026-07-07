# Product polish

This layer improves the production dashboard so VendorVerdict is easier to use as a small SaaS product, not only as an API.

## Added

- Public landing page at `/`.
- Favicon files and routes for `/favicon.ico` and `/favicon.png`.
- Guided report builder on `/reviews/new`.
- Cleaner dashboard report cards with PDF and Markdown actions.
- Report detail summary metrics for recommendation, findings, and source checks.
- Official-source snapshot table on report pages.

## Public and protected routes

Public:

- `/`
- `/health`
- `/login`
- `/favicon.ico`
- `/favicon.png`
- `/static/*`

Protected when `VENDORVERDICT_AUTH_ENABLED=1`:

- `/dashboard`
- `/reviews/new`
- `/reviews/run`
- `/dashboard/reports/{report_id}`
- `/reports`
- `/reports/{report_id}`
- `/reports/{report_id}/markdown`
- `/reports/{report_id}/pdf`
- `/docs`

## Guided review builder

The dashboard can now build a review query from structured fields:

- vendors
- use case
- team size
- region
- data sensitivity

Example generated query:

```text
Compare Notion, Airtable for storing client project data for a 10-person team in UK with medium-high data sensitivity.
```

If the structured fields are empty, users can still use the advanced full-question textarea.

## Deployment

After pulling this version on the VM, reinstall the app and restart:

```bash
cd /tmp/vendorverdict
git pull origin main
sudo bash scripts/install_gcp_vm.sh
sudo systemctl restart vendorverdict
```

Quick checks:

```bash
curl -i https://vendorverdict.docoply.com/
curl -i https://vendorverdict.docoply.com/favicon.ico
curl -i https://vendorverdict.docoply.com/dashboard
```

Expected:

- `/` returns `200 OK` public landing page.
- `/favicon.ico` returns `200 OK`.
- `/dashboard` returns `303` to login when unauthenticated.
