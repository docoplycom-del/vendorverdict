# VendorVerdict Multi-Agent Collaboration

VendorVerdict exposes one public ASI:One-compatible uAgent, then delegates the workflow to specialist worker agents inside the application. This gives judges a clear multi-agent story without making the demo fragile.

## Agents

| Agent | Responsibility |
|---|---|
| Procurement Intent Agent | Parses the user request and extracts vendors, use case, team size, region, and data sensitivity. |
| Evidence Agent | Collects fallback vendor evidence and checks configured official vendor pages when live evidence is enabled. |
| Risk Scoring Agent | Applies the weighted procurement-risk rubric and returns vendor scorecards. |
| Recommendation Agent | Ranks comparison candidates or classifies a single-vendor audit. |
| Email Agent | Generates the due-diligence email artifact. |
| Critic Agent | Reviews confidence, evidence gaps, and sensitive-data risk before the final response. |

## Why this is demo-safe

The public Agentverse agent remains stable and easy to use through ASI:One. The specialist agents run deterministically behind the orchestrator, so the demo keeps working even if live website checks fail.

The Evidence Agent is especially defensive: live official-source checks are additive, and the fallback vendor database still produces a complete result when a vendor blocks HTTP requests or a network call times out.

## Judge-visible output

Every successful response includes a section like:

```text
Multi-agent collaboration completed:
1. Procurement Intent Agent extracted 3 vendors, the use case, team size, region, and data sensitivity.
2. Evidence Agent checked official vendor sources and found 11/12 reachable configured sources.
3. Risk Scoring Agent scored and ranked vendors with the weighted procurement-risk rubric.
4. Recommendation Agent selected Notion as the strongest practical choice.
5. Email Agent drafted the due-diligence email for Notion.
6. Critic Agent reviewed confidence, evidence gaps, and sensitive-data risk before final output.
```

## Future extension

The same responsibilities can be published later as separate uAgents or remote Agentverse agents. The current implementation keeps the split explicit in code while preserving the existing ASI:One chat path.
