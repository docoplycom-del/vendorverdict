# VendorVerdict

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

**VendorVerdict** is an ASI:One-compatible procurement-risk agent that helps small teams compare SaaS vendors, score practical risk, choose the safest option, and generate a due-diligence email.

## Agent details

- Agent name: `vendorverdict`
- Intended Agentverse handle: `@vendorverdict`
- Category: Innovation Lab / procurement / vendor-risk / SME tools
- Protocol: Agent Chat Protocol
- MVP status: deterministic offline-safe skeleton using fallback vendor data

## Demo query

```text
Compare Notion, Airtable, and Coda for storing client project data for a 10-person consulting startup in the UK. Rank them by privacy, security, pricing risk, lock-in, and SME suitability. Give me the safest recommendation and draft an email I can send to the chosen vendor.
```

## What the MVP returns

- Ranked vendor comparison table
- Scores for security, privacy, pricing predictability, lock-in/portability, SME fit, and operational maturity
- Recommendation
- Vendor-by-vendor strengths and risks
- Ready-to-send due-diligence email
- Source and confidence notes
- Graceful fallback behavior when live research is unavailable

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Edit `.env` and set a long private `AGENT_SEED` before demo or deployment.

## Run locally without Agentverse

```bash
vendorverdict --demo
```

or:

```bash
python scripts/run_demo.py
```

## Run the ASI:One-compatible uAgent

```bash
python -m vendorverdict.agent
```

The terminal should print the agent address and an Agentverse inspector URL. Use that URL to connect the mailbox, then register/discover the agent through Agentverse and ASI:One.

## Repo structure

```text
src/vendorverdict/
  agent.py              # ASI:One Agent Chat Protocol wrapper
  cli.py                # Local CLI runner
  parser.py             # Deterministic MVP request parser
  scoring.py            # Transparent weighted risk scoring
  verdict.py            # Response assembly
  emailer.py            # Due-diligence email artifact
  tools/evidence.py     # Fallback evidence collector; live search TODO
  data/fallback_vendors.json
```

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Roadmap

1. Add live evidence collector using search + official vendor page fetching.
2. Add LLM summarization for trust/pricing/privacy pages.
3. Split evidence, scoring, and email drafting into separate uAgents if time allows.
4. Add interactive cards for the ranked comparison.
5. Add payment/monetization as a stretch feature for premium vendor reports.

## Safety note

VendorVerdict provides procurement guidance based on public and fallback evidence. It is not legal advice, financial advice, or a formal security audit.
