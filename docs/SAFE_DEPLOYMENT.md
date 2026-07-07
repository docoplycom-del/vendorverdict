# Safe production deployment

Use the safe deploy script for every VendorVerdict production update on the Google Cloud VM.

It prevents the two deployment mistakes that caused downtime:

1. deleting `/opt/vendorverdict/.venv` during `rsync --delete`
2. copying operational scripts without executable permissions

## Standard deployment command

SSH into the VM, then run:

```bash
cd /tmp/vendorverdict
git pull origin main
sudo scripts/deploy_gcp_vm.sh
```

The script will:

- validate `/etc/vendorverdict/vendorverdict.env`
- pull the latest `main` branch
- run a pre-deploy backup when the backup service exists
- sync code into `/opt/vendorverdict` while preserving `.venv`
- recreate `.venv` if it is missing
- install/update the Python package
- reinstall operational scripts with `0755` permissions
- reinstall systemd unit files
- restart `vendorverdict.service`
- wait for `http://127.0.0.1:8080/health`
- check public `/health` if `VENDORVERDICT_PUBLIC_URL` is configured
- run the production monitor once

## Never use plain rsync

Do not run:

```bash
sudo rsync -a --delete /tmp/vendorverdict/ /opt/vendorverdict/
```

That can delete the production virtual environment.

The safe script uses:

```bash
rsync -a --delete \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  /tmp/vendorverdict/ /opt/vendorverdict/
```

## Useful options

Skip the pre-deploy backup:

```bash
sudo VENDORVERDICT_DEPLOY_RUN_BACKUP=0 scripts/deploy_gcp_vm.sh
```

Skip the post-deploy monitor run:

```bash
sudo VENDORVERDICT_DEPLOY_RUN_MONITOR=0 scripts/deploy_gcp_vm.sh
```

Use another branch:

```bash
sudo GIT_BRANCH=staging scripts/deploy_gcp_vm.sh
```

Use another repo checkout:

```bash
sudo REPO_DIR=/tmp/vendorverdict scripts/deploy_gcp_vm.sh
```

## If deployment fails

Check the app service:

```bash
sudo systemctl status vendorverdict --no-pager -l
sudo journalctl -u vendorverdict -n 120 --no-pager
```

Check the monitor:

```bash
sudo journalctl -u vendorverdict-monitor -n 120 --no-pager
```

Run the status command:

```bash
sudo /opt/vendorverdict/scripts/status_vendorverdict.sh
```

## Post-deploy checks

```bash
curl -i http://127.0.0.1:8080/health
curl -i https://vendorverdict.docoply.com/health
curl -i https://vendorverdict.docoply.com/
curl -i https://vendorverdict.docoply.com/dashboard
```

Expected:

- local `/health` returns `200 OK`
- public `/health` returns `200 OK`
- homepage returns `200 OK`
- dashboard redirects to login with `303 See Other`
