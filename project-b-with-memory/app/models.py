"""
Pydantic schemas and domain models for EventRoute.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DeliveryStatus(str, Enum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    RETRYING = "RETRYING"
    FAILED = "FAILED"


class WebhookIngestRequest(BaseModel):
    topic: str = Field(..., description="Event topic or event type, e.g. payment.success")
    payload: Dict[str, Any] = Field(..., description="Raw JSON event data")
    idempotency_key: Optional[str] = Field(None, description="Optional key to prevent duplicate delivery")


class WebhookDeliveryLog(BaseModel):
    id: str
    event_id: str
    source_id: str
    topic: str
    destination_url: str
    status: DeliveryStatus
    attempts: int
    last_http_status: Optional[int] = None
    response_body: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RoutingSubscription(BaseModel):
    id: str
    topic_pattern: str
    destination_url: str
    enabled: bool = True
