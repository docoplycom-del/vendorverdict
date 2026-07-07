#!/usr/bin/env bash
set -euo pipefail

# Safe production deployment for VendorVerdict on the Google Cloud VM.
# Run from the checked-out repository, usually /tmp/vendorverdict:
#   sudo scripts/deploy_gcp_vm.sh
#
# The script deliberately preserves /opt/vendorverdict/.venv and reinstalls
# executable scripts after rsync so deployments do not break systemd services.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PARENT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [ -d "${SCRIPT_PARENT}/.git" ]; then
  DEFAULT_REPO_DIR="${SCRIPT_PARENT}"
else
  DEFAULT_REPO_DIR="/tmp/vendorverdict"
fi

REPO_URL="${REPO_URL:-https://github.com/docoplycom-del/vendorverdict.git}"
REPO_DIR="${REPO_DIR:-${DEFAULT_REPO_DIR}}"
GIT_BRANCH="${GIT_BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/vendorverdict}"
APP_USER="${APP_USER:-vendorverdict}"
APP_GROUP="${APP_GROUP:-www-data}"
ENV_FILE="${ENV_FILE:-/etc/vendorverdict/vendorverdict.env}"
DATA_DIR="${DATA_DIR:-/var/lib/vendorverdict}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/vendorverdict}"
HEALTH_URL="${VENDORVERDICT_LOCAL_HEALTH_URL:-http://127.0.0.1:8080/health}"
HEALTH_ATTEMPTS="${VENDORVERDICT_DEPLOY_HEALTH_ATTEMPTS:-30}"
HEALTH_SLEEP_SECONDS="${VENDORVERDICT_DEPLOY_HEALTH_SLEEP_SECONDS:-2}"
RUN_BACKUP="${VENDORVERDICT_DEPLOY_RUN_BACKUP:-1}"
RUN_MONITOR="${VENDORVERDICT_DEPLOY_RUN_MONITOR:-1}"

