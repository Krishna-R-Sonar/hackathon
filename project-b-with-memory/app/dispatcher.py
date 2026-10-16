"""
Asynchronous webhook dispatcher with exponential backoff retry.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import httpx
from app.models import DeliveryStatus, WebhookDeliveryLog
from app.storage import SQLiteStorage


class WebhookDispatcher:
    def __init__(
        self,
        storage: SQLiteStorage,
        initial_delay: float = 0.05,
        backoff_factor: float = 2.0,
        max_retries: int = 3,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.storage = storage
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_retries = max_retries
        self._custom_client = http_client

    async def dispatch(
        self,
        delivery_id: str,
        event_id: str,
        source_id: str,
        topic: str,
        destination_url: str,
        payload: Dict[str, Any],
    ) -> WebhookDeliveryLog:
        """
        Dispatches payload to destination URL.
        Retries transient failures (5xx, timeouts) with exponential backoff.
        Aborts immediately on permanent failures (4xx).
        """
        log = WebhookDeliveryLog(
            id=delivery_id,
            event_id=event_id,
            source_id=source_id,
            topic=topic,
            destination_url=destination_url,
            status=DeliveryStatus.PENDING,
            attempts=0,
        )
        self.storage.save_delivery_log(log)

        client = self._custom_client or httpx.AsyncClient(timeout=5.0)
        close_client = self._custom_client is None

        attempt = 0
        delay = self.initial_delay

        try:
            while attempt < self.max_retries:
                attempt += 1
                log.attempts = attempt
                now_iso = datetime.now(timezone.utc).isoformat()
                log.updated_at = now_iso

                try:
                    resp = await client.post(
                        destination_url,
                        json=payload,
                        headers={"X-Event-ID": event_id, "X-Event-Topic": topic},
                    )
                    log.last_http_status = resp.status_code
                    log.response_body = resp.text[:500]

                    if 200 <= resp.status_code < 300:
                        log.status = DeliveryStatus.DELIVERED
                        self.storage.save_delivery_log(log)
                        return log

                    if 400 <= resp.status_code < 500:
                        # Client error - permanent failure, do not retry
                        log.status = DeliveryStatus.FAILED
                        self.storage.save_delivery_log(log)
                        return log

                    # Server error (5xx) - transient failure, retry
                    if attempt < self.max_retries:
                        log.status = DeliveryStatus.RETRYING
                        self.storage.save_delivery_log(log)
                        await asyncio.sleep(delay)
                        delay *= self.backoff_factor
                    else:
                        log.status = DeliveryStatus.FAILED
                        self.storage.save_delivery_log(log)
                        return log

                except (httpx.RequestError, httpx.TimeoutException) as exc:
                    log.response_body = f"Network/Timeout error: {str(exc)}"
                    log.last_http_status = None
                    if attempt < self.max_retries:
                        log.status = DeliveryStatus.RETRYING
                        self.storage.save_delivery_log(log)
                        await asyncio.sleep(delay)
                        delay *= self.backoff_factor
                    else:
                        log.status = DeliveryStatus.FAILED
                        self.storage.save_delivery_log(log)
                        return log

            log.status = DeliveryStatus.FAILED
            self.storage.save_delivery_log(log)
            return log

        finally:
            if close_client:
                await client.aclose()
