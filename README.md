# VendorVerdict

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![tag:agentverse](https://img.shields.io/badge/Agentverse-ready-6C47FF)
![tag:asi-one](https://img.shields.io/badge/ASI%3AOne-chat-111111)

**VendorVerdict** is an ASI:One-compatible procurement-risk agent that helps small teams compare SaaS vendors, score practical risk, choose the safest option, and generate a ready-to-send due-diligence email.

It is built for the Fetch.ai Innovation Lab / UK AI Agent Hack. The primary workflow runs inside an ASI:One conversation: the user asks a messy vendor-selection question, and the agent performs planning, live official-source checks, transparent risk scoring, recommendation, and email generation.

---

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
  data/fallback_vendors.json

tests/
  test_agents.py
  test_parser.py
  test_scoring.py
  test_evidence.py
  test_verdict.py
  test_payment.py

docs/
  MVP_CONTRACT.md
  MULTI_AGENT_COLLABORATION.md
  PAYMENT_PROTOCOL.md
```

---

## Test

```bash
python -m unittest discover -s tests -v
```

Expected:

```text
Ran 16 tests
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
