# Source Discovery

VendorVerdict Production V1 now includes deterministic source discovery for SaaS vendors that are not yet in the curated fallback registry, or for vendors where one of the configured official-source URLs is missing.

## Why this matters

Earlier versions relied on curated URLs such as `security_url`, `pricing_url`, `privacy_url`, and `docs_url`. That is reliable for known vendors, but production users will ask about vendors that are not in the fallback database yet.

Source discovery lets VendorVerdict bootstrap evidence collection for new vendors by probing likely official URLs before the normal live evidence and extraction pipeline runs.

## What it discovers

For a vendor name such as `ExampleCRM`, VendorVerdict infers likely official domains and common source paths:

- `/security`
- `/trust`
- `/pricing`
- `/privacy`
- `/privacy-policy`
- `/docs`
- `/help`
- `/support`

If a candidate URL is reachable, it is added to the vendor evidence and then checked by the normal Evidence Agent.

## Workflow

```text
User asks about new vendor
  ↓
Procurement Intent Agent extracts vendor name
  ↓
Evidence Agent cannot find curated fallback data
  ↓
Source Discovery Agent infers likely official URLs
  ↓
Evidence Agent checks discovered URLs
  ↓
Evidence Extractor finds concrete signals and snippets
  ↓
Risk Scoring Agent scores the vendor with lower initial confidence
```

## Reliability rules

Source discovery is additive and conservative:

- It does not replace curated fallback URLs for known vendors.
- It only fills missing official-source labels.
- It uses short request timeouts.
- It never blocks the fallback workflow.
- It does not treat a discovered page as proof of compliance.
- Discovered pages are re-checked before extraction and scoring.

## Configuration

Source discovery is enabled by default when live evidence is enabled.

Disable it with:

```env
VENDORVERDICT_SOURCE_DISCOVERY=0
```

Disable live evidence entirely with:

```env
VENDORVERDICT_LIVE_EVIDENCE=0
```

## Tests

Source discovery is covered by tests for:

- domain slug normalization,
- configured-domain preference,
- missing privacy/docs discovery,
- unknown vendor discovery integration,
- parser extraction of unknown vendors,
- evidence extraction after discovered source checks.

## Limitations

This is not a search engine. It does not crawl arbitrary web results or guarantee it has found the vendor's correct official site. It is a deterministic bootstrapper for likely official source pages. Future versions can add search APIs, domain verification, and vendor registry enrichment.
