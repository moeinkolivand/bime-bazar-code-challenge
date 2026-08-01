__all__ = ["OrderServiceError", "ReservationNotConfirmedError", "OrderAlreadyExistsError", "OrderNotFoundError"]


class OrderServiceError(Exception):
    pass


class ReservationNotConfirmedError(OrderServiceError):
    def __init__(self, reservation_id: int):
        self.reservation_id = reservation_id
        super().__init__(f"Reservation {reservation_id} is not confirmed; cannot create order")


class OrderAlreadyExistsError(OrderServiceError):
    def __init__(self, reservation_id: int, order_id: int):
        self.reservation_id = reservation_id
        self.order_id = order_id
        super().__init__(f"Order {order_id} already exists for reservation {reservation_id}")


class OrderNotFoundError(OrderServiceError):
    def __init__(self, order_id: int):
        self.order_id = order_id
        super().__init__(f"Order {order_id} not found")
