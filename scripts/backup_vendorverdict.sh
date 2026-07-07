#!/usr/bin/env bash
set -euo pipefail

# Backup VendorVerdict production data from a Google Compute Engine VM.
# Intended to run from systemd timer as root.
# It creates a timestamped directory under /var/backups/vendorverdict by default.

ENV_FILE="${VENDORVERDICT_ENV_FILE:-/etc/vendorverdict/vendorverdict.env}"
BACKUP_ROOT="${VENDORVERDICT_BACKUP_DIR:-/var/backups/vendorverdict}"
RETENTION_DAYS="${VENDORVERDICT_BACKUP_RETENTION_DAYS:-14}"
LOCK_FILE="${VENDORVERDICT_BACKUP_LOCK_FILE:-/tmp/vendorverdict-backup.lock}"

if [ -f "${ENV_FILE}" ]; then
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
fi

DB_PATH="${VENDORVERDICT_API_DB_PATH:-/var/lib/vendorverdict/vendorverdict.sqlite3}"
REPORTS_DIR="${VENDORVERDICT_API_EXPORT_DIR:-/var/lib/vendorverdict/reports}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

mkdir -p "${BACKUP_ROOT}"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "Another VendorVerdict backup is already running." >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

if [ ! -f "${DB_PATH}" ]; then
  echo "Database not found: ${DB_PATH}" >&2
  exit 1
fi

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "${DB_PATH}" ".backup '${BACKUP_DIR}/vendorverdict.sqlite3'"
else
  cp "${DB_PATH}" "${BACKUP_DIR}/vendorverdict.sqlite3"
fi

if [ -d "${REPORTS_DIR}" ]; then
  tar -czf "${BACKUP_DIR}/reports.tar.gz" -C "${REPORTS_DIR}" .
else
  mkdir -p "${BACKUP_DIR}/empty-reports-dir"
  tar -czf "${BACKUP_DIR}/reports.tar.gz" -C "${BACKUP_DIR}" empty-reports-dir
  rm -rf "${BACKUP_DIR}/empty-reports-dir"
fi

cat > "${BACKUP_DIR}/manifest.txt" <<MANIFEST
VendorVerdict backup
created_at_utc=${TIMESTAMP}
database=${DB_PATH}
reports_dir=${REPORTS_DIR}
hostname=$(hostname)
MANIFEST

sha256sum "${BACKUP_DIR}/vendorverdict.sqlite3" "${BACKUP_DIR}/reports.tar.gz" > "${BACKUP_DIR}/SHA256SUMS"

find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -mtime +"${RETENTION_DAYS}" -print -exec rm -rf {} \;

LATEST_LINK="${BACKUP_ROOT}/latest"
rm -f "${LATEST_LINK}"
ln -s "${BACKUP_DIR}" "${LATEST_LINK}"

echo "VendorVerdict backup created: ${BACKUP_DIR}"
