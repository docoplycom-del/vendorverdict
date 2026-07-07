#!/usr/bin/env bash
set -euo pipefail

# VendorVerdict production health check.
# Intended for systemd timers and manual VM diagnostics.

ENV_FILE="${VENDORVERDICT_ENV_FILE:-/etc/vendorverdict/vendorverdict.env}"
if [ -f "${ENV_FILE}" ]; then
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
fi

SERVICE_NAME="${VENDORVERDICT_SERVICE_NAME:-vendorverdict.service}"
BACKUP_TIMER="${VENDORVERDICT_BACKUP_TIMER:-vendorverdict-backup.timer}"
API_HOST="${VENDORVERDICT_API_HOST:-127.0.0.1}"
API_PORT="${VENDORVERDICT_API_PORT:-8080}"
LOCAL_URL="http://${API_HOST}:${API_PORT}"
PUBLIC_URL="${VENDORVERDICT_PUBLIC_URL:-}"
DB_PATH="${VENDORVERDICT_API_DB_PATH:-/var/lib/vendorverdict/vendorverdict.sqlite3}"
EXPORT_DIR="${VENDORVERDICT_API_EXPORT_DIR:-/var/lib/vendorverdict/reports}"
BACKUP_DIR="${VENDORVERDICT_BACKUP_DIR:-/var/backups/vendorverdict}"
MAX_BACKUP_AGE_HOURS="${VENDORVERDICT_MONITOR_MAX_BACKUP_AGE_HOURS:-36}"
MAX_DISK_USED_PERCENT="${VENDORVERDICT_MONITOR_MAX_DISK_USED_PERCENT:-85}"
CURL_TIMEOUT="${VENDORVERDICT_MONITOR_CURL_TIMEOUT_SECONDS:-10}"

failures=0
warnings=0
events=()

ok() { printf 'OK: %s\n' "$*"; }
warn() { local msg="$*"; printf 'WARN: %s\n' "${msg}" >&2; warnings=$((warnings + 1)); events+=("WARN: ${msg}"); }
fail() { local msg="$*"; printf 'FAIL: %s\n' "${msg}" >&2; failures=$((failures + 1)); events+=("FAIL: ${msg}"); }

http_code() {
  local url="$1"
  curl --max-time "${CURL_TIMEOUT}" -sS -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true
}

printf 'VendorVerdict health check started at %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'Using env file: %s\n' "${ENV_FILE}"

if systemctl is-active --quiet "${SERVICE_NAME}"; then
  ok "${SERVICE_NAME} is active"
else
  fail "${SERVICE_NAME} is not active"
fi

local_health_code="$(http_code "${LOCAL_URL}/health")"
if [ "${local_health_code}" = "200" ]; then
  ok "local /health returned 200 (${LOCAL_URL}/health)"
else
  fail "local /health returned ${local_health_code:-no-response} (${LOCAL_URL}/health)"
fi

if [ "${VENDORVERDICT_AUTH_ENABLED:-0}" = "1" ]; then
  reports_code="$(http_code "${LOCAL_URL}/reports")"
  if [ "${reports_code}" = "401" ]; then
    ok "unauthenticated local /reports is protected with 401"
  else
    fail "unauthenticated local /reports returned ${reports_code:-no-response}; expected 401"
  fi
fi

if [ -n "${PUBLIC_URL}" ]; then
  public_health_code="$(http_code "${PUBLIC_URL%/}/health")"
  if [ "${public_health_code}" = "200" ]; then
    ok "public /health returned 200 (${PUBLIC_URL%/}/health)"
  else
    fail "public /health returned ${public_health_code:-no-response} (${PUBLIC_URL%/}/health)"
  fi

  public_dashboard_code="$(http_code "${PUBLIC_URL%/}/dashboard")"
  case "${public_dashboard_code}" in
    200|303|307|401) ok "public /dashboard returned expected protected status ${public_dashboard_code}" ;;
    *) fail "public /dashboard returned ${public_dashboard_code:-no-response}; expected 200, 303, 307, or 401" ;;
  esac
fi

