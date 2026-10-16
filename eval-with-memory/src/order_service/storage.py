"""
In-memory transactional storage and repository for products and orders with idempotency cache.
"""

from datetime import datetime, timezone
from typing import Dict, Optional
from order_service.models import Order, OrderStatus
from order_service.errors import OrderNotFoundError, InventoryUnavailableError


class InMemoryStorage:
    """Thread-safe transactional in-memory store for orders and inventory."""

    def __init__(self):
        self.orders: Dict[str, Order] = {}
        # product_id -> available_stock
        self.inventory: Dict[str, int] = {
            "prod_laptop": 10,
            "prod_mouse": 50,
            "prod_keyboard": 30,
        }
        # Simulated lock contention tracking: product_id -> transient_failure_count
        self.transient_lock_counters: Dict[str, int] = {}
        # idempotency_key -> {"order_id": str, "timestamp": float}
        self.idempotency_cache: Dict[str, Dict[str, any]] = {}

    def get_stock(self, product_id: str) -> int:
        return self.inventory.get(product_id, 0)

    def set_stock(self, product_id: str, quantity: int) -> None:
        self.inventory[product_id] = quantity

    def configure_transient_failures(self, product_id: str, failures_before_success: int) -> None:
        """Configures simulated lock contention for testing retry behavior."""
        self.transient_lock_counters[product_id] = failures_before_success

    def reserve_stock(self, product_id: str, quantity: int) -> None:
        """Reserves stock or raises InventoryUnavailableError (transient or permanent)."""
        # Check transient simulated lock contention
        if self.transient_lock_counters.get(product_id, 0) > 0:
            self.transient_lock_counters[product_id] -= 1
            raise InventoryUnavailableError(
                f"Transient lock contention on product {product_id}. Retry recommended.",
                is_transient=True,
            )

        current = self.inventory.get(product_id, 0)
        if current < quantity:
            raise InventoryUnavailableError(
                f"Insufficient stock for product {product_id}: requested {quantity}, available {current}",
                is_transient=False,
            )
        self.inventory[product_id] = current - quantity

    def release_stock(self, product_id: str, quantity: int) -> None:
        """Releases stock back on order failure or cancellation."""
        self.inventory[product_id] = self.inventory.get(product_id, 0) + quantity

    def save_order(self, order: Order) -> None:
        self.orders[order.id] = order

    def get_order(self, order_id: str) -> Order:
        if order_id not in self.orders:
            raise OrderNotFoundError(f"Order {order_id} not found")
        return self.orders[order_id]

    def get_idempotent_order(self, idempotency_key: str, ttl_seconds: int = 600) -> Optional[Order]:
        """Retrieves cached completed order if within TTL."""
        entry = self.idempotency_cache.get(idempotency_key)
        if not entry:
            return None
        now = datetime.now(timezone.utc).timestamp()
        if now - entry["timestamp"] > ttl_seconds:
            return None
        order = self.orders.get(entry["order_id"])
        if order and order.status == OrderStatus.COMPLETED:
            return order
        return None

    def record_idempotent_order(self, idempotency_key: str, order_id: str) -> None:
        now = datetime.now(timezone.utc).timestamp()
        self.idempotency_cache[idempotency_key] = {
            "order_id": order_id,
            "timestamp": now,
        }
