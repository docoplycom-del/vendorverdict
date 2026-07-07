#!/usr/bin/env bash
set -euo pipefail

# Send a VendorVerdict production alert.
# Reads alert body from stdin and sends it to an optional webhook and/or local mailer.
# Intended to be called by scripts/check_vendorverdict_health.sh.

ENV_FILE="${VENDORVERDICT_ENV_FILE:-/etc/vendorverdict/vendorverdict.env}"
if [ -f "${ENV_FILE}" ]; then
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
fi

if [ "${VENDORVERDICT_ALERT_ENABLED:-0}" != "1" ]; then
  printf 'VendorVerdict alerts are disabled; skipping alert send.\n'
  exit 0
fi

SUBJECT="${1:-VendorVerdict production alert}"
BODY="$(cat)"
ALERT_NAME="${VENDORVERDICT_ALERT_NAME:-VendorVerdict production}"
WEBHOOK_URL="${VENDORVERDICT_ALERT_WEBHOOK_URL:-}"
WEBHOOK_FORMAT="${VENDORVERDICT_ALERT_WEBHOOK_FORMAT:-generic}"
EMAIL_TO="${VENDORVERDICT_ALERT_EMAIL_TO:-}"
EMAIL_FROM="${VENDORVERDICT_ALERT_EMAIL_FROM:-vendorverdict@localhost}"
STATE_DIR="${VENDORVERDICT_ALERT_STATE_DIR:-/var/lib/vendorverdict/monitor}"
COOLDOWN_SECONDS="${VENDORVERDICT_ALERT_COOLDOWN_SECONDS:-3600}"
CURL_TIMEOUT="${VENDORVERDICT_MONITOR_CURL_TIMEOUT_SECONDS:-10}"

mkdir -p "${STATE_DIR}"

fingerprint="$(printf '%s\n%s\n' "${SUBJECT}" "${BODY}" | sha256sum | awk '{print $1}')"
last_hash_file="${STATE_DIR}/last_alert.sha256"
last_sent_file="${STATE_DIR}/last_alert.sent_at"
now="$(date +%s)"

if [ -f "${last_hash_file}" ] && [ -f "${last_sent_file}" ]; then
  last_hash="$(cat "${last_hash_file}" 2>/dev/null || true)"
  last_sent="$(cat "${last_sent_file}" 2>/dev/null || echo 0)"
  if [ "${last_hash}" = "${fingerprint}" ] && [ $((now - last_sent)) -lt "${COOLDOWN_SECONDS}" ]; then
    printf 'VendorVerdict alert suppressed by cooldown (%ss).\n' "${COOLDOWN_SECONDS}"
    exit 0
  fi
fi

sent=0
message="${ALERT_NAME}: ${SUBJECT}

${BODY}"

if [ -n "${WEBHOOK_URL}" ]; then
  payload="$(ALERT_MESSAGE="${message}" ALERT_FORMAT="${WEBHOOK_FORMAT}" python3 - <<'PY'
import json
import os

message = os.environ.get("ALERT_MESSAGE", "")
fmt = os.environ.get("ALERT_FORMAT", "generic").lower()
if fmt == "discord":
    print(json.dumps({"content": message[:1900]}))
elif fmt in {"slack", "generic", "text"}:
    print(json.dumps({"text": message}))
else:
    print(json.dumps({"text": message}))
PY
)"
  if curl --max-time "${CURL_TIMEOUT}" -fsS -X POST -H 'Content-Type: application/json' --data "${payload}" "${WEBHOOK_URL}" >/dev/null; then
    printf 'VendorVerdict alert sent to webhook.\n'
    sent=1
  else
    printf 'WARN: failed to send VendorVerdict alert to webhook.\n' >&2
  fi
fi

if [ -n "${EMAIL_TO}" ]; then
  if command -v mail >/dev/null 2>&1; then
    if printf '%s\n' "${BODY}" | mail -s "${SUBJECT}" -r "${EMAIL_FROM}" "${EMAIL_TO}"; then
      printf 'VendorVerdict alert sent by mail command.\n'
      sent=1
    else
      printf 'WARN: mail command failed while sending VendorVerdict alert.\n' >&2
    fi
  elif command -v sendmail >/dev/null 2>&1; then
    if {
      printf 'From: %s\n' "${EMAIL_FROM}"
      printf 'To: %s\n' "${EMAIL_TO}"
      printf 'Subject: %s\n' "${SUBJECT}"
      printf '\n%s\n' "${BODY}"
    } | sendmail -t; then
      printf 'VendorVerdict alert sent by sendmail.\n'
      sent=1
    else
      printf 'WARN: sendmail failed while sending VendorVerdict alert.\n' >&2
    fi
  else
    printf 'WARN: VENDORVERDICT_ALERT_EMAIL_TO is set, but neither mail nor sendmail is installed.\n' >&2
  fi
fi

if [ "${sent}" -eq 1 ]; then
  printf '%s' "${fingerprint}" > "${last_hash_file}"
  printf '%s' "${now}" > "${last_sent_file}"
else
  printf 'WARN: no VendorVerdict alert channel succeeded. Configure VENDORVERDICT_ALERT_WEBHOOK_URL or VENDORVERDICT_ALERT_EMAIL_TO.\n' >&2
fi
