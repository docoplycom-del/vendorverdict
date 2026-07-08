# Payment request workflow

VendorVerdict can now help send and track payment requests after a proposal is accepted or ready for payment.

## What it adds

- Payment request email template on proposal detail pages.
- Payment reminder email template on proposal detail pages.
- `mailto:` fallback for payment requests and reminders.
- Optional SMTP sending using the existing proposal email SMTP settings.
- Payment request send only marks the invoice/payment link as sent after SMTP succeeds.
- Customer proposal share link is included in the payment email when one exists.

## Dashboard flow

1. Open `/dashboard/proposals`.
2. Open a proposal.
3. Add or confirm:
   - invoice/payment reference,
   - payment due date,
   - payment or checkout link.
4. Use **Open payment request email** for manual sending, or **Send payment request now** when SMTP is configured.
5. Use **Open payment reminder** or **Send payment reminder now** if payment is not received.
6. Mark payment received when paid.

## SMTP configuration

This uses the same environment variables as proposal email sending:

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

Secrets should stay in `/etc/vendorverdict/vendorverdict.env` on the VM, not in Git.

## Customer-facing content

Payment emails include:

- package,
- commercial starting point,
- billing text,
- invoice/payment reference when present,
- payment due date when present,
- payment/checkout link when present,
- proposal share link when present.

They do not include internal notes, pilot IDs, dashboard links, or private tracking state.
