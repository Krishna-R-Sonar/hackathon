"""
Acceptance test suite for Idempotency, Transient Retry, and Audit Logging.
"""

import pytest
from order_service.models import OrderItem, OrderStatus
from order_service.errors import InventoryUnavailableError
from order_service.storage import InMemoryStorage
from order_service.service import OrderService


def test_idempotent_duplicate_submission():
    storage = InMemoryStorage()
    service = OrderService(storage=storage)

    items = [OrderItem(product_id="prod_laptop", quantity=1, unit_price=1200.0)]
    idemp_key = "idemp_test_key_001"

    # First request
    order1 = service.create_order(customer_id="cust_1", items=items, idempotency_key=idemp_key)
    completed1 = service.process_order(order1.id)
    assert completed1.status == OrderStatus.COMPLETED
    assert storage.get_stock("prod_laptop") == 9

    # Second request with exact same idempotency_key
    order2 = service.create_order(customer_id="cust_1", items=items, idempotency_key=idemp_key)
    # Must return the cached completed order
    assert order2.id == completed1.id
    assert order2.status == OrderStatus.COMPLETED

    # Inventory must NOT have been deducted a second time
    assert storage.get_stock("prod_laptop") == 9


def test_transient_lock_retry_success():
    storage = InMemoryStorage()
    # Configure 2 transient lock failures before success
    storage.configure_transient_failures("prod_laptop", failures_before_success=2)
    service = OrderService(storage=storage, initial_retry_delay=0.01, backoff_factor=1.5, max_retries=3)

    items = [OrderItem(product_id="prod_laptop", quantity=1, unit_price=1200.0)]
    order = service.create_order(customer_id="cust_2", items=items)
    
    completed = service.process_order(order.id)
    assert completed.status == OrderStatus.COMPLETED
    assert storage.get_stock("prod_laptop") == 9

    # Check audit log for RETRIED status
    statuses_logged = [entry.to_status for entry in completed.audit_log]
    assert "CREATED" in statuses_logged
    assert "RETRIED" in statuses_logged
    assert "COMPLETED" in statuses_logged


def test_transient_lock_retry_exhaustion():
    storage = InMemoryStorage()
    # Configure 5 transient lock failures (exceeds max_retries of 3)
    storage.configure_transient_failures("prod_laptop", failures_before_success=5)
    service = OrderService(storage=storage, initial_retry_delay=0.01, backoff_factor=1.5, max_retries=3)

    items = [OrderItem(product_id="prod_laptop", quantity=1, unit_price=1200.0)]
    order = service.create_order(customer_id="cust_3", items=items)

    with pytest.raises(InventoryUnavailableError) as exc_info:
        service.process_order(order.id)

    assert exc_info.value.is_transient is True
    # Stock must remain unaffected (rolled back)
    assert storage.get_stock("prod_laptop") == 10
    failed_order = service.get_order(order.id)
    assert failed_order.status == OrderStatus.FAILED


def test_permanent_insufficient_stock_no_retry():
    storage = InMemoryStorage()
    service = OrderService(storage=storage)

    # Request 100 laptops (stock is 10) -> permanent failure
    items = [OrderItem(product_id="prod_laptop", quantity=100, unit_price=1200.0)]
    order = service.create_order(customer_id="cust_4", items=items)

    with pytest.raises(InventoryUnavailableError) as exc_info:
        service.process_order(order.id)

    assert exc_info.value.is_transient is False
    failed_order = service.get_order(order.id)
    assert failed_order.status == OrderStatus.FAILED
