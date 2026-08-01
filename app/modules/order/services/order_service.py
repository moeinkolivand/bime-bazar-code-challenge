from app.modules.order.public_api.order_reservation_public_api import ReservationPort
from app.modules.order.repositories.order_repository import OrderRepository
from app.modules.order.models.order import Order, OrderStatus
from app.modules.order.exceptions.order_exceptions import (
    ReservationNotConfirmedError,
    OrderAlreadyExistsError,
    OrderNotFoundError,
)

__all__ = ["OrderService"]


class OrderService:
    def __init__(self, order_repo: OrderRepository, reservation_port: ReservationPort):
        self.order_repo = order_repo
        self.reservation_port = reservation_port

    def create_order_from_reservation(self, reservation_id: int) -> Order:
        existing = self.order_repo.get_by_reservation_id(reservation_id)
        if existing is not None:
            raise OrderAlreadyExistsError(reservation_id, existing.id)

        confirmed_reservation = self.reservation_port.get_confirmed_reservation(reservation_id)
        if confirmed_reservation is None:
            raise ReservationNotConfirmedError(reservation_id)

        order = self.order_repo.create(
            user_id=confirmed_reservation.user_id, reservation_id=reservation_id
        )

        for item in confirmed_reservation.items:
            self.order_repo.add_item(
                order_id=order.id,
                product_inventory_id=item.product_inventory_id,
                sku=item.sku,
                quantity=item.quantity,
            )

        order.status = OrderStatus.COMPLETED
        self.order_repo.flush()
        return order

    def get_order(self, order_id: int) -> Order:
        order = self.order_repo.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return order
