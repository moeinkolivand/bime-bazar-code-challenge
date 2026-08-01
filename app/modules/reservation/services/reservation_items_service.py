from app.modules.reservation.dtoes.reservation_request_dto import ReservationItemRequest
from app.modules.reservation.exceptions.reservation_exceptions import (
    ReservationItemLocalHoldFailed,
)
from app.modules.reservation.models.reservation import Reservation
from app.modules.reservation.models.reservation_item import (
    ReservationItem,
    ReservationItemStatus,
)
from app.modules.reservation.public_api.public_inventory_api_interface import (
    InventoryPublicApiInterface,
)
from app.modules.reservation.repositories.reservation_repository import (
    ReservationRepository,
)


class ReservationItemReserver:

    def __init__(
        self,
        reservation_repo: ReservationRepository,
        inventory_port: InventoryPublicApiInterface,
    ):
        self.reservation_repo = reservation_repo
        self.inventory_port = inventory_port

    def reserve_local(
        self,
        reservation: Reservation,
        item_request: ReservationItemRequest,
    ) -> ReservationItem:
        item = self.reservation_repo.add_item(
            reservation_id=reservation.id,
            product_inventory_id=item_request.product_inventory_id,
            sku=item_request.sku,
            quantity=item_request.quantity,
            status=ReservationItemStatus.HELD_LOCAL,
        )

        try:
            held = self.inventory_port.hold_stock(
                item_request.product_inventory_id, item_request.quantity
            )
        except Exception as e:
            item.status = ReservationItemStatus.FAILED
            raise ReservationItemLocalHoldFailed(
                reservation.id, item_request.sku, f"hold_stock threw exception {e}"
            )

        if not held:
            item.status = ReservationItemStatus.FAILED
            raise ReservationItemLocalHoldFailed(
                reservation_id=reservation.id,
                sku=item_request.sku,
                reason="insufficient stock",
            )

        return item

    def reserve_upstream_and_update(
        self, item: ReservationItem, client_idempotency_key: str
    ) -> None:
        if item.status != ReservationItemStatus.HELD_LOCAL:
            return

        try:
            outcome = self.inventory_port.reserve_upstream(
                item.product_inventory_id,
                item.sku,
                item.quantity,
                client_idempotency_key,
            )
        except Exception:
            outcome = None

        with self.reservation_repo.transaction():
            # re-fetch item inside the new transaction
            fresh_item = self.reservation_repo.get_item_by_id(item.id)
            if (
                fresh_item is None
                or fresh_item.status != ReservationItemStatus.HELD_LOCAL
            ):
                return  # something else changed it

            if outcome is not None and outcome.success:
                fresh_item.provider_reservation_ref = outcome.provider_reservation_ref
                fresh_item.status = ReservationItemStatus.HELD
            else:
                try:
                    self.inventory_port.release_stock(
                        fresh_item.product_inventory_id, fresh_item.quantity
                    )
                except Exception:
                    # If release fails we log and leave the item HELD_LOCAL
                    # for reconciliation. Better than leaking stock.
                    fresh_item.status = ReservationItemStatus.FAILED
                    # TODO: write compensation task for background retry
                else:
                    fresh_item.status = ReservationItemStatus.FAILED

            self.reservation_repo.flush()
