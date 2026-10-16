"""
Domain models for Order Service.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    INVENTORY_RESERVED = "INVENTORY_RESERVED"
    PAYMENT_PROCESSED = "PAYMENT_PROCESSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRIED = "RETRIED"


class AuditLogEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    from_status: Optional[str] = None
    to_status: str
    message: str


class OrderItem(BaseModel):
    product_id: str
    quantity: int
    unit_price: float


class Order(BaseModel):
    id: str
    customer_id: str
    items: List[OrderItem]
    total_amount: float
    status: OrderStatus = OrderStatus.CREATED
    idempotency_key: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    audit_log: List[AuditLogEntry] = Field(default_factory=list)
