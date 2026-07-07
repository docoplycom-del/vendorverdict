# VendorVerdict Web Dashboard

VendorVerdict now includes a lightweight customer-facing dashboard built on FastAPI and Jinja2 templates.

The dashboard turns the production API into a simple SaaS-style interface for creating, viewing, and exporting vendor-risk reports.

## Run locally

```bash
vendorverdict-api --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080/dashboard
```

## Dashboard pages

```text
GET  /dashboard
GET  /reviews/new
POST /reviews/run
GET  /dashboard/reports/{report_id}
```

## What users can do

- Start a new SaaS vendor-risk review.
- Choose live evidence checks or deterministic fallback mode.
- Save generated reports to the configured SQLite database.
- View report history.
- Open report detail pages.
- Download Markdown and PDF exports.
- Open the underlying JSON/API endpoints.

## Why this matters for production

The original hackathon product worked inside ASI:One and through the CLI. The production API added machine-readable endpoints. The dashboard adds a customer-facing interface that can become the first web product for SMEs, consultants, and agencies.

This is intentionally simple: it uses server-rendered HTML rather than a separate React/Next.js app. That keeps deployment easy and reuses the same FastAPI service.

## Environment variables

The dashboard uses the same API configuration:

```env
VENDORVERDICT_API_DB_PATH=./data/vendorverdict.sqlite3
VENDORVERDICT_API_EXPORT_DIR=./reports
VENDORVERDICT_API_LIVE_EVIDENCE=0
```

For local demos, set live evidence to `0` for reliable deterministic behaviour. For production, set it to `1` so reports can use live official-source checks.

## Future dashboard features

- User accounts and workspaces.
- Saved organizations.
- Report sharing links.
- Stripe/FET billing controls.
- Admin source-management UI.
- Vendor library and history.

## Authentication

The dashboard is protected when `VENDORVERDICT_AUTH_ENABLED=1` or `VENDORVERDICT_AUTH_PASSWORD` is configured.

Unauthenticated browser users are redirected to `/login`. The same credentials also work for API clients through HTTP Basic authentication. See `docs/AUTHENTICATION.md`.