if [ -f "${DB_PATH}" ]; then
  ok "database exists: ${DB_PATH}"
  if command -v sqlite3 >/dev/null 2>&1; then
    integrity="$(sqlite3 "${DB_PATH}" 'PRAGMA integrity_check;' 2>/dev/null || true)"
    if [ "${integrity}" = "ok" ]; then
      ok "SQLite integrity_check returned ok"
    else
      fail "SQLite integrity_check returned: ${integrity:-no-output}"
    fi
  else
    warn "sqlite3 command not installed; skipping DB integrity_check"
  fi
else
  fail "database missing: ${DB_PATH}"
fi

if [ -d "${EXPORT_DIR}" ]; then
  ok "export directory exists: ${EXPORT_DIR}"
else
  fail "export directory missing: ${EXPORT_DIR}"
fi

if systemctl is-enabled --quiet "${BACKUP_TIMER}"; then
  ok "${BACKUP_TIMER} is enabled"
else
  warn "${BACKUP_TIMER} is not enabled"
fi

latest_backup="${BACKUP_DIR}/latest"
if [ -e "${latest_backup}" ]; then
  resolved_backup="$(readlink -f "${latest_backup}" || true)"
  ok "latest backup points to ${resolved_backup:-${latest_backup}}"

  if [ -f "${latest_backup}/SHA256SUMS" ]; then
    if (cd "${latest_backup}" && sha256sum -c SHA256SUMS >/dev/null); then
      ok "latest backup SHA256 verification passed"
    else
      fail "latest backup SHA256 verification failed"
    fi
  else
    fail "latest backup missing SHA256SUMS"
  fi

  backup_mtime="$(stat -c %Y "${latest_backup}" 2>/dev/null || stat -c %Y "${resolved_backup}" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  max_age_seconds=$((MAX_BACKUP_AGE_HOURS * 3600))
  age_seconds=$((now - backup_mtime))
  if [ "${age_seconds}" -le "${max_age_seconds}" ]; then
    ok "latest backup age is within ${MAX_BACKUP_AGE_HOURS}h"
  else
    fail "latest backup is older than ${MAX_BACKUP_AGE_HOURS}h"
  fi
else
  fail "latest backup missing: ${latest_backup}"
fi

if command -v df >/dev/null 2>&1; then
  disk_target="${DB_PATH}"
  [ -e "${disk_target}" ] || disk_target="${EXPORT_DIR}"
  [ -e "${disk_target}" ] || disk_target="/"
  disk_used_percent="$(df -P "${disk_target}" | awk 'NR==2 {gsub(/%/, "", $5); print $5}')"
  if [ -n "${disk_used_percent}" ] && [ "${disk_used_percent}" -le "${MAX_DISK_USED_PERCENT}" ]; then
    ok "disk usage is ${disk_used_percent}% <= ${MAX_DISK_USED_PERCENT}%"
  else
    fail "disk usage is ${disk_used_percent:-unknown}% > ${MAX_DISK_USED_PERCENT}%"
  fi
fi

printf 'VendorVerdict health check finished with %s failure(s), %s warning(s).\n' "${failures}" "${warnings}"

if [ "${failures}" -gt 0 ]; then
  if [ "${VENDORVERDICT_ALERT_ENABLED:-0}" = "1" ]; then
    alert_script="${VENDORVERDICT_ALERT_SCRIPT:-/opt/vendorverdict/scripts/send_vendorverdict_alert.sh}"
    if [ -x "${alert_script}" ]; then
      {
        printf 'VendorVerdict monitor detected %s failure(s) and %s warning(s).\n' "${failures}" "${warnings}"
        printf 'Timestamp: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf 'Host: %s\n' "$(hostname -f 2>/dev/null || hostname)"
        printf 'Service: %s\n' "${SERVICE_NAME}"
        printf 'Local URL: %s\n' "${LOCAL_URL}"
        if [ -n "${PUBLIC_URL}" ]; then
          printf 'Public URL: %s\n' "${PUBLIC_URL}"
        fi
        printf '\nFailure / warning details:\n'
        if [ "${#events[@]}" -gt 0 ]; then
          printf '%s\n' "${events[@]}"
        else
          printf 'No detailed events captured.\n'
        fi
        printf '\nRecent application logs:\n'
        journalctl -u "${SERVICE_NAME}" -n 25 --no-pager 2>/dev/null || true
      } | "${alert_script}" "VendorVerdict production alert: ${failures} failure(s)" || warn "alert script failed"
    else
      warn "alert script not found or not executable: ${alert_script}"
    fi
  fi
  exit 1
fi
