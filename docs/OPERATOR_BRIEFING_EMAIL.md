# Operator briefing email

VendorVerdict now includes an optional operator briefing email workflow.

## What it does

The protected `/dashboard/briefing` page still gives the live daily operating view, and now also provides:

- a copy/paste `mailto:` briefing email
- an optional SMTP-powered **Send briefing now** action
- a delivery log of recent briefing send attempts
- recipient resolution from `VENDORVERDICT_BRIEFING_EMAIL_TO` or the admin **Operator email** setting

The email contains the same priority queue, funnel snapshot, call talking points, and recent activity as the Markdown export.

## Configuration

Automatic sending uses the existing SMTP settings used for proposal and payment emails.

```env
VENDORVERDICT_EMAIL_SEND_ENABLED=1
VENDORVERDICT_SMTP_HOST=smtp.example.com
VENDORVERDICT_SMTP_PORT=587
VENDORVERDICT_SMTP_USERNAME=your-smtp-username
VENDORVERDICT_SMTP_PASSWORD=your-smtp-password
VENDORVERDICT_SMTP_FROM=vendorverdict@docoply.com
VENDORVERDICT_SMTP_FROM_NAME="VendorVerdict"
VENDORVERDICT_SMTP_STARTTLS=1
VENDORVERDICT_SMTP_TIMEOUT_SECONDS=15
```

Then enable operator briefing sends:

```env
VENDORVERDICT_BRIEFING_EMAIL_ENABLED=1
VENDORVERDICT_BRIEFING_EMAIL_TO=vladimir@example.com
```

If `VENDORVERDICT_BRIEFING_EMAIL_TO` is not set, VendorVerdict uses the non-secret **Operator email** value from `/dashboard/settings`.

## Safety

Secrets remain in `/etc/vendorverdict/vendorverdict.env`. The admin settings page only stores non-secret defaults. Delivery attempts are recorded in SQLite with status, recipient, subject, detail, action count, and urgent action count.

## Manual fallback

If SMTP is not configured, use **Open briefing email** on `/dashboard/briefing`. It opens a prefilled email in your local email client.
