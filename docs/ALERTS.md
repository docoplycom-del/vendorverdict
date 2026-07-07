# VendorVerdict production alerts

VendorVerdict can send an alert when the production monitor detects a failure.

The alert layer is intentionally lightweight. It is designed for the Google Cloud VM deployment and is called by `scripts/check_vendorverdict_health.sh` when the monitor exits with one or more failures.

## What triggers an alert

An alert is sent when the monitor detects failures such as:

- `vendorverdict.service` is not active.
- Local `/health` fails.
- Public `/health` fails.
- `/reports` is not protected when authentication is enabled.
- The SQLite database is missing or fails `PRAGMA integrity_check`.
- The export directory is missing.
- The latest backup is missing, stale, or fails SHA256 verification.
- Disk usage exceeds the configured threshold.

Warnings alone do not make the monitor fail.

## Alert channels

Supported channels:

- Generic webhook using JSON body `{"text":"..."}`.
- Slack-compatible webhook using JSON body `{"text":"..."}`.
- Discord-compatible webhook using JSON body `{"content":"..."}`.
- Local email through `mail` or `sendmail`, if installed and configured on the VM.

Webhook alerts are the recommended first option because they do not require configuring a local mail server.

## Environment variables

Add these to `/etc/vendorverdict/vendorverdict.env`:

```env
VENDORVERDICT_ALERT_ENABLED=1
VENDORVERDICT_ALERT_NAME=VendorVerdict production
VENDORVERDICT_ALERT_WEBHOOK_URL=https://example.com/your-webhook-url
VENDORVERDICT_ALERT_WEBHOOK_FORMAT=generic
VENDORVERDICT_ALERT_COOLDOWN_SECONDS=3600
VENDORVERDICT_ALERT_STATE_DIR=/var/lib/vendorverdict/monitor
```

For Discord, use:

```env
VENDORVERDICT_ALERT_WEBHOOK_FORMAT=discord
```

For Slack, use:

```env
VENDORVERDICT_ALERT_WEBHOOK_FORMAT=slack
```

Optional email settings:

```env
VENDORVERDICT_ALERT_EMAIL_TO=you@example.com
VENDORVERDICT_ALERT_EMAIL_FROM=vendorverdict@docoply.com
```

Email only works if the VM has `mail` or `sendmail` installed and configured.

## Install alert scripts on the VM

After pulling the latest code:

```bash
cd /tmp/vendorverdict
git pull origin main

sudo mkdir -p /opt/vendorverdict/scripts /var/lib/vendorverdict/monitor
sudo install -m 0755 scripts/check_vendorverdict_health.sh /opt/vendorverdict/scripts/check_vendorverdict_health.sh
sudo install -m 0755 scripts/send_vendorverdict_alert.sh /opt/vendorverdict/scripts/send_vendorverdict_alert.sh
sudo install -m 0755 scripts/status_vendorverdict.sh /opt/vendorverdict/scripts/status_vendorverdict.sh
sudo cp deploy/gcp/vendorverdict-monitor.service /etc/systemd/system/vendorverdict-monitor.service
sudo cp deploy/gcp/vendorverdict-monitor.timer /etc/systemd/system/vendorverdict-monitor.timer
sudo chown -R vendorverdict:www-data /var/lib/vendorverdict/monitor

sudo systemctl daemon-reload
sudo systemctl restart vendorverdict-monitor.timer
```

## Test the alert sender directly

Use this to test the webhook/email configuration without breaking the app:

```bash
printf 'This is a VendorVerdict test alert from the production VM.\n' \
  | sudo /opt/vendorverdict/scripts/send_vendorverdict_alert.sh 'VendorVerdict test alert'
```

Expected output for a working webhook:

```text
VendorVerdict alert sent to webhook.
```

If no channel is configured, the script will log a warning but will not affect the running app.

## Test a real monitor failure safely

Temporarily set an impossible public URL in `/etc/vendorverdict/vendorverdict.env`:

```env
VENDORVERDICT_PUBLIC_URL=https://invalid.vendorverdict.example
VENDORVERDICT_ALERT_ENABLED=1
```

Then run:

```bash
sudo systemctl start vendorverdict-monitor
sudo journalctl -u vendorverdict-monitor -n 100 --no-pager
```

Restore the correct URL immediately after the test:

```env
VENDORVERDICT_PUBLIC_URL=https://vendorverdict.docoply.com
```

Then restart the app and run the monitor again:

```bash
sudo systemctl restart vendorverdict
sudo systemctl start vendorverdict-monitor
```

## Cooldown

Duplicate alerts are suppressed for `VENDORVERDICT_ALERT_COOLDOWN_SECONDS`, default `3600` seconds.

The cooldown state is stored in:

```text
/var/lib/vendorverdict/monitor
```

This prevents repeated identical alerts every 15 minutes while a known incident is already active.
