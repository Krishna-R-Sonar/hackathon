"""
Automated tests for dashboard static assets, delivery audit log API, and manual redelivery.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app, storage
from app.models import DeliveryStatus, WebhookDeliveryLog


@pytest.mark.asyncio
async def test_dashboard_page_served():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "EventRoute Gateway" in resp.text
        assert "Live Delivery Feed" in resp.text


@pytest.mark.asyncio
async def test_list_deliveries_api():
    # Insert a dummy log
    log = WebhookDeliveryLog(
        id="del_test_audit_01",
        event_id="evt_audit_01",
        source_id="src_stripe",
        topic="invoice.paid",
        destination_url="https://api.example.com/dest",
        status=DeliveryStatus.DELIVERED,
        attempts=1,
        last_http_status=200,
    )
    storage.save_delivery_log(log)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/deliveries")
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        assert any(l["id"] == "del_test_audit_01" for l in logs)


@pytest.mark.asyncio
async def test_manual_redelivery():
    log = WebhookDeliveryLog(
        id="del_redeliver_test",
        event_id="evt_redeliver",
        source_id="src_stripe",
        topic="customer.updated",
        destination_url="https://api.example.com/dest",
        status=DeliveryStatus.FAILED,
        attempts=3,
        last_http_status=500,
    )
    storage.save_delivery_log(log)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/deliveries/del_redeliver_test/redeliver")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Redelivery initiated"
        assert "delivery" in data
