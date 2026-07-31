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
        super().__init__(f"Insufficient stock for product inventory {product_inventory_id}")


class ReservationFailedError(ReservationServiceError):
    """
    Raised when at least one item in a checkout could not be reserved.
    All previously-held items in the same reservation are released before
    this is raised — a reservation is all-or-nothing at creation time.
    """

    def __init__(self, reservation_id: int, failed_skus: list[str]):
        self.reservation_id = reservation_id
        self.failed_skus = failed_skus
        super().__init__(f"Reservation {reservation_id} failed: could not reserve {failed_skus}")


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