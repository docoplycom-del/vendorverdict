FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENT_NAME=vendorverdict \
    AGENT_PORT=8001 \
    VENDORVERDICT_LIVE_EVIDENCE=1 \
    VENDORVERDICT_PAYMENT_ENABLED=1 \
    VENDORVERDICT_PREMIUM_PRICE_FET=0.05 \
    FET_USE_TESTNET=true \
    VENDORVERDICT_PAYMENT_DEMO_MODE=1 \
    VENDORVERDICT_API_HOST=0.0.0.0 \
    VENDORVERDICT_API_PORT=8080 \
    VENDORVERDICT_AUTH_ENABLED=0

WORKDIR /app

COPY pyproject.toml README.md requirements.txt ./
COPY src ./src
COPY tests ./tests

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir -e .

EXPOSE 8001 8080

HEALTHCHECK --interval=60s --timeout=20s --start-period=30s --retries=3 \
    CMD vendorverdict --health || exit 1

CMD ["python", "-m", "vendorverdict.agent"]