log() {
  printf '\n[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

fail() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

require_root() {
  if [ "${EUID}" -ne 0 ]; then
    fail "Run this script with sudo, for example: sudo scripts/deploy_gcp_vm.sh"
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

run_as_app_user() {
  runuser -u "${APP_USER}" -- "$@"
}

safe_path_guard() {
  case "${APP_DIR}" in
    ""|"/"|"/opt"|"/tmp"|"/var"|"/usr"|"/etc")
      fail "Refusing to deploy to unsafe APP_DIR=${APP_DIR}"
      ;;
  esac
}

load_env_if_valid() {
  if [ -f "${ENV_FILE}" ]; then
    log "Validating environment file: ${ENV_FILE}"
    # shellcheck disable=SC1090
    bash -n "${ENV_FILE}" || fail "Invalid shell syntax in ${ENV_FILE}"
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
    if [ -n "${VENDORVERDICT_PUBLIC_URL:-}" ]; then
      PUBLIC_HEALTH_URL="${VENDORVERDICT_PUBLIC_URL%/}/health"
    else
      PUBLIC_HEALTH_URL=""
    fi
  else
    PUBLIC_HEALTH_URL=""
  fi
}

ensure_repo() {
  if [ ! -d "${REPO_DIR}/.git" ]; then
    log "Repository not found at ${REPO_DIR}; cloning ${REPO_URL}"
    mkdir -p "$(dirname "${REPO_DIR}")"
    git clone "${REPO_URL}" "${REPO_DIR}"
  fi
  [ -f "${REPO_DIR}/pyproject.toml" ] || fail "${REPO_DIR} does not look like the VendorVerdict repository"
}

update_repo() {
  log "Updating ${REPO_DIR} from origin/${GIT_BRANCH}"
  git -C "${REPO_DIR}" fetch origin "${GIT_BRANCH}"
  git -C "${REPO_DIR}" checkout "${GIT_BRANCH}"
  git -C "${REPO_DIR}" pull --ff-only origin "${GIT_BRANCH}"
  DEPLOY_SHA="$(git -C "${REPO_DIR}" rev-parse --short HEAD)"
  log "Deploying commit ${DEPLOY_SHA}"
}

ensure_user_and_dirs() {
  log "Ensuring user and directories"
  if ! id "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "${APP_USER}"
  fi

  mkdir -p "${APP_DIR}" "${DATA_DIR}/reports" "${DATA_DIR}/monitor" "${BACKUP_DIR}"
  chown -R "${APP_USER}:${APP_GROUP}" "${DATA_DIR}" "${APP_DIR}"
  chown -R root:root "${BACKUP_DIR}"
  chmod 750 "${DATA_DIR}"
  chmod 700 "${BACKUP_DIR}"
}

run_pre_deploy_backup() {
  if [ "${RUN_BACKUP}" != "1" ]; then
    log "Skipping pre-deploy backup because VENDORVERDICT_DEPLOY_RUN_BACKUP=${RUN_BACKUP}"
    return 0
  fi

  if systemctl list-unit-files vendorverdict-backup.service >/dev/null 2>&1; then
    log "Running pre-deploy backup"
    if ! systemctl start vendorverdict-backup.service; then
      fail "Pre-deploy backup failed. Check: sudo journalctl -u vendorverdict-backup -n 100 --no-pager"
    fi
  else
    log "Backup service not installed yet; skipping pre-deploy backup"
  fi
}

sync_code_preserving_runtime() {
  log "Syncing code to ${APP_DIR} while preserving runtime state"
  rsync -a --delete \
    --exclude ".git" \
    --exclude ".venv" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    "${REPO_DIR}/" "${APP_DIR}/"
  chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
}

ensure_venv_and_install() {
  log "Ensuring Python virtual environment"
  if [ ! -x "${APP_DIR}/.venv/bin/python" ]; then
    log "Virtual environment missing; creating ${APP_DIR}/.venv"
    rm -rf "${APP_DIR}/.venv"
    run_as_app_user python3 -m venv "${APP_DIR}/.venv"
  else
    log "Preserving existing virtual environment at ${APP_DIR}/.venv"
  fi

  log "Installing/updating Python package"
  run_as_app_user "${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip
  run_as_app_user "${APP_DIR}/.venv/bin/python" -m pip install -e "${APP_DIR}"

  [ -x "${APP_DIR}/.venv/bin/vendorverdict-api" ] || fail "vendorverdict-api executable is missing after install"
}

install_runtime_scripts() {
  log "Installing executable operational scripts"
  mkdir -p "${APP_DIR}/scripts"
  for script in \
    check_vendorverdict_health.sh \
    status_vendorverdict.sh \
    send_vendorverdict_alert.sh \
    backup_vendorverdict.sh \
    restore_vendorverdict_backup.sh \
    deploy_gcp_vm.sh; do
    if [ -f "${REPO_DIR}/scripts/${script}" ]; then
      install -m 0755 "${REPO_DIR}/scripts/${script}" "${APP_DIR}/scripts/${script}"
    fi
  done
  chown -R root:root "${APP_DIR}/scripts"
  chmod 755 "${APP_DIR}/scripts"
}

install_systemd_units() {
  log "Installing systemd units"
  install -m 0644 "${APP_DIR}/deploy/gcp/vendorverdict.service" /etc/systemd/system/vendorverdict.service

  if [ -f "${APP_DIR}/deploy/gcp/vendorverdict-backup.service" ]; then
    install -m 0644 "${APP_DIR}/deploy/gcp/vendorverdict-backup.service" /etc/systemd/system/vendorverdict-backup.service
    install -m 0644 "${APP_DIR}/deploy/gcp/vendorverdict-backup.timer" /etc/systemd/system/vendorverdict-backup.timer
  fi

  if [ -f "${APP_DIR}/deploy/gcp/vendorverdict-monitor.service" ]; then
    install -m 0644 "${APP_DIR}/deploy/gcp/vendorverdict-monitor.service" /etc/systemd/system/vendorverdict-monitor.service
    install -m 0644 "${APP_DIR}/deploy/gcp/vendorverdict-monitor.timer" /etc/systemd/system/vendorverdict-monitor.timer
  fi

  systemctl daemon-reload
  systemctl enable vendorverdict.service
  systemctl enable --now vendorverdict-backup.timer >/dev/null 2>&1 || true
  systemctl enable --now vendorverdict-monitor.timer >/dev/null 2>&1 || true
}

restart_and_wait() {
  log "Restarting VendorVerdict"
  systemctl restart vendorverdict.service

  log "Waiting for local health: ${HEALTH_URL}"
  for attempt in $(seq 1 "${HEALTH_ATTEMPTS}"); do
    if curl -fsS --max-time 10 "${HEALTH_URL}" >/tmp/vendorverdict-deploy-health.json 2>/tmp/vendorverdict-deploy-health.err; then
      log "Local health passed on attempt ${attempt}"
      cat /tmp/vendorverdict-deploy-health.json
      printf '\n'
      return 0
    fi
    sleep "${HEALTH_SLEEP_SECONDS}"
  done

  systemctl status vendorverdict.service --no-pager -l || true
  journalctl -u vendorverdict.service -n 120 --no-pager || true
  fail "VendorVerdict did not pass local health check"
}

check_public_health() {
  if [ -z "${PUBLIC_HEALTH_URL:-}" ]; then
    log "No VENDORVERDICT_PUBLIC_URL configured; skipping public health check"
    return 0
  fi

  log "Checking public health: ${PUBLIC_HEALTH_URL}"
  curl -fsS --max-time 15 "${PUBLIC_HEALTH_URL}" >/tmp/vendorverdict-deploy-public-health.json
  cat /tmp/vendorverdict-deploy-public-health.json
  printf '\n'
}

run_monitor_once() {
  if [ "${RUN_MONITOR}" != "1" ]; then
    log "Skipping monitor run because VENDORVERDICT_DEPLOY_RUN_MONITOR=${RUN_MONITOR}"
    return 0
  fi

  if systemctl list-unit-files vendorverdict-monitor.service >/dev/null 2>&1; then
    log "Running production monitor once"
    if ! systemctl start vendorverdict-monitor.service; then
      journalctl -u vendorverdict-monitor.service -n 120 --no-pager || true
      fail "Production monitor failed after deploy"
    fi
    journalctl -u vendorverdict-monitor.service -n 40 --no-pager || true
  else
    log "Monitor service not installed; skipping monitor run"
  fi
}

print_summary() {
  log "Deployment finished successfully"
  systemctl status vendorverdict.service --no-pager -l || true
  printf '\nUseful checks:\n'
  printf '  curl -i http://127.0.0.1:8080/health\n'
  printf '  curl -i https://vendorverdict.docoply.com/health\n'
  printf '  sudo /opt/vendorverdict/scripts/status_vendorverdict.sh\n'
  printf '  sudo journalctl -u vendorverdict -n 100 --no-pager\n'
}

main() {
  require_root
  safe_path_guard
  require_command git
  require_command rsync
  require_command curl
  require_command python3
  require_command systemctl

  load_env_if_valid
  ensure_repo
  update_repo
  ensure_user_and_dirs
  run_pre_deploy_backup
  sync_code_preserving_runtime
  ensure_venv_and_install
  install_runtime_scripts
  install_systemd_units
  restart_and_wait
  check_public_health
  run_monitor_once
  print_summary
}

main "$@"
