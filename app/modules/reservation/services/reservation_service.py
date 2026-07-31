from datetime import datetime, timedelta
from app.modules.reservation.models.reservation import Reservation, ReservationStatus
from app.modules.reservation.models.reservation_item import ReservationItemStatus
from app.modules.reservation.dtoes.reservation_request_dto import ReservationItemRequest
from app.modules.reservation.exceptions.reservation_exceptions import (
    ReservationConfirmationIncompleteError,
    ReservationFailedError,
    ReservationNotFoundError,
    ReservationNotPendingError,
)
from app.modules.reservation.public_api.public_inventory_api_interface import (
    InventoryPublicApiInterface,
)
from app.modules.reservation.repositories.reservation_repository import (
    ReservationRepository,
)
from app.modules.reservation.services.reservation_items_service import (
    ReservationItemReserver,
)


class ReservationService:
    def __init__(
        self,
        reservation_repo: ReservationRepository,
        inventory_port: InventoryPublicApiInterface,
        item_reserver: ReservationItemReserver,
        reservation_ttl_seconds: int = 300,
    ):
        self.reservation_repo = reservation_repo
        self.inventory_port = inventory_port
        self.item_reserver = item_reserver
        self.reservation_ttl_seconds = reservation_ttl_seconds

    def create_reservation(
        self, user_id: int, items: list[ReservationItemRequest]
    ) -> Reservation:
        reservation = self.reservation_repo.create(
            user_id=user_id,
            expires_at=datetime.now() + timedelta(seconds=self.reservation_ttl_seconds),
        )

        reserved_items = [
            self.item_reserver.reserve(reservation, item_request)
            for item_request in items
        ]

        failed_items = [
            item
            for item in reserved_items
            if item.status == ReservationItemStatus.FAILED
        ]

        if failed_items:
            # All-or-nothing: roll back every item that DID succeed, since the
            # checkout as a whole cannot proceed with a missing product.
            self._rollback_partial_reservation(reserved_items)
            reservation.status = ReservationStatus.CANCELLED
            reservation.cancelled_at = datetime.now()
            self.reservation_repo.flush()

            failed_skus = [item.sku for item in failed_items]
            raise ReservationFailedError(
                reservation_id=reservation.id, failed_skus=failed_skus
            )

        reservation.status = ReservationStatus.PENDING
        self.reservation_repo.flush()
        return reservation

    def _rollback_partial_reservation(self, reserved_items) -> None:
        for item in reserved_items:
            if item.status == ReservationItemStatus.HELD:
                self.inventory_port.release_stock(
                    item.product_inventory_id, item.quantity
                )
                self.inventory_port.release_upstream(
                    item.product_inventory_id, item.provider_reservation_ref
                )
                item.status = ReservationItemStatus.RELEASED

    def confirm_reservation(self, reservation_id: int) -> Reservation:
        reservation = self.reservation_repo.get_by_id(reservation_id)
        if reservation is None:
            raise ReservationNotFoundError(reservation_id)
        if reservation.status != ReservationStatus.PENDING:
            raise ReservationNotPendingError(reservation_id)

        all_confirmed = True

        for item in reservation.items:
            if item.status != ReservationItemStatus.HELD:
                all_confirmed = False
                continue

            if item.provider_reservation_ref is not None:
                confirmed = self.inventory_port.confirm_upstream(
                    item.product_inventory_id,
                    item.provider_reservation_ref,
                    str(item.id),
                )
                if not confirmed:
                    # provider confirm failed mid-flow — do NOT mark FAILED, do NOT release.
                    # We already told the user payment succeeded; the local hold stays as-is
                    # while a reconciliation job retries the confirm using the same idempotency key.
                    all_confirmed = False
                    continue
            else:
                if not self.inventory_port.revalidate_stock(
                    item.product_inventory_id, item.sku, item.quantity
                ):
                    self.inventory_port.release_stock(
                        item.product_inventory_id, item.quantity
                    )
                    item.status = ReservationItemStatus.FAILED
                    all_confirmed = False
                    continue

            self.inventory_port.consume_stock(item.product_inventory_id, item.quantity)
            item.status = ReservationItemStatus.CONFIRMED

        reservation.status = (
            ReservationStatus.CONFIRMED if all_confirmed else ReservationStatus.PENDING
        )
        if all_confirmed:
            reservation.confirmed_at = datetime.now()

        self.reservation_repo.flush()

        if not all_confirmed:
            raise ReservationConfirmationIncompleteError(reservation_id)
        return reservation

    def cancel_reservation(self, reservation_id: int) -> Reservation:
        reservation = self.reservation_repo.get_by_id(reservation_id)
        if reservation is None:
            raise ReservationNotFoundError(reservation_id)

        for item in reservation.items:
            if item.status != ReservationItemStatus.HELD:
                continue
            self.inventory_port.release_stock(item.product_inventory_id, item.quantity)
            self.inventory_port.release_upstream(
                item.product_inventory_id, item.provider_reservation_ref
            )
            item.status = ReservationItemStatus.RELEASED

        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_at = datetime.now()
        self.reservation_repo.flush()
        return reservation
