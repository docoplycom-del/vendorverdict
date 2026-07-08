# Customer proposal polish

This release makes the commercial proposal export suitable to share with a prospect after a pilot close-out conversation.

## Customer-facing exports

The PDF and Markdown proposal exports now exclude internal delivery and sales-tracking details:

- no pipeline status such as `draft` or `sent`
- no raw ISO timestamps
- no internal notes
- no protected pilot IDs
- no copy/paste follow-up email draft
- no weak pilot-progress wording such as `1/20 reviews delivered`

The protected proposal dashboard still keeps those details for the founder/admin.

## PDF contents

The customer PDF includes:

- VendorVerdict customer proposal title
- customer/company name
- readable proposal date
- short proposal reference
- package
- proposed price
- billing model
- proposed scope
- customer-facing success criteria
- suggested next step
- customer contact
- disclaimer

## Markdown contents

The Markdown export mirrors the customer PDF and is intended for quick sharing or editing before sending.

## Why this matters

The previous export was technically correct but looked like an internal system export. This version separates:

- customer proposal material, suitable to send externally
- internal proposal workflow, kept on the protected dashboard


## Follow-up wording polish

A later wording polish also makes customer exports safer for real prospects:

- replaces "resolve the remaining pilot actions" with a positive rollout call-to-action
- replaces vendor-specific wording such as "why Notion was recommended most often" with a more general discussion of recommended vendor approach, evidence gaps, and rollout priorities
- applies the customer-facing wording at export time, so existing proposal records can still produce polished PDFs and Markdown exports
