# Azure Container Apps deployment

Azure Container Apps is the recommended sponsor-aligned deployment target for keeping VendorVerdict online after the hackathon. It runs VendorVerdict as a containerized background-style service while Azure handles infrastructure management, logs, secrets, and revisions.

## Prerequisites

- Azure subscription
- Azure CLI
- Docker
- The same private `AGENT_SEED` used for the Agentverse profile

## Build and push image with Azure Container Registry

```bash
az login
az group create --name vendorverdict-rg --location uksouth
az acr create --resource-group vendorverdict-rg --name vendorverdictacr --sku Basic
az acr login --name vendorverdictacr

docker build -t vendorverdictacr.azurecr.io/vendorverdict:latest .
docker push vendorverdictacr.azurecr.io/vendorverdict:latest
```

## Create Container Apps environment

```bash
az containerapp env create \
  --name vendorverdict-env \
  --resource-group vendorverdict-rg \
  --location uksouth
```

## Deploy VendorVerdict

Set secrets and environment variables. Do not hardcode the seed in source control.

```bash
az containerapp create \
  --name vendorverdict \
  --resource-group vendorverdict-rg \
  --environment vendorverdict-env \
  --image vendorverdictacr.azurecr.io/vendorverdict:latest \
  --target-port 8001 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 1 \
  --secrets agent-seed=PASTE_PRIVATE_AGENT_SEED_HERE \
  --env-vars \
    AGENT_NAME=vendorverdict \
    AGENT_PORT=8001 \
    AGENT_SEED=secretref:agent-seed \
    VENDORVERDICT_LIVE_EVIDENCE=1 \
    VENDORVERDICT_PAYMENT_ENABLED=1 \
    VENDORVERDICT_PREMIUM_PRICE_FET=0.05 \
    FET_USE_TESTNET=true \
    VENDORVERDICT_PAYMENT_DEMO_MODE=1
```

Use `min-replicas 1` so the uAgent stays online instead of scaling to zero.

## Logs

```bash
az containerapp logs show \
  --name vendorverdict \
  --resource-group vendorverdict-rg \
  --follow
```

Look for:

```text
Starting mailbox client for https://agentverse.ai
Manifest published successfully: AgentChatProtocol
Manifest published successfully: AgentPaymentProtocol
Agent registration status updated to active
```

## Update deployment

```bash
docker build -t vendorverdictacr.azurecr.io/vendorverdict:latest .
docker push vendorverdictacr.azurecr.io/vendorverdict:latest
az containerapp update \
  --name vendorverdict \
  --resource-group vendorverdict-rg \
  --image vendorverdictacr.azurecr.io/vendorverdict:latest
```
