# Production Evidence Extraction

VendorVerdict now includes a deterministic evidence-extraction layer for the first production version.

The goal is to move from "the source page was reachable" to "this source page contains specific vendor-risk signals that can support scoring and report citations."

## What gets extracted

The extractor scans reachable official-source pages for common procurement/security/privacy signals:

- SOC 2
- ISO 27001
- GDPR
- Data Processing Agreement / DPA
- Subprocessors
- Single sign-on / SSO
- MFA / 2FA
- Role-based access control / RBAC
- Audit logs
- Encryption
- Data export / portability
- Data retention / deletion
- AI training policy
- Status / uptime signals

## Design principles

The extractor is intentionally conservative.

A finding means:

> VendorVerdict found a public signal in a vendor source page.

It does **not** mean:

> The vendor is definitively compliant, secure, certified, or safe.

This lets VendorVerdict provide evidence-backed procurement guidance without overclaiming legal or security conclusions.

## Finding schema

Each extracted finding includes:

- vendor
- signal key
- human-readable label
- source label, such as security/privacy/pricing/docs
- source URL
- confidence level
- short evidence snippet
- checked timestamp

## Production report storage

When a report is saved, VendorVerdict now persists extracted findings in the SQLite report store. Markdown exports include an **Extracted evidence findings** section so reports can be reviewed later.

## Scoring impact

Extracted signals apply small conservative nudges to the existing scoring rubric:

- security signals can nudge the security score,
- privacy signals can nudge the privacy score,
- data export can nudge portability / low lock-in,
- status-page signals can nudge operational maturity.

Source reachability and fallback scoring still remain in place. Live extraction improves reports but does not make the workflow fragile.

## Reliability

If a source page fails, blocks automated requests, redirects unexpectedly, or has no extractable signals, VendorVerdict still returns a usable report using fallback evidence.
