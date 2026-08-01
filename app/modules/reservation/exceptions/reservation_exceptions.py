__all__ = [
    "ReservationServiceError",
    "ReservationNotFoundError",
    "ReservationNotPendingError",
    "ReservationFailedError",
    "ReservationConfirmationIncompleteError",
    "InsufficientStockError",
]


class ReservationServiceError(Exception):
    """Base class for all reservation-related domain errors."""


class ReservationNotFoundError(ReservationServiceError):
    def __init__(self, reservation_id: int):
        self.reservation_id = reservation_id
        super().__init__(f"Reservation {reservation_id} not found")


class ReservationNotPendingError(ReservationServiceError):
    def __init__(self, reservation_id: int):
        self.reservation_id = reservation_id
        super().__init__(f"Reservation {reservation_id} is not pending")


class InsufficientStockError(ReservationServiceError):
    def __init__(self, product_inventory_id: int):
        self.product_inventory_id = product_inventory_id
        super().__init__(
            f"Insufficient stock for product inventory {product_inventory_id}"
        )


class ReservationFailedError(ReservationServiceError):
    """
    Raised when at least one item in a checkout could not be reserved.
    All previously-held items in the same reservation are released before
    this is raised — a reservation is all-or-nothing at creation time.
    """

    def __init__(self, reservation_id: int, failed_skus: list[str]):
        self.reservation_id = reservation_id
        self.failed_skus = failed_skus
        super().__init__(
            f"Reservation {reservation_id} failed: could not reserve {failed_skus}"
        )


class ReservationConfirmationIncompleteError(ReservationServiceError):
    """
    Raised when confirm_reservation() could not confirm every item —
    e.g. an upstream provider confirm call failed mid-flow, or a
    read-only provider's stock recheck came back insufficient.

    Unlike ReservationFailedError, this does NOT mean everything was
    rolled back: items that did confirm remain CONFIRMED, and the
    reservation stays PENDING pending reconciliation (retry of the
    failed confirm using the original idempotency key).
    """

    def __init__(self, reservation_id: int):
        self.reservation_id = reservation_id
        super().__init__(
            f"Reservation {reservation_id} could not be fully confirmed; "
            f"some items remain unconfirmed and will be retried via reconciliation"
        )


class InventoryNotFoundError(Exception):
    def __init__(self, product_inventory_id: int):
        self.product_inventory_id = product_inventory_id
        super().__init__(f"Inventory row not found for id={product_inventory_id}")


class InventoryInsufficientStockError(Exception):
    def __init__(self, product_inventory_id: int, requested: int, available: int):
        self.product_inventory_id = product_inventory_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for inventory {product_inventory_id}: "
            f"requested {requested}, available {available}"
        )


class ReservationIdempotencyConflictError(Exception):
    """
    Raised when a request with an idempotency key is retried but the original
    reservation is in a terminal or conflicting state, or when the requested
    items don't match the existing reservation.
    """

    def __init__(self, client_idempotency_key: str, existing_reservation_id: int):
        self.client_idempotency_key = client_idempotency_key
        self.existing_reservation_id = existing_reservation_id
        super().__init__(
            f"Idempotency conflict for key '{client_idempotency_key}'. "
            f"Existing reservation id={existing_reservation_id} is not in a valid state for retry."
        )


class ReservationConcurrencyConflictError(Exception):
    def __init__(self, reservation_id: int):
        self.reservation_id = reservation_id
        super().__init__(
            f"Reservation {reservation_id} was modified concurrently. Please retry."
        )

class ReservationItemLocalHoldFailed(Exception):
    """
    Raised when the local (in-DB) stock hold for a single reservation item
    could not be acquired — either because the optimistic version-guarded
    UPDATE affected 0 rows (insufficient stock or a concurrent writer won
    the race), or because hold_stock() itself raised an unexpected error.

    Raised from ReservationItemReserver.reserve_local(), inside the
    original create-reservation transaction, so the caller
    (ReservationService.create_reservation) can catch it, roll back the
    whole transaction, and treat the checkout as all-or-nothing.
    """

    def __init__(self, reservation_id: int, sku: str, reason: str):
        self.reservation_id = reservation_id
        self.sku = sku
        self.reason = reason
        super().__init__(
            f"Failed to hold local stock for sku '{sku}' in reservation {reservation_id}: {reason}"
        )
