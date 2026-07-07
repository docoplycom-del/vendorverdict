# VendorVerdict authentication

VendorVerdict includes simple authentication for the production dashboard, API endpoints, and report downloads.

## What is protected

When authentication is enabled, these routes require a valid session cookie or HTTP Basic credentials:

- `/dashboard`
- `/reviews/new`
- `/reviews/run`
- `/dashboard/reports/{report_id}`
- `/reports`
- `/reports/run`
- `/reports/{report_id}`
- `/reports/{report_id}/markdown`
- `/reports/{report_id}/pdf`
- `/docs`
- `/openapi.json`

These routes remain public:

- `/health`
- `/login`
- `/logout`
- `/static/*`

## Environment variables

```env
VENDORVERDICT_AUTH_ENABLED=1
VENDORVERDICT_AUTH_USERNAME=admin
VENDORVERDICT_AUTH_PASSWORD=replace-with-a-strong-password
VENDORVERDICT_AUTH_SECRET=replace-with-a-long-random-session-secret
VENDORVERDICT_AUTH_SECURE_COOKIE=1
VENDORVERDICT_AUTH_SESSION_SECONDS=43200
```

`VENDORVERDICT_AUTH_ENABLED` may be omitted if `VENDORVERDICT_AUTH_PASSWORD` is set. The service enables auth automatically when a password exists.

Use `VENDORVERDICT_AUTH_SECURE_COOKIE=1` when running behind HTTPS. Keep it `0` for plain local development on `http://127.0.0.1`.

## Browser login

Start the service:

```bash
vendorverdict-api --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080/dashboard
```

Unauthenticated users are redirected to:

```text
/login
```

## API access with HTTP Basic

API clients can pass the same credentials with HTTP Basic authentication:

```bash
curl -u admin:replace-with-a-strong-password http://127.0.0.1:8080/reports
```

Example report creation:

```bash
curl -u admin:replace-with-a-strong-password \
  -X POST http://127.0.0.1:8080/reports/run \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Notion and Airtable for storing client project data for a 10-person consulting startup in the UK.","live_evidence":false,"export_pdf":true}'
```

## Production checklist

Before exposing VendorVerdict publicly:

1. Set a strong `VENDORVERDICT_AUTH_PASSWORD`.
2. Set a long random `VENDORVERDICT_AUTH_SECRET`.
3. Use HTTPS and set `VENDORVERDICT_AUTH_SECURE_COOKIE=1`.
4. Keep `/health` public for container health checks.
5. Keep SQLite data and report exports on persistent storage.

This is intentionally simple V1 protection. Later production versions should add user accounts, organisations, role-based access control, password rotation, audit logging, and billing integration.
