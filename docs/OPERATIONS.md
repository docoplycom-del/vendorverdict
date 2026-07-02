# VendorVerdict operations plan

VendorVerdict is designed to continue operating after the hackathon as an always-on ASI:One-compatible uAgent.

## Operating goals

- Preserve the same Agentverse identity by keeping the same private `AGENT_SEED`.
- Run continuously on a cloud VM, Azure Container Apps, or another managed container/background-worker service.
- Use Agentverse Mailbox for message routing and resilience.
- Auto-restart on crash or host reboot.
- Keep secrets out of Git and in environment variables or managed cloud secrets.
- Run CI tests before every deployment.
- Keep fallback evidence enabled so vendor website failures do not break the workflow.

## Health checks

Run the deterministic local health check:

```bash
vendorverdict --health
```

This verifies the parser, specialist-agent workflow, fallback evidence path, scoring, recommendation, and email rendering without relying on live vendor websites.

For a live-source health check:

```bash
vendorverdict --health --live-health
```

Use the deterministic version for container/process health. Use live health manually during operational checks.

## systemd deployment

Copy `deploy/systemd/vendorverdict.service.example` to `/etc/systemd/system/vendorverdict.service` and create `/etc/vendorverdict.env` from `deploy/systemd/vendorverdict.env.example`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable vendorverdict
sudo systemctl start vendorverdict
sudo systemctl status vendorverdict
sudo journalctl -u vendorverdict -f
```

## Docker deployment

```bash
docker build -t vendorverdict:latest .
docker run --env-file .env -p 8001:8001 --restart unless-stopped vendorverdict:latest
```

Or:

```bash
docker compose up -d --build
docker compose logs -f
```

## Runbook

- If ASI:One cannot reach the agent, check that the same `AGENT_SEED` is deployed and the agent address matches Agentverse.
- If live evidence fails, confirm fallback mode still passes with `vendorverdict --health`.
- If payment verification fails, keep the free workflow available and check `VENDORVERDICT_PAYMENT_DEMO_MODE` / FET network settings.
- If the process crashes, systemd or Docker restart policy should bring it back.
