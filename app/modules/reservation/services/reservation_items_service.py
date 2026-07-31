from app.modules.reservation.models.reservation import Reservation
from app.modules.reservation.models.reservation_item import (
    ReservationItem,
    ReservationItemStatus,
)

from app.modules.reservation.dtoes.reservation_request_dto import ReservationItemRequest
from app.modules.reservation.public_api.public_inventory_api_interface import InventoryPublicApiInterface
from app.modules.reservation.repositories.reservation_repository import ReservationRepository


class ReservationItemReserver:
    def __init__(
        self, reservation_repo: ReservationRepository, inventory_port: InventoryPublicApiInterface
    ):
        self.reservation_repo = reservation_repo
        self.inventory_port = inventory_port

    def reserve(
        self, reservation: Reservation, item_request: ReservationItemRequest
    ) -> ReservationItem:
        item = self.reservation_repo.add_item(
            reservation_id=reservation.id,
            product_inventory_id=item_request.product_inventory_id,
            sku=item_request.sku,
            quantity=item_request.quantity,
            status=ReservationItemStatus.PENDING,
        )

        held = self.inventory_port.hold_stock(
            item_request.product_inventory_id, item_request.quantity
        )
        if not held:
            item.status = ReservationItemStatus.FAILED
            return item

        outcome = self.inventory_port.reserve_upstream(
            item_request.product_inventory_id,
            item_request.sku,
            item_request.quantity,
            str(item.id),
        )
        if not outcome.success:
            self.inventory_port.release_stock(
                item_request.product_inventory_id, item_request.quantity
            )
            item.status = ReservationItemStatus.FAILED
            return item

        item.provider_reservation_ref = outcome.provider_reservation_ref
        item.status = ReservationItemStatus.HELD
        return item
