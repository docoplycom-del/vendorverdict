# Proposal email sending

VendorVerdict can send a commercial proposal email directly from the protected proposal page. This is optional. If SMTP is not configured, the dashboard keeps the existing `mailto:` fallback and manual delivery tracking.

## What it does

From `/dashboard/proposals/{proposal_id}` you can:

- open the existing email draft in your local email client;
- send the proposal email directly from VendorVerdict when SMTP is configured;
- attach the customer-ready proposal PDF automatically;
- include the customer share link in the email body when a share link exists;
- mark the proposal as sent only after SMTP send succeeds;
- schedule the next follow-up date.

## Environment variables

SMTP credentials are secrets and should stay in `/etc/vendorverdict/vendorverdict.env` on the VM. Do not store real credentials in the admin settings page or commit them to git.

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

Minimum required fields when sending is enabled:

- `VENDORVERDICT_EMAIL_SEND_ENABLED=1`
- `VENDORVERDICT_SMTP_HOST`
- `VENDORVERDICT_SMTP_FROM`

`VENDORVERDICT_SMTP_USERNAME` and `VENDORVERDICT_SMTP_PASSWORD` are optional for SMTP providers that do not require authentication, but most production providers require them.

## Safe deployment

After changing `/etc/vendorverdict/vendorverdict.env`, validate it before deploying:

```bash
sudo bash -lc 'set -a; source /etc/vendorverdict/vendorverdict.env; set +a; echo "$VENDORVERDICT_SMTP_FROM"'
```

Then deploy:

```bash
cd /tmp/vendorverdict
git pull origin main
sudo scripts/deploy_gcp_vm.sh
```

## Recommended workflow

1. Open a proposal from `/dashboard/proposals`.
2. Create a customer share link if you want the email to include a secure web link.
3. Click **Send proposal email now**.
4. Confirm the page shows the sent notice.
5. Confirm the proposal delivery state says `sent` and has a follow-up due date.

## Fallback mode

If SMTP is not configured, the proposal page shows the missing settings and keeps the manual flow:

1. click **Open proposal email**;
2. download the customer PDF;
3. send manually from your email client;
4. click **Mark proposal sent** in VendorVerdict.
