"""
Baseline test suite for Order Service.
"""

import pytest
from order_service.models import OrderItem, OrderStatus
from order_service.errors import InventoryUnavailableError, OrderNotFoundError
from order_service.storage import InMemoryStorage
from order_service.service import OrderService


def test_create_and_complete_order():
    storage = InMemoryStorage()
    service = OrderService(storage=storage)

    items = [
        OrderItem(product_id="prod_laptop", quantity=2, unit_price=1200.0),
        OrderItem(product_id="prod_mouse", quantity=1, unit_price=25.0),
    ]

    order = service.create_order(customer_id="cust_101", items=items)
    assert order.status == OrderStatus.CREATED
    assert order.total_amount == 2425.0
    assert len(order.audit_log) == 1
    assert order.audit_log[0].to_status == "CREATED"

    completed = service.process_order(order.id)
    assert completed.status == OrderStatus.COMPLETED
    assert storage.get_stock("prod_laptop") == 8
    assert storage.get_stock("prod_mouse") == 49


def test_order_rollback_on_insufficient_stock():
    storage = InMemoryStorage()
    service = OrderService(storage=storage)

    items = [
        OrderItem(product_id="prod_laptop", quantity=1, unit_price=1200.0),
        OrderItem(product_id="prod_mouse", quantity=999, unit_price=25.0), # Too many
    ]

    order = service.create_order(customer_id="cust_102", items=items)
    with pytest.raises(InventoryUnavailableError):
        service.process_order(order.id)

    # Laptop stock must be rolled back
    assert storage.get_stock("prod_laptop") == 10
    failed_order = service.get_order(order.id)
    assert failed_order.status == OrderStatus.FAILED


def test_order_not_found():
    service = OrderService()
    with pytest.raises(OrderNotFoundError):
        service.get_order("nonexistent_id")
