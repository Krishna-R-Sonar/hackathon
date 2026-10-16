"""
Automated tests for webhook ingestion, HMAC security, and idempotency.
"""

import json
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app, SOURCE_SECRETS
from app.security import compute_signature


@pytest.mark.asyncio
async def test_ingest_valid_hmac_signature():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"topic": "payment.success", "amount": 100, "currency": "USD"}
        payload_bytes = json.dumps(payload).encode("utf-8")
        secret = SOURCE_SECRETS["src_stripe"]
        sig = compute_signature(payload_bytes, secret)

        resp = await client.post(
            "/api/v1/webhooks/ingest/src_stripe",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Signature-256": f"sha256={sig}",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"
        assert "event_id" in data


@pytest.mark.asyncio
async def test_ingest_invalid_hmac_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"topic": "payment.success", "amount": 100}
        payload_bytes = json.dumps(payload).encode("utf-8")

        resp = await client.post(
            "/api/v1/webhooks/ingest/src_stripe",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Signature-256": "sha256=invalid_hex_digest_12345",
            },
        )
        assert resp.status_code == 401
        assert "Invalid HMAC" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_ingest_unregistered_source():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/webhooks/ingest/unknown_source_999",
            json={"topic": "test"},
            headers={"X-Signature-256": "sha256=abcdef"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ingest_idempotency_cache():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"topic": "user.signup", "user_id": "u_999"}
        payload_bytes = json.dumps(payload).encode("utf-8")
        secret = SOURCE_SECRETS["src_github"]
        sig = compute_signature(payload_bytes, secret)
        import uuid
        idemp_key = f"idemp_test_user_signup_{uuid.uuid4().hex}"

        # 1st call
        resp1 = await client.post(
            "/api/v1/webhooks/ingest/src_github",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Signature-256": f"sha256={sig}",
                "X-Idempotency-Key": idemp_key,
            },
        )
        assert resp1.status_code == 202

        # 2nd call with same idempotency key
        resp2 = await client.post(
            "/api/v1/webhooks/ingest/src_github",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Signature-256": f"sha256={sig}",
                "X-Idempotency-Key": idemp_key,
            },
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "cached_idempotent"
