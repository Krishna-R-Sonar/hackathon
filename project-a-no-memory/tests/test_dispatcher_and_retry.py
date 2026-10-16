"""
Automated tests for async dispatcher, retry backoff, and failure recovery.
"""

import httpx
import pytest
from app.dispatcher import WebhookDispatcher
from app.models import DeliveryStatus
from app.storage import SQLiteStorage


@pytest.mark.asyncio
async def test_transient_503_retry_and_recovery(tmp_path):
    db_file = str(tmp_path / "test_disp.db")
    storage = SQLiteStorage(db_path=db_file)

    call_count = 0

    def mock_handler(request: httpx.Request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(status_code=503, text="Service Unavailable")
        return httpx.Response(status_code=200, text='{"success": true}')

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    dispatcher = WebhookDispatcher(
        storage=storage,
        initial_delay=0.01,
        backoff_factor=1.5,
        max_retries=3,
        http_client=mock_client,
    )

    log = await dispatcher.dispatch(
        delivery_id="del_transient_test",
        event_id="evt_01",
        source_id="src_stripe",
        topic="payment.charge",
        destination_url="https://api.example.com/dest",
        payload={"amount": 500},
    )

    assert log.status == DeliveryStatus.DELIVERED
    assert log.attempts == 3
    assert log.last_http_status == 200
    assert call_count == 3


@pytest.mark.asyncio
async def test_permanent_404_client_error_aborts_immediately(tmp_path):
    db_file = str(tmp_path / "test_perm.db")
    storage = SQLiteStorage(db_path=db_file)

    call_count = 0

    def mock_handler(request: httpx.Request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(status_code=404, text="Endpoint Not Found")

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    dispatcher = WebhookDispatcher(
        storage=storage,
        initial_delay=0.01,
        backoff_factor=1.5,
        max_retries=3,
        http_client=mock_client,
    )

    log = await dispatcher.dispatch(
        delivery_id="del_perm_test",
        event_id="evt_02",
        source_id="src_stripe",
        topic="order.created",
        destination_url="https://api.example.com/bad-endpoint",
        payload={"order_id": "ord_123"},
    )

    assert log.status == DeliveryStatus.FAILED
    assert log.attempts == 1
    assert log.last_http_status == 404
    assert call_count == 1  # Did NOT retry


@pytest.mark.asyncio
async def test_transient_failure_exhaustion(tmp_path):
    db_file = str(tmp_path / "test_exhaust.db")
    storage = SQLiteStorage(db_path=db_file)

    call_count = 0

    def mock_handler(request: httpx.Request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(status_code=500, text="Internal Server Error")

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    dispatcher = WebhookDispatcher(
        storage=storage,
        initial_delay=0.01,
        backoff_factor=1.5,
        max_retries=3,
        http_client=mock_client,
    )

    log = await dispatcher.dispatch(
        delivery_id="del_exhaust_test",
        event_id="evt_03",
        source_id="src_stripe",
        topic="order.refund",
        destination_url="https://api.example.com/failing",
        payload={"refund_id": "ref_99"},
    )

    assert log.status == DeliveryStatus.FAILED
    assert log.attempts == 3
    assert log.last_http_status == 500
    assert call_count == 3
