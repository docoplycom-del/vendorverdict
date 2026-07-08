# Google Cloud Compute Engine deployment

This deployment target is a Google Compute Engine VM, not Azure Container Apps.

Recommended production/pilot shape:

```text
Browser / API client
        |
        v
HTTPS subdomain, for example vendorverdict.docoply.com
        |
        v
Apache reverse proxy on the VM
        |
        v
VendorVerdict FastAPI service on 127.0.0.1:8080
        |
        v
SQLite database and exported reports in /var/lib/vendorverdict
```

This is suitable for a pilot or small production deployment. For larger multi-customer usage, move persistence to Cloud SQL/Postgres and object storage.

## Target VM

Example SSH command:

```bash
gcloud compute ssh --zone "us-central1-c" "instance-20250730-190838" --project "ultra-strength-467518-r2"
```

## Paths

| Purpose | Path |
|---|---|
| App code | `/opt/vendorverdict` |
| Environment file | `/etc/vendorverdict/vendorverdict.env` |
| SQLite database | `/var/lib/vendorverdict/vendorverdict.sqlite3` |
| Exported reports | `/var/lib/vendorverdict/reports` |
| Systemd service | `vendorverdict.service` |
| Local app port | `127.0.0.1:8080` |

Do not expose port 8080 directly to the public internet. Keep it bound to `127.0.0.1` and expose the app through Apache/Nginx with HTTPS.

## 1. SSH into the VM

```bash
gcloud compute ssh --zone "us-central1-c" "instance-20250730-190838" --project "ultra-strength-467518-r2"
```

## 2. Install the app as a systemd service

```bash
cd /tmp
rm -rf vendorverdict

git clone https://github.com/docoplycom-del/vendorverdict.git
cd vendorverdict

bash scripts/install_gcp_vm.sh
```

Then edit the production env file:

```bash
sudo nano /etc/vendorverdict/vendorverdict.env
```

Minimum production values:

```env
VENDORVERDICT_API_DB_PATH=/var/lib/vendorverdict/vendorverdict.sqlite3
VENDORVERDICT_API_EXPORT_DIR=/var/lib/vendorverdict/reports
VENDORVERDICT_AUTH_ENABLED=1
VENDORVERDICT_AUTH_USERNAME=admin
VENDORVERDICT_AUTH_PASSWORD=replace-with-a-strong-password
VENDORVERDICT_AUTH_SECRET=replace-with-a-long-random-session-secret
VENDORVERDICT_AUTH_SECURE_COOKIE=1
```

Generate a strong session secret on the VM:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

Restart after editing:

```bash
sudo systemctl restart vendorverdict
sudo systemctl status vendorverdict --no-pager
curl http://127.0.0.1:8080/health
```

Expected health response:

```json
{"status":"ok"}
```

## 3. Configure Apache reverse proxy

Enable proxy modules:

```bash
sudo a2enmod proxy proxy_http headers ssl rewrite
sudo systemctl restart apache2
```

Copy the example vhost:

```bash
sudo cp /opt/vendorverdict/deploy/gcp/apache-vhost.conf /etc/apache2/sites-available/vendorverdict.conf
sudo nano /etc/apache2/sites-available/vendorverdict.conf
```

Change:

```apache
ServerName vendorverdict.example.com
```

to your real subdomain, for example:

```apache
ServerName vendorverdict.docoply.com
```

Enable the site:

