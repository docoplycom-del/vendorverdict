# VendorVerdict admin settings

VendorVerdict includes a protected settings page for non-secret runtime defaults:

```text
/dashboard/settings
```

The page is intended to reduce small production edits to `/etc/vendorverdict/vendorverdict.env`.
It stores editable values in the same SQLite database used by reports, leads, pilots, proposals, and share links.
The existing backup workflow therefore includes these settings automatically.

## Editable settings

The settings page currently manages:

- company / product name
- public URL used for follow-up and customer share links
- default review region
- default data sensitivity
- default proposal price
- default proposal billing wording
- default proposal follow-up interval in days
- operator email for internal reference

## What the settings affect

The saved settings are used by:

- `/reviews/new` for default region and data sensitivity
- `/dashboard/pilots/{pilot_id}` for pilot review defaults
- new proposals created from pilot outcomes
- proposal delivery tracking when marking a proposal sent without a manually entered follow-up date
- customer share URLs and lead follow-up URLs when a public URL is configured

## What remains in the environment file

Secrets and infrastructure values should remain in `/etc/vendorverdict/vendorverdict.env`, not in SQLite settings.
Keep these as environment variables:

- admin password
- auth secret
- webhook URLs
- OpenAI/API keys
- database path
- export directory
- service host/port

## Environment fallback

If settings are reset in the dashboard, VendorVerdict falls back to matching environment variables and then to built-in defaults.
Examples:

```env
VENDORVERDICT_PUBLIC_URL="https://vendorverdict.docoply.com"
VENDORVERDICT_DEFAULT_REVIEW_REGION="UK"
VENDORVERDICT_DEFAULT_DATA_SENSITIVITY="medium"
VENDORVERDICT_DEFAULT_PROPOSAL_PRICE="From £1,000/month after pilot"
VENDORVERDICT_DEFAULT_PROPOSAL_BILLING="Monthly or quarterly subscription after the paid pilot, depending on review volume and support needs."
VENDORVERDICT_DEFAULT_FOLLOW_UP_DAYS="7"
VENDORVERDICT_OPERATOR_EMAIL=""
```

Quote values with spaces in the env file.

## Test after deploy

```bash
curl -i https://vendorverdict.docoply.com/dashboard/settings
```

Unauthenticated requests should redirect to `/login`. After login, open the settings page, save a test default, and then check `/reviews/new` or a new proposal to confirm the setting is applied.
