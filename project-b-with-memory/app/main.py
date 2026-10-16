"""
FastAPI application entry point for EventRoute Webhook Gateway.
"""

import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.dispatcher import WebhookDispatcher
from app.models import DeliveryStatus, WebhookDeliveryLog, WebhookIngestRequest, RoutingSubscription
from app.security import verify_signature
from app.storage import SQLiteStorage

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
DB_PATH = os.environ.get("EVENTROUTE_DB_PATH", "eventroute.db")

app = FastAPI(
    title="EventRoute Webhook Gateway",
    version="0.1.0",
    description="Reliable Webhook Ingestion, Routing, and Audit Gateway with HMAC validation and automatic retry."
)

# In-memory configuration of registered webhook sources: source_id -> secret
SOURCE_SECRETS: Dict[str, str] = {
    "src_stripe": "whsec_stripe_test_secret_12345",
    "src_github": "whsec_github_test_secret_67890",
    "src_custom": "whsec_custom_secret_abcde",
}

storage = SQLiteStorage(db_path=DB_PATH)
dispatcher = WebhookDispatcher(storage=storage)

# Ensure sample subscriptions exist for testing
storage.add_subscription(RoutingSubscription(
    id="sub_payment_processor",
    topic_pattern="payment.*",
    destination_url="https://api.example.com/internal/payments",
))
storage.add_subscription(RoutingSubscription(
    id="sub_audit_collector",
    topic_pattern="*",
    destination_url="https://api.example.com/audit/events",
))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=FileResponse)
async def serve_dashboard():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse({"message": "EventRoute API Gateway running."})
    return FileResponse(index_file)


@app.post("/api/v1/webhooks/ingest/{source_id}", status_code=status.HTTP_202_ACCEPTED)
async def ingest_webhook(
    source_id: str,
    request: Request,
    x_signature_256: Optional[str] = Header(None, alias="X-Signature-256"),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Ingests and validates raw webhook event:
    1. Authenticates HMAC-SHA256 signature against source secret.
    2. Checks idempotency cache to prevent duplicate ingestion.
    3. Matches subscriptions and triggers async dispatch.
    """
    raw_body = await request.body()
    secret = SOURCE_SECRETS.get(source_id)

    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook source '{source_id}' is not registered."
        )

    # 1. Verify Signature
    if not verify_signature(raw_body, x_signature_256, secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC-SHA256 signature header 'X-Signature-256'."
        )

    # Parse JSON
    try:
        data = await request.json()
        topic = data.get("topic", "default.event")
        payload = data.get("payload", data)
        idemp_key = x_idempotency_key or data.get("idempotency_key")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {str(e)}"
        )

    # 2. Check Idempotency
    event_id = f"evt_{uuid.uuid4().hex[:10]}"
    if idemp_key:
        is_new = storage.save_event(event_id, source_id, topic, payload, idemp_key)
        if not is_new:
            cached_event = storage.get_event_by_idempotency_key(idemp_key)
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "cached_idempotent",
                    "message": "Event was previously ingested and processed.",
                    "event": cached_event,
                }
            )
    else:
        storage.save_event(event_id, source_id, topic, payload, None)

    # 3. Match Routing Subscriptions and Dispatch
    subs = storage.get_matching_subscriptions(topic)
    dispatched_logs = []
    for sub in subs:
        delivery_id = f"del_{uuid.uuid4().hex[:10]}"
        log = await dispatcher.dispatch(
            delivery_id=delivery_id,
            event_id=event_id,
            source_id=source_id,
            topic=topic,
            destination_url=sub.destination_url,
            payload=payload,
        )
        dispatched_logs.append(log.model_dump())

    return {
        "status": "accepted",
        "event_id": event_id,
        "matched_subscriptions": len(subs),
        "deliveries": dispatched_logs,
    }


@app.get("/api/v1/deliveries", response_model=List[WebhookDeliveryLog])
async def list_deliveries(limit: int = 50):
    """Returns recent delivery logs for the audit dashboard."""
    return storage.get_delivery_logs(limit=limit)


@app.post("/api/v1/deliveries/{delivery_id}/redeliver")
async def redeliver_event(delivery_id: str):
    """Manually triggers redelivery of an event from the dashboard."""
    log = storage.get_delivery_log_by_id(delivery_id)
    if not log:
        raise HTTPException(status_code=404, detail="Delivery log not found")

    new_log = await dispatcher.dispatch(
        delivery_id=log.id,
        event_id=log.event_id,
        source_id=log.source_id,
        topic=log.topic,
        destination_url=log.destination_url,
        payload={"redelivered": True, "original_event_id": log.event_id},
    )
    return {"message": "Redelivery initiated", "delivery": new_log.model_dump()}


@app.get("/api/v1/health")
async def healthcheck():
    return {"status": "healthy", "service": "EventRoute Webhook Gateway"}
