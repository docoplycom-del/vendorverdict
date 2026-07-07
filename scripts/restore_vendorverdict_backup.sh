#!/usr/bin/env bash
set -euo pipefail

# Restore a VendorVerdict backup directory created by backup_vendorverdict.sh.
# Usage:
#   sudo scripts/restore_vendorverdict_backup.sh /var/backups/vendorverdict/20260707T120000Z

if [ "$#" -ne 1 ]; then
  echo "Usage: sudo $0 /path/to/backup-directory" >&2
  exit 2
fi

BACKUP_DIR="$1"
ENV_FILE="${VENDORVERDICT_ENV_FILE:-/etc/vendorverdict/vendorverdict.env}"

if [ -f "${ENV_FILE}" ]; then
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
fi

DB_PATH="${VENDORVERDICT_API_DB_PATH:-/var/lib/vendorverdict/vendorverdict.sqlite3}"
REPORTS_DIR="${VENDORVERDICT_API_EXPORT_DIR:-/var/lib/vendorverdict/reports}"
APP_USER="${VENDORVERDICT_APP_USER:-vendorverdict}"
APP_GROUP="${VENDORVERDICT_APP_GROUP:-www-data}"

if [ ! -f "${BACKUP_DIR}/vendorverdict.sqlite3" ]; then
  echo "Backup database missing: ${BACKUP_DIR}/vendorverdict.sqlite3" >&2
  exit 1
fi

if [ ! -f "${BACKUP_DIR}/reports.tar.gz" ]; then
  echo "Backup reports archive missing: ${BACKUP_DIR}/reports.tar.gz" >&2
  exit 1
fi

if [ -f "${BACKUP_DIR}/SHA256SUMS" ]; then
  (cd "${BACKUP_DIR}" && sha256sum -c SHA256SUMS)
fi

systemctl stop vendorverdict

mkdir -p "$(dirname "${DB_PATH}")" "${REPORTS_DIR}"

if [ -f "${DB_PATH}" ]; then
  cp "${DB_PATH}" "${DB_PATH}.pre-restore.$(date -u +%Y%m%dT%H%M%SZ)"
fi

cp "${BACKUP_DIR}/vendorverdict.sqlite3" "${DB_PATH}"
rm -rf "${REPORTS_DIR:?}"/*
tar -xzf "${BACKUP_DIR}/reports.tar.gz" -C "${REPORTS_DIR}"

chown -R "${APP_USER}:${APP_GROUP}" "$(dirname "${DB_PATH}")" "${REPORTS_DIR}"
chmod 750 "$(dirname "${DB_PATH}")" "${REPORTS_DIR}"
chmod 640 "${DB_PATH}"

systemctl start vendorverdict
systemctl status vendorverdict --no-pager

echo "VendorVerdict restored from ${BACKUP_DIR}"
