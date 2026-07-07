#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${VENDORVERDICT_ENV_FILE:-/etc/vendorverdict/vendorverdict.env}"
if [ -f "${ENV_FILE}" ]; then
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
fi

API_HOST="${VENDORVERDICT_API_HOST:-127.0.0.1}"
API_PORT="${VENDORVERDICT_API_PORT:-8080}"
LOCAL_URL="http://${API_HOST}:${API_PORT}"
DB_PATH="${VENDORVERDICT_API_DB_PATH:-/var/lib/vendorverdict/vendorverdict.sqlite3}"
EXPORT_DIR="${VENDORVERDICT_API_EXPORT_DIR:-/var/lib/vendorverdict/reports}"
BACKUP_DIR="${VENDORVERDICT_BACKUP_DIR:-/var/backups/vendorverdict}"
PUBLIC_URL="${VENDORVERDICT_PUBLIC_URL:-}"

section() { printf '\n== %s ==\n' "$*"; }

section "VendorVerdict service"
sudo systemctl status vendorverdict --no-pager -l || true

section "Local health"
curl -sS "${LOCAL_URL}/health" || true
printf '\n'

if [ -n "${PUBLIC_URL}" ]; then
  section "Public health"
  curl -i -sS "${PUBLIC_URL%/}/health" || true
  printf '\n'
fi

section "Ports"
sudo ss -ltnp | grep -E ':8080|:80|:443' || true

section "Database and reports"
ls -lh "${DB_PATH}" 2>/dev/null || true
ls -ld "${EXPORT_DIR}" 2>/dev/null || true
if command -v sqlite3 >/dev/null 2>&1 && [ -f "${DB_PATH}" ]; then
  sqlite3 "${DB_PATH}" 'PRAGMA integrity_check;' || true
fi

section "Backups"
sudo systemctl status vendorverdict-backup.timer --no-pager -l || true
sudo ls -la "${BACKUP_DIR}" || true
if [ -e "${BACKUP_DIR}/latest" ]; then
  sudo ls -la "${BACKUP_DIR}/latest/" || true
fi

section "Monitoring timer"
sudo systemctl status vendorverdict-monitor.timer --no-pager -l || true

section "Alerts"
printf 'Enabled: %s\n' "${VENDORVERDICT_ALERT_ENABLED:-0}"
printf 'Webhook configured: %s\n' "$([ -n "${VENDORVERDICT_ALERT_WEBHOOK_URL:-}" ] && echo yes || echo no)"
printf 'Email recipient configured: %s\n' "$([ -n "${VENDORVERDICT_ALERT_EMAIL_TO:-}" ] && echo yes || echo no)"
printf 'Cooldown seconds: %s\n' "${VENDORVERDICT_ALERT_COOLDOWN_SECONDS:-3600}"
if [ -d "${VENDORVERDICT_ALERT_STATE_DIR:-/var/lib/vendorverdict/monitor}" ]; then
  sudo ls -la "${VENDORVERDICT_ALERT_STATE_DIR:-/var/lib/vendorverdict/monitor}" || true
fi

section "Disk"
df -h / /var/lib/vendorverdict /var/backups/vendorverdict 2>/dev/null || df -h

section "Recent app logs"
sudo journalctl -u vendorverdict -n 40 --no-pager || true

section "Recent monitor logs"
sudo journalctl -u vendorverdict-monitor -n 40 --no-pager || true
