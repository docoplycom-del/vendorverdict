# VendorVerdict

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![tag:agentverse](https://img.shields.io/badge/Agentverse-ready-6C47FF)
![tag:asi-one](https://img.shields.io/badge/ASI%3AOne-chat-111111)

**VendorVerdict** is an ASI:One-compatible procurement-risk agent that helps small teams compare SaaS vendors, score practical risk, choose the safest option, and generate a ready-to-send due-diligence email.

It is built for the Fetch.ai Innovation Lab / UK AI Agent Hack. The primary workflow runs inside an ASI:One conversation: the user asks a messy vendor-selection question, and the agent performs planning, live official-source checks, transparent risk scoring, recommendation, and email generation.

---



## Trust, privacy, and disclaimer pages

The production web app includes public trust pages for pilot customers:

- `/trust` explains evidence-first reports, human approval, operational controls, and what not to submit.
- `/privacy` explains what the pilot instance collects and how it is used.
- `/disclaimer` clarifies that VendorVerdict is procurement decision support, not legal advice or a formal security audit.

The public navigation is now focused on the customer journey, while operational links such as API docs and health remain available to authenticated users. See `docs/TRUST_PRIVACY_PAGES.md`.

## Pilot package

The production web app includes a public pilot package page at `/pricing` and a request form at `/pilot`.

Default public offer:

- From £1,500
- 4 weeks
- 10–20 SaaS vendor reviews
- Guided setup and review session
- PDF/Markdown reports and due-diligence questions

## Agent details

| Field | Value |
|---|---|
| Agent name | `vendorverdict` |
| Intended Agentverse handle | `@vendorverdict` |
| Agent address | `agent1qgcqf94pr5sevh2c8em36xj0g8ef8ycz50aw4vcqgaawlgv84ceej8wnrun` |
| Category | Innovation Lab / procurement / vendor-risk / SME tools |
| Protocols | Agent Chat Protocol + Payment Protocol seller flow |
| ASI:One status | Tested through Agentverse / ASI:One chat |
| GitHub repo | `https://github.com/docoplycom-del/vendorverdict` |

---

## One-line pitch

**VendorVerdict is a vendor-risk copilot for small teams: it compares SaaS tools, checks official vendor sources, scores security/privacy/pricing/lock-in risk, recommends the safest option, and drafts the follow-up email.**

---

## Why this is useful

Small teams often choose SaaS tools based on popularity, price, or a single recommendation. They rarely have time to check security pages, privacy terms, pricing thresholds, lock-in risk, export options, and follow-up questions before putting client or operational data into a new platform.

VendorVerdict turns that decision into a structured procurement workflow:

1. Understand the use case and vendors.
2. Check official vendor pages when available.
3. Apply a transparent risk rubric.
4. Rank the options.
5. Explain key tradeoffs.
6. Generate a concrete due-diligence email.

---

## Demo prompt

Use this exact prompt in ASI:One:

```text
@agent1qgcqf94pr5sevh2c8em36xj0g8ef8ycz50aw4vcqgaawlgv84ceej8wnrun Compare Notion, Airtable, and Coda for storing client project data for a 10-person consulting startup in the UK. Rank them by privacy, security, pricing risk, lock-in, and SME suitability. Give me the safest recommendation and draft an email I can send to the chosen vendor.
```

Local CLI demo:

```bash
vendorverdict --demo
```

Reliable fallback-only demo:

```bash
vendorverdict --demo --no-live-evidence
```

---

## What the MVP returns

- Parsed procurement intent and assumptions.
- Agent workflow summary for judges.
- Ranked vendor comparison table.
- Scores for security, privacy, pricing predictability, portability/lock-in, SME fit, and operational maturity.
- Vendor-by-vendor strengths and risks.
- Live official-source reachability checks.
- Recommended vendor.
- Ready-to-send due-diligence email.
- Source and confidence notes.
- Graceful fallback behavior when live checks fail.
- Optional Payment Protocol request for the paid Premium Vendor Dossier.

---

## Multi-agent collaboration

VendorVerdict is exposed as one public ASI:One-compatible uAgent, backed by specialist worker agents that collaborate inside the workflow. This keeps the Agentverse user experience simple while making each responsibility explicit and testable.

```text
ASI:One user
   |
   v
VendorVerdict public uAgent / Orchestrator
   |
   +--> Procurement Intent Agent
   |      Extracts vendors, use case, team size, region, and data sensitivity.
   |
   +--> Evidence Agent
   |      Checks configured official vendor security, pricing, privacy, and docs pages.
   |      Falls back to curated evidence if live checks fail.
   |
   +--> Risk Scoring Agent
   |      Applies the transparent weighted procurement-risk rubric.
   |
   +--> Recommendation Agent
   |      Ranks vendors or classifies a single-vendor audit.
   |
   +--> Email Agent
   |      Creates the ready-to-send due-diligence email.
   |
   +--> Critic Agent
   |      Reviews confidence, evidence gaps, and sensitive-data risk before final output.
   |
   v
ASI:One response
```

Judge-visible workflow section included in every successful response:

```text
Multi-agent collaboration completed:
1. Procurement Intent Agent extracted the vendors/use case.
2. Evidence Agent checked official vendor sources.
3. Risk Scoring Agent applied the procurement-risk rubric.
4. Recommendation Agent selected or classified the vendor.
5. Email Agent drafted the due-diligence email.
6. Critic Agent reviewed confidence and evidence gaps.
```

---

## Payment Protocol + monetization

VendorVerdict keeps the basic review free, then offers a paid upgrade:

```text
Free review:
- vendor comparison or single-vendor audit
- live official-source checks
- risk scorecard
- recommendation
- due-diligence email

Paid upgrade:
- Premium Vendor Dossier
```

The Premium Vendor Dossier is a credible paid product for SMEs and consultants. It adds:

- executive procurement memo,
- approval conditions,
- vendor risk register,
- rollout checklist,
- expanded due-diligence questionnaire,
- evidence appendix.

Demo price:

```text
0.05 FET
```

Business model:

```text
£3–£10 per premium vendor dossier
£29/month for small-team review bundles
pay-per-call API for other procurement or compliance agents
```

Payment flow in ASI:One:

```text
1. User requests a normal free review.
2. VendorVerdict returns the free analysis and due-diligence email.
3. User says: “Upgrade to Premium Vendor Dossier.”
4. VendorVerdict sends a Fetch.ai Payment Protocol RequestPayment message.
5. Buyer commits payment.
6. VendorVerdict verifies or demo-verifies the payment.
7. VendorVerdict returns the premium report in the same ASI:One conversation.
```

The public agent includes the Payment Protocol as a seller-side protocol when the runtime supports it. For hackathon demos, `VENDORVERDICT_PAYMENT_DEMO_MODE=1` allows the Payment Protocol flow to be shown without requiring real funds. Set it to `0` for real FET verification through `cosmpy`.

Local premium demo:

```bash
vendorverdict --premium-demo --no-live-evidence
```


---

## Scoring rubric

VendorVerdict uses a simple, explainable 100-point model:

| Dimension | Weight | What it checks |
|---|---:|---|
| Security controls | 25 | Security/trust page, SSO/MFA/RBAC/audit-log posture, public maturity signals |
| Privacy and compliance | 20 | Privacy page, GDPR/DPA/subprocessor/compliance posture |
| Pricing predictability | 15 | Pricing transparency, growth risk, advanced-feature gating |
| Portability / low lock-in | 15 | Export options, APIs, migration risk, workflow lock-in |
| SME fit | 15 | Ease of setup, usability, templates, admin fit for small teams |
| Operational maturity | 10 | Docs, status/support signals, ecosystem maturity |

The scores are procurement guidance, not legal advice or a formal security audit.

---

## Reliability strategy

The hackathon demo should not fail because a website blocks requests or an API is slow. VendorVerdict uses two evidence modes:

1. **Live official-source checks**: the agent checks configured security, pricing, privacy, and docs URLs for each vendor.
2. **Fallback vendor database**: if live evidence is unavailable, the agent still returns a complete ranked decision using curated fallback evidence.

Disable live checks for a guaranteed deterministic demo:

```bash
vendorverdict --demo --no-live-evidence
```

or set:

```env
VENDORVERDICT_LIVE_EVIDENCE=0
```

---

## Setup

### Windows Command Prompt

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
copy .env.example .env
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
cp .env.example .env
```

Edit `.env` and set a long private `AGENT_SEED` before demo or deployment. Do not commit `.env`.

---

## Run locally without Agentverse

```bash
vendorverdict --demo
```

or:

```bash
python scripts/run_demo.py
```

Run a custom query:

```bash
vendorverdict "Compare Notion, Airtable, and Coda for storing client project data for a 10-person consulting startup in the UK."
```

---

## Run the ASI:One-compatible uAgent

```bash
python -m vendorverdict.agent
```

The terminal prints the agent address and an Agentverse Inspector URL. Open the Inspector URL, connect a Mailbox, then test the agent in ASI:One using the demo prompt above.

Expected startup signals:

```text
Starting agent with address: agent1...
Starting mailbox client for https://agentverse.ai
Manifest published successfully: AgentChatProtocol
Manifest published successfully: AgentPaymentProtocol
Agent registration status updated to active
```

A warning about insufficient funds for on-chain Almanac contract registration does not block the local/mailbox ASI:One demo.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `AGENT_NAME` | `vendorverdict` | uAgent name |
| `AGENT_PORT` | `8001` | Local agent port |
| `AGENT_SEED` | development placeholder | Stable private seed for the agent identity |
| `VENDORVERDICT_LIVE_EVIDENCE` | `1` | Set to `0` to disable live official-source checks |
| `VENDORVERDICT_PAYMENT_ENABLED` | `1` | Enables the premium report Payment Protocol flow |
| `VENDORVERDICT_PREMIUM_PRICE_FET` | `0.05` | Demo price for the Premium Vendor Dossier |
| `FET_USE_TESTNET` | `true` | Uses Fetch.ai testnet settings for payment verification |
| `VENDORVERDICT_PAYMENT_DEMO_MODE` | `1` | Accepts committed payments for demo flow; set `0` for chain verification |

---

## Repo structure

```text
src/vendorverdict/
  agent.py              # ASI:One Agent Chat Protocol wrapper
  cli.py                # Local CLI runner
  parser.py             # Deterministic MVP request parser
  scoring.py            # Transparent weighted risk scoring
  verdict.py            # Response assembly
  emailer.py            # Due-diligence email artifact
  agents/               # Specialist multi-agent collaboration layer
    multiagent.py       # Intent, evidence, scoring, recommendation, email, critic agents
  payment/              # Payment Protocol + premium dossier monetization
    payment_proto.py    # Seller-side RequestPayment / CommitPayment flow
    premium_report.py   # Paid Premium Vendor Dossier renderer
  tools/evidence.py     # Live official-source checks + fallback evidence collector
  tools/evidence_extractor.py  # Deterministic source-page signal extraction
  reporting.py          # Report build/export helpers
  storage.py            # SQLite report persistence
  data/fallback_vendors.json

tests/
  test_agents.py
  test_parser.py
  test_scoring.py
  test_evidence.py
  test_verdict.py
  test_payment.py
  test_evidence_extractor.py
  test_storage.py
  test_storage_findings.py

docs/
  MVP_CONTRACT.md
  MULTI_AGENT_COLLABORATION.md
  PAYMENT_PROTOCOL.md
  PRODUCTION_REPORTING.md
  PRODUCTION_V1.md
  EVIDENCE_EXTRACTION.md
```

---

## Test

```bash
python -m unittest discover -s tests -v
```

Expected:

```text
Ran 25 tests
OK
```

---

## Current limitations

- The MVP compares or audits named vendors; it does not yet discover vendors from a broad category.
- It checks configured official URLs rather than doing open-ended search across the web.
- It provides procurement guidance, not legal advice or a formal security audit.
- The specialist worker agents currently run behind one public Agentverse agent for demo reliability.
- Interactive ASI:One cards are a stretch feature.
- Payment verification is demo-friendly by default; production mode requires funded wallets and chain verification.

---

## Roadmap

1. Add vendor discovery for category prompts like: `Find three CRM tools for a 5-person agency`.
2. Add richer evidence extraction from official pages.
3. Optionally publish the specialist worker agents as separate Agentverse agents.
4. Add ASI:One interactive cards for ranked comparisons.
5. Deploy continuously on a VM/cloud host.

---

## Demo video outline

1. Problem: small teams choose SaaS vendors without procurement support.
2. Show the Agentverse / ASI:One agent profile.
3. Send the demo prompt in ASI:One.
4. Highlight the workflow summary.
5. Highlight live official-source checks.
6. Highlight the ranked scoring table.
7. Highlight the generated due-diligence email.
8. Trigger “Upgrade to Premium Vendor Dossier” to show the Payment Protocol monetization path.
9. Explain fallback reliability and why it still works if websites fail.
10. Close with the real-world impact: faster, safer SaaS decisions for SMEs.

---

## Safety note

VendorVerdict provides procurement guidance based on public and fallback evidence. It is not legal advice, financial advice, or a formal security audit.


## Post-hackathon operation plan

VendorVerdict is designed to keep operating after the hackathon instead of only running on a laptop.

Operational plan:

- Run VendorVerdict as a continuously hosted uAgent on Azure Container Apps, Docker, or a small VM with `systemd`.
- Keep the same private `AGENT_SEED` so the Agentverse identity and address remain stable.
- Use Agentverse Mailbox for ASI:One message routing.
- Use Docker health checks or `vendorverdict --health` to verify the deterministic fallback workflow.
- Store secrets in environment variables or managed cloud secrets, never in Git.
- Run GitHub Actions tests before every deployment.
- Keep fallback evidence enabled so vendor website outages do not break the workflow.
- Keep the free workflow available even if the Premium Vendor Dossier payment path is unavailable.

Deployment assets included in this repo:

```text
Dockerfile
docker-compose.yml
.github/workflows/tests.yml
.github/workflows/docker-build.yml
deploy/systemd/vendorverdict.service.example
deploy/systemd/vendorverdict.env.example
deploy/azure/containerapp.env.example
docs/OPERATIONS.md
docs/AZURE_CONTAINER_APPS.md
```

Health check:

```bash
vendorverdict --health
```

This validates the parser, multi-agent workflow, fallback evidence, scoring, recommendation, and email rendering without depending on live vendor websites.


## Production evidence extraction

VendorVerdict now extracts concrete evidence-backed signals from reachable official vendor pages.

Extracted signals include SOC 2, ISO 27001, GDPR, DPA, subprocessors, SSO, MFA, RBAC, audit logs, encryption, data export, data retention/deletion, AI-training policy, and status/uptime signals.

Each finding stores a signal label, source URL, confidence, checked timestamp, and a short evidence snippet. Saved reports and Markdown exports include an **Extracted evidence findings** section.

These findings apply small conservative nudges to the scoring rubric, but they do not represent legal advice, compliance certification, or a formal security audit. They are public-evidence signals that help make vendor-risk reports more trustworthy and repeatable.

See `docs/EVIDENCE_EXTRACTION.md` for details.

## Production reporting MVP

VendorVerdict now includes a first production persistence layer for saved vendor-risk reports.

The CLI can save, list, show, and export reports:

```bash
vendorverdict --demo --no-live-evidence --save-report
vendorverdict --list-reports
vendorverdict --show-report REPORT_ID
vendorverdict --show-report REPORT_ID --export-markdown --export-dir ./exports
```

Reports are stored in SQLite by default at `~/.vendorverdict/vendorverdict.sqlite3`, or in a custom location with `--db-path` / `VENDORVERDICT_DB_PATH`.

This makes the product more than a one-off chat answer: production users can retain vendor-risk reports, export them, and rerun them later as vendor evidence changes.

## Production V1: report persistence

VendorVerdict now includes a first production persistence layer. Generated reports can be saved to a local SQLite report store and exported to Markdown.

This lets the product move beyond one-off chat responses toward repeatable procurement records with report IDs, vendor scorecards, evidence appendix items, confidence, timestamps, and exportable artifacts.

Examples:

```bash
vendorverdict --demo --save-report --export-markdown
vendorverdict --demo --no-live-evidence --save-report --export-markdown
vendorverdict --list-reports
vendorverdict --show-report <REPORT_ID>
```

Configuration:

```env
VENDORVERDICT_DB_PATH=/data/vendorverdict.sqlite3
```

See `docs/PRODUCTION_V1.md` for details.

## Production source discovery

VendorVerdict now includes a conservative source-discovery layer for vendors that are not yet in the curated fallback registry. When live evidence is enabled, the Evidence Agent can generate likely official domains, probe common trust/security/pricing/privacy/docs paths, and use reachable pages for evidence extraction.

This helps production coverage expand beyond the initial curated SaaS list while keeping fallback behavior safe. Source discovery can be disabled with `VENDORVERDICT_SOURCE_DISCOVERY=0`.

## PDF export for production reports

VendorVerdict can now export saved reports as client-ready PDF files in addition to Markdown.

PDF exports include:

- report metadata and recommendation,
- structured vendor scorecard,
- multi-agent workflow summary,
- Critic Agent notes,
- evidence-backed findings with snippets and source URLs,
- source snapshot,
- due-diligence email,
- procurement guidance disclaimer.

Examples:

```bash
vendorverdict --demo --save-report --export-pdf --db-path ./data/vendorverdict.sqlite3 --export-dir ./reports
vendorverdict --demo --save-report --export-markdown --export-pdf --db-path ./data/vendorverdict.sqlite3 --export-dir ./reports
vendorverdict --show-report REPORT_ID --export-pdf --db-path ./data/vendorverdict.sqlite3 --export-dir ./reports
```

See `docs/PDF_EXPORT.md` for details.

## Production HTTP API

VendorVerdict includes a FastAPI backend for production report management. The ASI:One uAgent remains the conversational interface, while the API enables a future web dashboard, customer portal, internal admin tool, or another agent to create, list, retrieve, and export stored reports.

Run locally:

```bash
vendorverdict-api
```

Default API URL:

```text
http://127.0.0.1:8080
```

Interactive docs:

```text
http://127.0.0.1:8080/docs
```

Core endpoints:

```text
GET  /health
POST /reports/run
GET  /reports
GET  /reports/{report_id}
GET  /reports/{report_id}/markdown
GET  /reports/{report_id}/pdf
```

Example request:

```bash
curl -X POST http://127.0.0.1:8080/reports/run \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare Notion and Airtable for storing client project data for a 10-person consulting startup in the UK.",
    "live_evidence": false,
    "export_markdown": true,
    "export_pdf": true
  }'
```

The API returns a saved report ID plus links for JSON, Markdown, and PDF export. See `docs/API.md` for full endpoint details.

## Production web dashboard

VendorVerdict includes a lightweight FastAPI/Jinja2 dashboard for production report management.

Run the API/web service:

```bash
vendorverdict-api --host 127.0.0.1 --port 8080
```

Then open:

```text
http://127.0.0.1:8080/dashboard
```

The dashboard supports:

- creating new vendor-risk reviews,
- saving reports to SQLite,
- viewing recent reports,
- viewing report detail pages,
- downloading Markdown and PDF exports,
- opening the underlying API endpoints.

See `docs/DASHBOARD.md` for details.

## Dashboard and API authentication

VendorVerdict now supports simple production authentication for the dashboard, API, and report downloads.

Authentication is enabled when either `VENDORVERDICT_AUTH_ENABLED=1` is set or `VENDORVERDICT_AUTH_PASSWORD` is configured.

Example local setup:

```bash
VENDORVERDICT_AUTH_ENABLED=1
VENDORVERDICT_AUTH_USERNAME=admin
VENDORVERDICT_AUTH_PASSWORD=change-this-password
VENDORVERDICT_AUTH_SECRET=change-this-long-random-secret
```

Protected browser routes redirect to `/login`. API clients can use HTTP Basic authentication:

```bash
curl -u admin:change-this-password http://127.0.0.1:8080/reports
```

`/health`, `/login`, `/logout`, and static assets remain public. See `docs/AUTHENTICATION.md` for production setup details.


## Google Cloud VM deployment

VendorVerdict can be deployed on a Google Compute Engine VM using systemd plus Apache reverse proxy.

The recommended pilot deployment stores the SQLite report database and generated reports on the VM at `/var/lib/vendorverdict`, runs the FastAPI dashboard on `127.0.0.1:8080`, and exposes it through an HTTPS subdomain such as `vendorverdict.docoply.com`.

See [`docs/GOOGLE_CLOUD_VM_DEPLOYMENT.md`](docs/GOOGLE_CLOUD_VM_DEPLOYMENT.md).


### Google Cloud VM backups

The Google Compute Engine deployment includes a systemd backup timer for the production SQLite database and report export directory.

```bash
sudo systemctl status vendorverdict-backup.timer --no-pager
sudo systemctl start vendorverdict-backup
sudo ls -la /var/backups/vendorverdict
```

See `docs/BACKUPS.md` for restore instructions.

## Production monitoring

The Google Cloud VM deployment includes lightweight systemd monitoring for service health, HTTPS reachability, database integrity, backup freshness, and disk usage.

Key commands on the VM:

```bash
sudo systemctl start vendorverdict-monitor
sudo journalctl -u vendorverdict-monitor -n 100 --no-pager
sudo /opt/vendorverdict/scripts/status_vendorverdict.sh
```

See `docs/MONITORING.md` for setup and troubleshooting.

### Production alerts

The Google Cloud VM monitoring layer can now send alerts when production checks fail.

Supported channels:

- generic/Slack-style webhook using `{ "text": "..." }`
- Discord webhook using `{ "content": "..." }`
- local `mail` or `sendmail` if configured on the VM

Key settings:

```env
VENDORVERDICT_ALERT_ENABLED=1
VENDORVERDICT_ALERT_WEBHOOK_URL=https://example.com/your-webhook-url
VENDORVERDICT_ALERT_WEBHOOK_FORMAT=generic
VENDORVERDICT_ALERT_COOLDOWN_SECONDS=3600
```

See `docs/ALERTS.md` and `docs/MONITORING.md`.

## Product polish

The production dashboard includes a public landing page, favicon, a guided report builder, clearer report cards, and improved report detail pages with evidence and source snapshots. See `docs/PRODUCT_POLISH.md`.

### Safe production deployment

For production updates on the Google Cloud VM, use the safe deploy script instead of manual `rsync`:

```bash
cd /tmp/vendorverdict
git pull origin main
sudo scripts/deploy_gcp_vm.sh
```

This preserves `/opt/vendorverdict/.venv`, reinstalls operational scripts with executable permissions, restarts the service, checks local/public health, and runs the monitor once. See `docs/SAFE_DEPLOYMENT.md`.


## Demo-to-lead capture

VendorVerdict includes a public pilot request flow:

- `/demo` includes a compact lead form below the sample report.
- `/pilot` shows the full pilot request form.
- `/pilot/thanks` confirms submission.
- `/dashboard/leads` shows saved pilot requests for authenticated users.

Lead requests are stored in SQLite in `lead_requests`, alongside saved reports. See `docs/LEAD_CAPTURE.md`.

## Customer demo flow

VendorVerdict includes a public 30-second demo page for pilot calls:

```text
https://vendorverdict.docoply.com/demo
```

The demo page renders a deterministic sample vendor-risk report without requiring login. Authenticated dashboard users can also click **Run sample review** to create a real saved sample report with PDF and Markdown exports.

Use the safe production deploy script for this and future releases:

```bash
cd /tmp/vendorverdict
sudo scripts/deploy_gcp_vm.sh
```

### Lead notifications

VendorVerdict can notify you when someone submits the public demo or pilot form. Configure `VENDORVERDICT_LEAD_NOTIFY_ENABLED=1` and either `VENDORVERDICT_LEAD_WEBHOOK_URL` or reuse the existing monitor alert webhook. Notification status is stored with each lead and shown in `/dashboard/leads`. See `docs/LEAD_NOTIFICATIONS.md
- `docs/LEAD_MANAGEMENT.md``.


- Contrast-hardened demo and lead capture forms with readable buttons, inputs, placeholders, and focus states.


### Visual contrast hardening

The public demo, pilot form, dashboard buttons, lead inbox, and report actions use a final high-contrast CSS override with cache-busting to keep button text, form input text, placeholders, and callout copy readable in production.

### Lead management

Pilot and demo leads can be tracked from the protected lead inbox:

```text
/dashboard/leads
/dashboard/leads.csv
```

The inbox supports status updates (`new`, `contacted`, `qualified`, `won`, `lost`), internal notes, notification status, and CSV export. See `docs/LEAD_MANAGEMENT.md`.

### Login contrast hardening

The login form uses high-contrast auth inputs and autofill-safe CSS so admin usernames, password bullets, and placeholders remain readable in Chrome and other browsers. See `docs/LOGIN_CONTRAST_FIX.md`.

### Lead follow-up workflow

Captured pilot leads can now be opened from `/dashboard/leads/{lead_id}`. The detail page includes lead context, workflow status, internal notes, and copy/paste follow-up email templates for first reply, qualification questions, and the pilot package.

### Pilot onboarding workflow

Qualified leads can now be converted into protected pilot workspaces. Each workspace tracks package type, status, review target, start/end dates, internal notes, and a delivery checklist from scope call through final review.

Protected URLs:

```text
/dashboard/pilots
/dashboard/pilots/{pilot_id}
/dashboard/pilots.csv
```

### Pilot review delivery

Pilot workspaces can now run VendorVerdict reviews directly from the pilot detail page, link saved reports back to the pilot, export PDF/Markdown artifacts, and track review count against the pilot target. See `docs/PILOT_REVIEW_DELIVERY.md`.

- Pilot outcome summaries: close-out metrics, linked review evidence, open actions, Markdown export, and follow-up email drafts.


## Commercial proposal workflow

After a pilot outcome is ready, create a tracked commercial proposal from `/dashboard/pilots/{pilot_id}/outcome`. The proposal pipeline lives at `/dashboard/proposals` and includes editable pricing, scope, success criteria, next step, Markdown export, PDF export, CSV export, and a copy/paste follow-up email.

### Commercial proposal PDF export

Commercial proposals can now be downloaded as customer-ready PDFs from `/dashboard/proposals/{proposal_id}.pdf`. The PDF includes proposal metadata, package, price, billing model, scope, success criteria, next step, customer contact, follow-up email draft, internal notes, and disclaimer. See `docs/COMMERCIAL_PROPOSAL_PDF_EXPORT.md`.