```bash
sudo a2ensite vendorverdict.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

## 4. Point DNS to the VM

Create a DNS record for the subdomain, for example:

```text
Type: A
Name: vendorverdict
Value: <VM external IP>
Proxy: DNS only first, then enable proxy if needed
```

Do not reuse the main `docoply.com` vhost unless you deliberately want to serve VendorVerdict from a path. A subdomain is safer.

## 5. Add HTTPS

After DNS resolves to the VM:

```bash
sudo apt-get install -y certbot python3-certbot-apache
sudo certbot --apache -d vendorverdict.docoply.com
```

Then set secure cookies:

```bash
sudo nano /etc/vendorverdict/vendorverdict.env
# VENDORVERDICT_AUTH_SECURE_COOKIE=1
sudo systemctl restart vendorverdict
```

## 6. Verify production behavior

From the VM:

```bash
curl http://127.0.0.1:8080/health
curl -i http://127.0.0.1:8080/reports
curl -i -u admin:YOUR_PASSWORD http://127.0.0.1:8080/reports
```

Expected:

```text
/health -> 200 OK
/reports without credentials -> 401 Unauthorized
/reports with Basic Auth -> 200 OK
```

From your browser:

```text
https://vendorverdict.docoply.com/login
https://vendorverdict.docoply.com/dashboard
```

## 7. Update deployment after a new GitHub push

```bash
sudo systemctl stop vendorverdict
cd /opt/vendorverdict
sudo git pull --ff-only origin main
sudo chown -R vendorverdict:www-data /opt/vendorverdict
sudo -u vendorverdict /opt/vendorverdict/.venv/bin/python -m pip install -e /opt/vendorverdict
sudo systemctl start vendorverdict
sudo systemctl status vendorverdict --no-pager
```

## 8. Backup SQLite reports

For pilots, back up the data directory:

```bash
sudo tar -czf /tmp/vendorverdict-backup-$(date +%F).tar.gz /var/lib/vendorverdict
```

Copy it down:

```bash
gcloud compute scp --zone "us-central1-c" "instance-20250730-190838:/tmp/vendorverdict-backup-YYYY-MM-DD.tar.gz" . --project "ultra-strength-467518-r2"
```

## Notes

- Keep 8080 private and bound to localhost.
- Store real secrets only in `/etc/vendorverdict/vendorverdict.env`.
- Do not commit real credentials to GitHub.
- Use a subdomain first to avoid disrupting any existing Apache/WordPress site on the VM.

## Backups

This deployment includes a nightly local backup timer for the SQLite database and exported report files.

Backed-up paths:

```text
/var/lib/vendorverdict/vendorverdict.sqlite3
/var/lib/vendorverdict/reports
```

Backup destination:

```text
/var/backups/vendorverdict
```

Check the timer:

```bash
sudo systemctl status vendorverdict-backup.timer --no-pager
systemctl list-timers | grep vendorverdict
```

Run a backup manually:

```bash
sudo systemctl start vendorverdict-backup
sudo journalctl -u vendorverdict-backup -n 60 --no-pager
sudo ls -la /var/backups/vendorverdict
```

Verify the latest backup:

```bash
cd /var/backups/vendorverdict/latest
sudo sha256sum -c SHA256SUMS
sudo sqlite3 vendorverdict.sqlite3 'PRAGMA integrity_check;'
```

See `docs/BACKUPS.md` for restore instructions.


## Monitoring and health checks

After the app, HTTPS, and backups are working, install the monitoring timer:

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

Set the public URL in `/etc/vendorverdict/vendorverdict.env`:

```env
VENDORVERDICT_PUBLIC_URL=https://vendorverdict.docoply.com
VENDORVERDICT_MONITOR_MAX_BACKUP_AGE_HOURS=36
VENDORVERDICT_MONITOR_MAX_DISK_USED_PERCENT=85
```

Run a manual check:

```bash
sudo systemctl start vendorverdict-monitor
sudo journalctl -u vendorverdict-monitor -n 100 --no-pager
```

For a full debugging snapshot:

```bash
sudo /opt/vendorverdict/scripts/status_vendorverdict.sh
```

See `docs/MONITORING.md`.

## Optional production alerts

After monitoring is installed, you can enable alerts so failures are pushed to a webhook or local mailer.

Install the alert sender on the VM:

```bash
cd /tmp/vendorverdict
git pull origin main
sudo mkdir -p /opt/vendorverdict/scripts /var/lib/vendorverdict/monitor
sudo install -m 0755 scripts/send_vendorverdict_alert.sh /opt/vendorverdict/scripts/send_vendorverdict_alert.sh
sudo install -m 0755 scripts/check_vendorverdict_health.sh /opt/vendorverdict/scripts/check_vendorverdict_health.sh
sudo cp deploy/gcp/vendorverdict-monitor.service /etc/systemd/system/vendorverdict-monitor.service
sudo systemctl daemon-reload
```

Add alert settings to `/etc/vendorverdict/vendorverdict.env`:

```env
VENDORVERDICT_ALERT_ENABLED=1
VENDORVERDICT_ALERT_WEBHOOK_URL=https://example.com/your-webhook-url
VENDORVERDICT_ALERT_WEBHOOK_FORMAT=generic
VENDORVERDICT_ALERT_COOLDOWN_SECONDS=3600
```

Then test:

```bash
printf 'VendorVerdict test alert from production VM\n' | sudo /opt/vendorverdict/scripts/send_vendorverdict_alert.sh 'VendorVerdict test alert'
```


## Safe deploy command

For every production update, use the safe deploy script:

```bash
cd /tmp/vendorverdict
git pull origin main
sudo scripts/deploy_gcp_vm.sh
```

This script preserves `/opt/vendorverdict/.venv`, reinstalls scripts with executable permissions, restarts the app, waits for local `/health`, checks the public URL, and runs the monitor once.

Do not run plain `rsync -a --delete /tmp/vendorverdict/ /opt/vendorverdict/`; it can delete the production virtual environment. See `docs/SAFE_DEPLOYMENT.md`.

## Customer demo flow check

After deployment, verify the public demo page and protected dashboard:

```bash
curl -i https://vendorverdict.docoply.com/demo
curl -i https://vendorverdict.docoply.com/dashboard
```

Expected:

```text
/demo      -> 200 OK
/dashboard -> 303 See Other when not logged in
```


## Lead capture checks

After deployment, verify the public pilot form and protected lead inbox:

```bash
curl -i https://vendorverdict.docoply.com/pilot
curl -i https://vendorverdict.docoply.com/demo
```

The protected lead inbox is available at `/dashboard/leads`.
