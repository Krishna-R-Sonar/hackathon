"""
Order Service core business logic with idempotency and exponential backoff retry.
"""

import time
import uuid
from typing import List, Optional
from order_service.models import Order, OrderItem, OrderStatus, AuditLogEntry
from order_service.errors import InventoryUnavailableError, OrderNotFoundError
from order_service.storage import InMemoryStorage


class OrderService:
    def __init__(
        self,
        storage: Optional[InMemoryStorage] = None,
        initial_retry_delay: float = 0.05,
        backoff_factor: float = 2.0,
        max_retries: int = 3,
    ):
        self.storage = storage or InMemoryStorage()
        self.initial_retry_delay = initial_retry_delay
        self.backoff_factor = backoff_factor
        self.max_retries = max_retries

    def create_order(
        self,
        customer_id: str,
        items: List[OrderItem],
        idempotency_key: Optional[str] = None,
    ) -> Order:
        """Initializes a new order in CREATED status or returns idempotent cached order."""
        if idempotency_key:
            cached = self.storage.get_idempotent_order(idempotency_key)
            if cached:
                return cached

        total = sum(item.quantity * item.unit_price for item in items)
        order_id = f"ord_{uuid.uuid4().hex[:8]}"
        order = Order(
            id=order_id,
            customer_id=customer_id,
            items=items,
            total_amount=total,
            status=OrderStatus.CREATED,
            idempotency_key=idempotency_key,
        )
        self._record_audit(order, from_status=None, to_status=OrderStatus.CREATED, message="Order created")
        self.storage.save_order(order)
        return order

    def process_order(self, order_id: str) -> Order:
        """Processes order: reserves inventory with exponential backoff on transient errors."""
        order = self.storage.get_order(order_id)
        if order.status == OrderStatus.COMPLETED:
            return order

        # Check idempotency cache if present
        if order.idempotency_key:
            cached = self.storage.get_idempotent_order(order.idempotency_key)
            if cached and cached.id != order.id:
                return cached

        attempt = 0
        delay = self.initial_retry_delay
        retried_successfully = False

        while True:
            reserved_items = []
            try:
                for item in order.items:
                    self.storage.reserve_stock(item.product_id, item.quantity)
                    reserved_items.append(item)

                if retried_successfully:
                    self._transition(order, OrderStatus.RETRIED, f"Transient lock recovered after retry attempt {attempt}")

                self._transition(order, OrderStatus.INVENTORY_RESERVED, "All item stock successfully reserved")
                self._transition(order, OrderStatus.COMPLETED, "Payment confirmed and order completed")

                if order.idempotency_key:
                    self.storage.record_idempotent_order(order.idempotency_key, order.id)

                self.storage.save_order(order)
                return order

            except InventoryUnavailableError as e:
                # Rollback already reserved stock in this attempt
                for item in reserved_items:
                    self.storage.release_stock(item.product_id, item.quantity)

                if e.is_transient and attempt < self.max_retries:
                    attempt += 1
                    retried_successfully = True
                    time.sleep(delay)
                    delay *= self.backoff_factor
                    continue

                # Permanent failure or retries exhausted
                self._transition(order, OrderStatus.FAILED, f"Order failed: {str(e)}")
                self.storage.save_order(order)
                raise

    def get_order(self, order_id: str) -> Order:
        return self.storage.get_order(order_id)

    def _transition(self, order: Order, new_status: OrderStatus, message: str) -> None:
        old_status = order.status
        order.status = new_status
        self._record_audit(order, from_status=old_status.value, to_status=new_status.value, message=message)

    def _record_audit(self, order: Order, from_status: Optional[str], to_status: str, message: str) -> None:
        entry = AuditLogEntry(
            from_status=from_status,
            to_status=to_status,
            message=message,
        )
        order.audit_log.append(entry)
