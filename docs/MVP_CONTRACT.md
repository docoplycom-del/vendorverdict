# VendorVerdict MVP Contract

VendorVerdict helps SMEs compare 2–5 SaaS vendors for a specific business use case. It researches public vendor evidence, scores each vendor across security, privacy, pricing predictability, lock-in/portability, SME fit, and operational maturity, then returns a ranked recommendation and a ready-to-send due-diligence email inside ASI:One.

## Demo query

```text
Compare Notion, Airtable, and Coda for storing client project data for a 10-person consulting startup in the UK. Rank them by privacy, security, pricing risk, lock-in, and SME suitability. Give me the safest recommendation and draft an email I can send to the chosen vendor.
```

## MVP success criteria

- The agent runs locally.
- The agent implements Agent Chat Protocol.
- The agent can be registered on Agentverse and used through ASI:One.
- The response includes a ranked comparison, transparent scores, key risks, a recommendation, a due-diligence email, confidence notes, and fallback behavior.
- The core workflow requires no custom frontend.
