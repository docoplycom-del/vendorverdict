# Lead Notifications

VendorVerdict can notify you when someone submits the public demo or pilot request form.

The form is still saved even if notification delivery fails. Notification status is recorded in SQLite and displayed in the protected lead inbox.

## What it does

When a visitor submits `/leads/request`, VendorVerdict:

1. validates the public form,
2. saves the lead in `lead_requests`,
3. sends a best-effort notification by webhook and/or local email,
4. records notification status on the lead record,
5. redirects the visitor to `/pilot/thanks`.

## Recommended setup

Use the same webhook you already use for production monitor alerts:

```env
VENDORVERDICT_LEAD_NOTIFY_ENABLED=1
VENDORVERDICT_LEAD_NOTIFY_NAME=VendorVerdict lead capture
VENDORVERDICT_LEAD_WEBHOOK_URL=""
VENDORVERDICT_LEAD_WEBHOOK_FORMAT=generic
VENDORVERDICT_LEAD_EMAIL_TO=
VENDORVERDICT_LEAD_EMAIL_FROM=vendorverdict@docoply.com
VENDORVERDICT_LEAD_NOTIFY_TIMEOUT_SECONDS=10
```

If `VENDORVERDICT_LEAD_WEBHOOK_URL` is empty, the app falls back to `VENDORVERDICT_ALERT_WEBHOOK_URL`. This is useful on the VM because the monitoring alert webhook is already configured.

For Discord webhooks:

```env
VENDORVERDICT_LEAD_WEBHOOK_FORMAT=discord
```

For Slack or most generic webhooks:

```env
VENDORVERDICT_LEAD_WEBHOOK_FORMAT=generic
```

## Optional local email

If the VM has `mail`, `mailx`, or `sendmail`, set:

```env
VENDORVERDICT_LEAD_EMAIL_TO=you@example.com
VENDORVERDICT_LEAD_EMAIL_FROM=vendorverdict@docoply.com
```

Webhook notifications are recommended first because they are easier to verify and do not require local mail configuration.

## Test manually

After deploying, submit the form from:

```text
https://vendorverdict.docoply.com/pilot
```

Then check:

```text
https://vendorverdict.docoply.com/dashboard/leads
```

The lead inbox should show `sent`, `skipped`, or `failed` in the notification column.

## Status values

- `sent`: notification was delivered to at least one destination.
- `skipped`: notifications are disabled or no destination is configured.
- `failed`: notification delivery was attempted but all destinations failed.

A failed notification does not lose the lead; the request remains saved in SQLite.
