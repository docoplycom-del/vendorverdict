# VendorVerdict backups

VendorVerdict production on the Google Compute Engine VM stores reports in:

- SQLite database: `/var/lib/vendorverdict/vendorverdict.sqlite3`
- exported files: `/var/lib/vendorverdict/reports`

The backup step adds a local nightly backup timer that copies both into timestamped directories under `/var/backups/vendorverdict`.

## Files added

- `scripts/backup_vendorverdict.sh`
- `scripts/restore_vendorverdict_backup.sh`
- `deploy/gcp/vendorverdict-backup.service`
- `deploy/gcp/vendorverdict-backup.timer`

## Schedule

The systemd timer runs every night at 02:15 UTC:

```bash
sudo systemctl status vendorverdict-backup.timer --no-pager
systemctl list-timers | grep vendorverdict
```

## Run a backup manually

```bash
sudo systemctl start vendorverdict-backup
sudo journalctl -u vendorverdict-backup -n 60 --no-pager
sudo ls -la /var/backups/vendorverdict
```

A successful backup creates a directory like:

```text
/var/backups/vendorverdict/20260707T021500Z/
  vendorverdict.sqlite3
  reports.tar.gz
  SHA256SUMS
  manifest.txt
```

The `latest` symlink points to the most recent backup.

## Verify the latest backup

```bash
cd /var/backups/vendorverdict/latest
sudo sha256sum -c SHA256SUMS
sudo sqlite3 vendorverdict.sqlite3 'PRAGMA integrity_check;'
```

Expected SQLite result:

```text
ok
```

## Retention

Default retention is 14 days.

Configure it in `/etc/vendorverdict/vendorverdict.env`:

```env
VENDORVERDICT_BACKUP_DIR=/var/backups/vendorverdict
VENDORVERDICT_BACKUP_RETENTION_DAYS=14
```

Restarting the app is not required for backup-only env changes. The backup service reads the env file when it runs.

## Restore from a backup

Use this only when you intentionally want to replace the current production database and report files.

```bash
sudo /opt/vendorverdict/scripts/restore_vendorverdict_backup.sh /var/backups/vendorverdict/20260707T021500Z
```

The restore script:

1. Verifies `SHA256SUMS` if present.
2. Stops `vendorverdict.service`.
3. Saves a copy of the current database as `vendorverdict.sqlite3.pre-restore.<timestamp>`.
4. Restores the backup database and reports archive.
5. Fixes ownership and permissions.
6. Starts `vendorverdict.service`.

After restore:

```bash
curl http://127.0.0.1:8080/health
curl -i -u admin:'YOUR_PASSWORD' http://127.0.0.1:8080/reports
```

## Recommended next hardening

Local VM backups protect against app mistakes, but not against VM loss. For stronger protection, periodically copy `/var/backups/vendorverdict` to Google Cloud Storage or another off-VM location.

Example future command:

```bash
gsutil rsync -r /var/backups/vendorverdict gs://YOUR_BUCKET/vendorverdict-backups
```
