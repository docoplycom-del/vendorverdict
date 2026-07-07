#!/usr/bin/env bash
set -euo pipefail

# Run this on the Google Compute Engine VM after SSHing in.
# It installs VendorVerdict as a systemd service bound to localhost:8080.
# Apache or another reverse proxy should expose it over HTTPS.

REPO_URL="${REPO_URL:-https://github.com/docoplycom-del/vendorverdict.git}"
APP_DIR="${APP_DIR:-/opt/vendorverdict}"
APP_USER="${APP_USER:-vendorverdict}"
ENV_DIR="${ENV_DIR:-/etc/vendorverdict}"
DATA_DIR="${DATA_DIR:-/var/lib/vendorverdict}"
LOG_DIR="${LOG_DIR:-/var/log/vendorverdict}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/vendorverdict}"

sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip apache2 sqlite3

if ! id "${APP_USER}" >/dev/null 2>&1; then
  sudo useradd --system --create-home --shell /usr/sbin/nologin "${APP_USER}"
fi

sudo mkdir -p "${DATA_DIR}/reports" "${LOG_DIR}" "${ENV_DIR}" "${BACKUP_DIR}"
sudo chown -R "${APP_USER}:www-data" "${DATA_DIR}" "${LOG_DIR}"
sudo chown -R root:root "${BACKUP_DIR}"
sudo chmod 750 "${DATA_DIR}" "${LOG_DIR}"
sudo chmod 700 "${BACKUP_DIR}"

if [ ! -d "${APP_DIR}/.git" ]; then
  sudo git clone "${REPO_URL}" "${APP_DIR}"
else
  sudo git -C "${APP_DIR}" pull --ff-only origin main
fi
sudo chown -R "${APP_USER}:www-data" "${APP_DIR}"

sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/.venv"
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/python" -m pip install -e "${APP_DIR}"

if [ ! -f "${ENV_DIR}/vendorverdict.env" ]; then
  sudo cp "${APP_DIR}/deploy/gcp/env.example" "${ENV_DIR}/vendorverdict.env"
  sudo chmod 640 "${ENV_DIR}/vendorverdict.env"
  sudo chown root:www-data "${ENV_DIR}/vendorverdict.env"
  echo "Created ${ENV_DIR}/vendorverdict.env. Edit it and set real secrets before public deployment."
fi

sudo chmod +x "${APP_DIR}/scripts/backup_vendorverdict.sh" "${APP_DIR}/scripts/restore_vendorverdict_backup.sh"
sudo cp "${APP_DIR}/deploy/gcp/vendorverdict.service" /etc/systemd/system/vendorverdict.service
sudo cp "${APP_DIR}/deploy/gcp/vendorverdict-backup.service" /etc/systemd/system/vendorverdict-backup.service
sudo cp "${APP_DIR}/deploy/gcp/vendorverdict-backup.timer" /etc/systemd/system/vendorverdict-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable vendorverdict
sudo systemctl enable --now vendorverdict-backup.timer
sudo systemctl restart vendorverdict
sudo systemctl status vendorverdict --no-pager
sudo systemctl status vendorverdict-backup.timer --no-pager

echo "VendorVerdict is running locally on the VM. Test with: curl http://127.0.0.1:8080/health"
echo "Backups are scheduled. Run one now with: sudo systemctl start vendorverdict-backup"
