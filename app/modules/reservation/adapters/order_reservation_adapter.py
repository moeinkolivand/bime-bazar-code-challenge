from app.modules.order.public_api.order_reservation_public_api import (
    ReservationPort, ConfirmedReservation, ConfirmedReservationItem,
)
from app.modules.reservation.repositories.reservation_repository import ReservationRepository
from app.modules.reservation.models.reservation import ReservationStatus
from app.modules.reservation.models.reservation_item import ReservationItemStatus

__all__ = ["OrderReservationAdapter"]


class OrderReservationAdapter(ReservationPort):
    def __init__(self, reservation_repo: ReservationRepository):
        self.reservation_repo = reservation_repo

    def get_confirmed_reservation(self, reservation_id: int) -> ConfirmedReservation | None:
        reservation = self.reservation_repo.get_by_id(reservation_id)
        if reservation is None or reservation.status != ReservationStatus.CONFIRMED:
            return None

        items = [
            ConfirmedReservationItem(
                product_inventory_id=item.product_inventory_id,
                sku=item.sku,
                quantity=item.quantity,
            )
            for item in reservation.items
            if item.status == ReservationItemStatus.CONFIRMED
        ]

        return ConfirmedReservation(
            reservation_id=reservation.id, user_id=reservation.user_id, items=items
        )