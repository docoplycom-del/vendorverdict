# VendorVerdict HTTP API

VendorVerdict includes a FastAPI backend for production report management. The API makes the report engine usable by a future web dashboard, customer portal, internal admin console, or other agents.

The ASI:One uAgent remains the conversational interface. The FastAPI backend manages persistent reports and downloadable artifacts.

## Run locally

```bash
python -m pip install -e .
vendorverdict-api
```

Default URL:

```text
http://127.0.0.1:8080
```

Interactive docs:

```text
http://127.0.0.1:8080/docs
```

## Environment variables

```env
VENDORVERDICT_API_HOST=0.0.0.0
VENDORVERDICT_API_PORT=8080
VENDORVERDICT_API_DB_PATH=data/vendorverdict.sqlite3
VENDORVERDICT_API_EXPORT_DIR=reports
VENDORVERDICT_API_LIVE_EVIDENCE=1
VENDORVERDICT_API_CORS_ORIGINS=
```

The API uses the same report store as the CLI. If `VENDORVERDICT_API_DB_PATH` is unset, it falls back to the normal VendorVerdict report store path.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Check API, report store, and deterministic workflow availability |
| POST | `/reports/run` | Run a vendor review and save the report |
| GET | `/reports` | List saved reports |
| GET | `/reports/{report_id}` | Return a stored report as JSON |
| GET | `/reports/{report_id}/markdown` | Return Markdown export |
| GET | `/reports/{report_id}/pdf` | Return PDF export |

## `GET /health`

Returns API status, report-store path, export path, and deterministic workflow checks.

Example response:

```json
{
  "status": "ok",
  "service": "vendorverdict-api",
  "checks": [
    "parser",
    "specialist-agent workflow",
    "scoring",
    "recommendation",
    "email rendering",
    "report storage"
  ]
}
```

## `POST /reports/run`

Runs and saves a VendorVerdict report.

Request:

```json
{
  "query": "Compare Notion and Airtable for storing client project data for a 10-person consulting startup in the UK.",
  "live_evidence": false,
  "export_markdown": true,
  "export_pdf": true,
  "metadata": {
    "source": "api-demo"
  }
}
```

`live_evidence` is accepted for backwards compatibility. `use_live_evidence` is also supported.

Completed response includes:

```json
{
  "status": "completed",
  "report_id": "...",
  "links": {
    "self": "/reports/...",
    "markdown": "/reports/.../markdown",
    "pdf": "/reports/.../pdf"
  },
  "recommendation": "Notion",
  "confidence": "Medium"
}
```

If the request is missing required fields, the endpoint returns HTTP 200 with `status: "needs_clarification"`, `missing_fields`, and the clarification text. This lets a frontend keep the conversation going without treating clarification as a hard API failure.

## `GET /reports`

Lists saved reports.

Optional query parameter:

```text
limit=20
```

## `GET /reports/{report_id}`

Returns a saved report with:

- rendered response,
- structured scores,
- collaboration steps,
- critic warnings,
- evidence sources,
- extracted findings,
- metadata,
- artifact links.

## `GET /reports/{report_id}/markdown`

Returns a Markdown report as `text/markdown`.

## `GET /reports/{report_id}/pdf`

Returns a PDF report as `application/pdf`.

## Docker Compose

The included `docker-compose.yml` includes two services:

```text
vendorverdict      # ASI:One / Agentverse uAgent
vendorverdict-api  # FastAPI report-management API
```

Run both:

```bash
docker compose up --build
```

The API will be available at:

```text
http://localhost:8080
```

## Production purpose

The API is the bridge from the agent MVP to a production SaaS product:

- ASI:One agent: conversational procurement assistant.
- FastAPI backend: report-management API.
- Future web app: dashboard, accounts, billing, and report history.
- Future API tier: paid report generation for other agents and business systems.

## Safety note

VendorVerdict provides procurement guidance based on public evidence and configured fallback data. It is not legal advice, financial advice, or a formal security audit.
