"""
Order Service core business logic.
"""

import uuid
from typing import List, Optional
from order_service.models import Order, OrderItem, OrderStatus, AuditLogEntry
from order_service.errors import InventoryUnavailableError, OrderNotFoundError
from order_service.storage import InMemoryStorage


class OrderService:
    def __init__(self, storage: Optional[InMemoryStorage] = None):
        self.storage = storage or InMemoryStorage()

    def create_order(
        self,
        customer_id: str,
        items: List[OrderItem],
        idempotency_key: Optional[str] = None,
    ) -> Order:
        """Initializes a new order in CREATED status."""
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
        """Processes order: reserves inventory and marks as COMPLETED."""
        order = self.storage.get_order(order_id)
        if order.status != OrderStatus.CREATED:
            return order

        # Reserve inventory for each item
        reserved_items = []
        try:
            for item in order.items:
                self.storage.reserve_stock(item.product_id, item.quantity)
                reserved_items.append(item)
            
            self._transition(order, OrderStatus.INVENTORY_RESERVED, "All item stock successfully reserved")
            self._transition(order, OrderStatus.COMPLETED, "Payment confirmed and order completed")
            self.storage.save_order(order)
            return order

        except InventoryUnavailableError as e:
            # Rollback already reserved stock
            for item in reserved_items:
                self.storage.release_stock(item.product_id, item.quantity)
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
