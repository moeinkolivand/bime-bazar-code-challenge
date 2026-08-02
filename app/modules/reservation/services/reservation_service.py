from datetime import datetime, timedelta
from typing import Optional

from app.modules.reservation.dtoes.reservation_request_dto import ReservationItemRequest
from app.modules.reservation.exceptions.reservation_exceptions import (
    ReservationConcurrencyConflictError,
    ReservationConfirmationIncompleteError,
    ReservationFailedError,
    ReservationNotFoundError,
    ReservationNotPendingError,
    ReservationIdempotencyConflictError,
)
from app.modules.reservation.models.reservation import Reservation, ReservationStatus
from app.modules.reservation.models.reservation_item import ReservationItemStatus
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
        self,
        user_id: int,
        items: list[ReservationItemRequest],
        client_idempotency_key: str,
    ) -> Reservation:
        existing = self.reservation_repo.find_by_client_idempotency_key(
            user_id, client_idempotency_key
        )
        if existing:
            return existing

        reservation = self.reservation_repo.create(
            user_id=user_id,
            client_idempotency_key=client_idempotency_key,
            expires_at=datetime.now() + timedelta(seconds=self.reservation_ttl_seconds),
            status=ReservationStatus.CREATING,
        )

        reserved_items = []
        try:
            for item_req in items:
                item = self.item_reserver.reserve_local(reservation, item_req)
                reserved_items.append(item)
        except Exception:
            self.reservation_repo.rollback()
            raise ReservationFailedError(
                reservation_id=reservation.id,
                failed_skus=[it.sku for it in items],
            )

        reservation.status = ReservationStatus.PENDING_LOCAL
        self.reservation_repo.flush()
        self.reservation_repo.commit()

        any_failure = False
        for item in reserved_items:
            self.item_reserver.reserve_upstream_and_update(item, client_idempotency_key)
            if item.status == ReservationItemStatus.FAILED:
                any_failure = True

        if any_failure:
            self._release_all_held_items(reserved_items)
            with self.reservation_repo.transaction():
                res = self.reservation_repo.get_by_id(reservation.id)
                if res:
                    res.status = ReservationStatus.CANCELLED
                    res.cancelled_at = datetime.now()
                    self.reservation_repo.flush()
            raise ReservationFailedError(
                reservation_id=reservation.id,
                failed_skus=[
                    it.sku
                    for it in reserved_items
                    if it.status == ReservationItemStatus.FAILED
                ],
            )

        with self.reservation_repo.transaction():
            res = self.reservation_repo.get_by_id(reservation.id)
            res.status = ReservationStatus.PENDING
            self.reservation_repo.flush()

        return reservation

    def _release_all_held_items(self, items: list) -> None:
        """Release local and (if any) upstream holds for items still HELD or HELD_LOCAL."""
        for item in items:
            if item.status in (
                ReservationItemStatus.HELD,
                ReservationItemStatus.HELD_LOCAL,
            ):
                try:
                    self.inventory_port.release_stock(
                        item.product_inventory_id, item.quantity
                    )
                    if item.provider_reservation_ref:
                        self.inventory_port.release_upstream(
                            item.product_inventory_id,
                            item.provider_reservation_ref,
                        )
                except Exception:
                    # Log and continue; we don't want a single release failure
                    # to stop the others. Items that can't be released remain
                    # in a dangling state for later reconciliation.
                    pass
                finally:
                    item.status = ReservationItemStatus.RELEASED
        self.reservation_repo.flush()

    def confirm_reservation(self, reservation_id: int) -> Reservation:
        reservation = self.reservation_repo.get_by_id(reservation_id)
        if reservation is None:
            raise ReservationNotFoundError(reservation_id)
        if reservation.status not in (
            ReservationStatus.PENDING,
            ReservationStatus.PENDING_LOCAL,
            ReservationStatus.CONFIRMING,
        ):
            raise ReservationNotPendingError(reservation_id)

        reservation = self.reservation_repo.lock_and_transition(
            reservation_id,
            (
                ReservationStatus.PENDING,
                ReservationStatus.PENDING_LOCAL,
                ReservationStatus.CONFIRMING,
            ),
            ReservationStatus.CONFIRMING,
        )
        if reservation is None:
            raise ReservationConcurrencyConflictError(reservation_id)
        self.reservation_repo.commit()
        self.reservation_repo.db.refresh(reservation)

        all_confirmed = True
        for item in reservation.items:
            if item.status != ReservationItemStatus.HELD:
                all_confirmed = False
                continue

            with self.reservation_repo.transaction():
                item = self.reservation_repo.get_item_by_id(item.id)

                if item.provider_reservation_ref is not None:
                    try:
                        ok = self.inventory_port.confirm_upstream(
                            item.product_inventory_id,
                            item.provider_reservation_ref,
                            str(item.id),
                        )
                    except Exception:
                        ok = False
                    if not ok:
                        all_confirmed = False
                        continue
                else:
                    try:
                        ok = self.inventory_port.revalidate_stock(
                            item.product_inventory_id, item.sku, item.quantity
                        )
                    except Exception:
                        ok = False
                    if not ok:
                        try:
                            self.inventory_port.release_stock(
                                item.product_inventory_id, item.quantity
                            )
                        except Exception:
                            pass
                        item.status = ReservationItemStatus.FAILED
                        all_confirmed = False
                        continue

                try:
                    self.inventory_port.consume_stock(
                        item.product_inventory_id, item.quantity
                    )
                    item.status = ReservationItemStatus.CONFIRMED
                except Exception:
                    all_confirmed = False

                self.reservation_repo.flush()

        with self.reservation_repo.transaction():
            extra = {"confirmed_at": datetime.now()} if all_confirmed else {}
            reservation = self.reservation_repo.lock_and_transition(
                reservation_id,
                (ReservationStatus.CONFIRMING,),
                ReservationStatus.CONFIRMED,
                **extra,
            )
            if reservation is None:
                raise ReservationConcurrencyConflictError(reservation_id)

        if not all_confirmed:
            raise ReservationConfirmationIncompleteError(reservation_id)

        return reservation

    def cancel_reservation(self, reservation_id: int) -> Reservation:
        reservation = self.reservation_repo.get_by_id(reservation_id)
        if reservation is None:
            raise ReservationNotFoundError(reservation_id)
        if reservation.status not in (
            ReservationStatus.PENDING,
            ReservationStatus.PENDING_LOCAL,
        ):
            raise ReservationNotPendingError(reservation_id)
        for item in reservation.items:
            if item.status not in (
                ReservationItemStatus.HELD,
                ReservationItemStatus.HELD_LOCAL,
            ):
                continue

            try:
                self.inventory_port.release_stock(
                    item.product_inventory_id, item.quantity
                )
            except Exception:
                pass  # log

            try:
                if item.provider_reservation_ref:
                    self.inventory_port.release_upstream(
                        item.product_inventory_id,
                        item.provider_reservation_ref,
                    )
            except Exception:
                pass

            item.status = ReservationItemStatus.RELEASED

        reservation = self.reservation_repo.lock_and_transition(
            reservation_id,
            (ReservationStatus.PENDING, ReservationStatus.PENDING_LOCAL),
            ReservationStatus.CANCELLED,
            cancelled_at=datetime.now(),
        )
        if reservation is None:
            raise ReservationConcurrencyConflictError(reservation_id)

        self.reservation_repo.flush()
        return reservation

    def expire_reservations(self) -> list[Reservation]:
        expired = self.reservation_repo.find_expired_and_lock()
        processed = []

        for reservation in expired:
            for item in reservation.items:
                if item.status not in (
                    ReservationItemStatus.HELD,
                    ReservationItemStatus.HELD_LOCAL,
                ):
                    continue
                try:
                    self.inventory_port.release_stock(
                        item.product_inventory_id, item.quantity
                    )
                    if item.provider_reservation_ref:
                        self.inventory_port.release_upstream(
                            item.product_inventory_id, item.provider_reservation_ref
                        )
                except Exception:
                    pass  # log; leave for reconciliation, same policy as cancel_reservation
                finally:
                    item.status = ReservationItemStatus.RELEASED

            updated = self.reservation_repo.lock_and_transition(
                reservation.id,
                (ReservationStatus.PENDING, ReservationStatus.PENDING_LOCAL),
                ReservationStatus.EXPIRED,
            )
            if updated is not None:
                processed.append(updated)

            self.reservation_repo.flush()
            self.reservation_repo.commit()

        return processed
