"""
Custom domain exceptions for Order Service.
"""

class OrderServiceError(Exception):
    """Base exception for all order service errors."""
    pass


class InventoryUnavailableError(OrderServiceError):
    """Raised when inventory cannot be reserved due to stock lock contention or insufficient items."""
    def __init__(self, message: str, is_transient: bool = True):
        super().__init__(message)
        self.is_transient = is_transient


class InsufficientFundsError(OrderServiceError):
    """Raised when payment fails due to insufficient funds."""
    pass


class OrderNotFoundError(OrderServiceError):
    """Raised when an order ID does not exist."""
    pass


class DuplicateOrderError(OrderServiceError):
    """Raised when an idempotency violation occurs."""
    pass
