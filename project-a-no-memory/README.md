# EventRoute Webhook Gateway (Condition A — Without Memory)

A reliable webhook ingestion, routing, and audit gateway with HMAC-SHA256 signature verification, exponential backoff retries, and an interactive administrative dashboard.

## Features
- **Inbound Ingestion & Security**: `POST /api/v1/webhooks/ingest/{source_id}` verifies `X-Signature-256` using constant-time HMAC comparison (`hmac.compare_digest`).
- **Idempotency Prevention**: Checks `X-Idempotency-Key` or payload hash against SQLite storage to eliminate duplicate dispatches.
- **Dynamic Routing**: Dispatches payloads to target URLs based on topic wildcard subscriptions.
- **Reliable Dispatcher**: Retries transient 5xx / timeout errors up to 3 times with exponential backoff (`initial_delay=0.1s`, `factor=2.0`); aborts immediately on 4xx client errors.
- **Interactive Web Dashboard**: Single-page administrative UI served directly at `/` for live delivery feeds and one-click manual redelivery.

## Architecture
- **Backend**: FastAPI + Uvicorn + Pydantic v2 + HTTPX (Async)
- **Database**: SQLite with WAL mode (`PRAGMA journal_mode=WAL`)
- **Frontend**: Lightweight vanilla HTML5/CSS/JavaScript dashboard embedded in static assets.

## Quick Start
```powershell
# 1. Install dependencies
pip install -e .

# 2. Run test suite
pytest -v

# 3. Launch the server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Navigate to `http://127.0.0.1:8000` to view the live dashboard.
