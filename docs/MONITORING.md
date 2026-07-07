# VendorVerdict monitoring and production health checks

VendorVerdict includes lightweight VM monitoring for the Google Cloud deployment.

The monitor checks:

- `vendorverdict.service` is active.
- Local `/health` returns `200`.
- `/reports` is protected with `401` when authentication is enabled.
- The public HTTPS `/health` endpoint works, if `VENDORVERDICT_PUBLIC_URL` is configured.
- The SQLite database exists and passes `PRAGMA integrity_check`.
- The report export directory exists.
- The backup timer is enabled.
- The latest backup exists, is recent, and passes SHA256 verification.
- Disk usage is below the configured threshold.

## Environment settings

Add these to `/etc/vendorverdict/vendorverdict.env`:

```env
VENDORVERDICT_PUBLIC_URL=https://vendorverdict.docoply.com
VENDORVERDICT_MONITOR_MAX_BACKUP_AGE_HOURS=36
VENDORVERDICT_MONITOR_MAX_DISK_USED_PERCENT=85
VENDORVERDICT_MONITOR_CURL_TIMEOUT_SECONDS=10
```

`VENDORVERDICT_PUBLIC_URL` is optional, but recommended after HTTPS is live.

## Install the monitoring timer

After pulling the latest code on the VM:

```bash
cd /tmp/vendorverdict
git pull origin main

sudo mkdir -p /opt/vendorverdict/scripts
sudo install -m 0755 scripts/check_vendorverdict_health.sh /opt/vendorverdict/scripts/check_vendorverdict_health.sh
sudo install -m 0755 scripts/status_vendorverdict.sh /opt/vendorverdict/scripts/status_vendorverdict.sh
sudo cp deploy/gcp/vendorverdict-monitor.service /etc/systemd/system/vendorverdict-monitor.service
sudo cp deploy/gcp/vendorverdict-monitor.timer /etc/systemd/system/vendorverdict-monitor.timer

sudo systemctl daemon-reload
sudo systemctl enable --now vendorverdict-monitor.timer
```

## Run checks manually

```bash
sudo systemctl start vendorverdict-monitor
sudo journalctl -u vendorverdict-monitor -n 100 --no-pager
```

A successful run ends with:

```text
VendorVerdict health check finished with 0 failure(s), 0 warning(s).
```

## Check timer schedule

```bash
sudo systemctl status vendorverdict-monitor.timer --no-pager
systemctl list-timers | grep vendorverdict
```

The monitor runs every 15 minutes.

## One-shot status report

Use this when debugging production:

```bash
sudo /opt/vendorverdict/scripts/status_vendorverdict.sh
```

It prints:

- service status
- local health JSON
- public health response
- listening ports
- database and export paths
- backup status
- monitoring timer status
- disk usage
- recent app logs
- recent monitor logs

## Troubleshooting

### Monitor says local `/health` failed

```bash
sudo systemctl status vendorverdict --no-pager -l
sudo journalctl -u vendorverdict -n 100 --no-pager
sudo ss -ltnp | grep 8080 || true
```

### Monitor says backup is stale

```bash
sudo systemctl status vendorverdict-backup.timer --no-pager
sudo systemctl start vendorverdict-backup
sudo journalctl -u vendorverdict-backup -n 100 --no-pager
sudo ls -la /var/backups/vendorverdict/latest/
```

### Monitor says disk usage is high

```bash
df -h
sudo du -sh /var/lib/vendorverdict /var/backups/vendorverdict /opt/vendorverdict
```

Remove old backups only after confirming a recent valid backup exists.

### Monitor says SHA256 verification failed

Create a fresh backup and inspect the latest folder:

```bash
sudo systemctl start vendorverdict-backup
sudo bash -lc 'cd /var/backups/vendorverdict/latest && sha256sum -c SHA256SUMS'
```

## Alerts

The monitor can send an alert when one or more checks fail.

Install the alert sender:

```bash
sudo mkdir -p /opt/vendorverdict/scripts /var/lib/vendorverdict/monitor
sudo install -m 0755 scripts/send_vendorverdict_alert.sh /opt/vendorverdict/scripts/send_vendorverdict_alert.sh
sudo install -m 0755 scripts/check_vendorverdict_health.sh /opt/vendorverdict/scripts/check_vendorverdict_health.sh
sudo cp deploy/gcp/vendorverdict-monitor.service /etc/systemd/system/vendorverdict-monitor.service
sudo systemctl daemon-reload
```

Enable alerts in `/etc/vendorverdict/vendorverdict.env`:

```env
VENDORVERDICT_ALERT_ENABLED=1
VENDORVERDICT_ALERT_WEBHOOK_URL=https://example.com/your-webhook-url
VENDORVERDICT_ALERT_WEBHOOK_FORMAT=generic
VENDORVERDICT_ALERT_COOLDOWN_SECONDS=3600
```

Send a direct test alert:

```bash
printf 'VendorVerdict test alert\n' | sudo /opt/vendorverdict/scripts/send_vendorverdict_alert.sh 'VendorVerdict test alert'
```

See `docs/ALERTS.md` for webhook formats, email fallback, and failure-test instructions.

## Deployment-safe script permissions

After manual deployments, operational scripts must be executable. The preferred fix is to use:

```bash
sudo scripts/deploy_gcp_vm.sh
```

The deploy script reinstalls health, status, alert, backup, and restore scripts with `0755` permissions before restarting systemd services.

