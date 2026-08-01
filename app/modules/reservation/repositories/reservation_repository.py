from datetime import datetime

from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session, SessionTransaction
from app.core.database import get_db_postgres
from app.modules.reservation.models.reservation import Reservation, ReservationStatus
from app.modules.reservation.models.reservation_item import (
    ReservationItem,
    ReservationItemStatus,
)

__all__ = ["ReservationRepository", "get_reservation_repository"]


class ReservationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: int,
        expires_at: datetime,
        client_idempotency_key: str,
        status: ReservationStatus = ReservationStatus.CREATING,
    ) -> Reservation:
        """Insert a new reservation row and return it."""
        reservation = Reservation(
            user_id=user_id,
            expires_at=expires_at,
            client_idempotency_key=client_idempotency_key,
            status=status,
        )
        self.db.add(reservation)
        self.db.flush()
        return reservation

    def get_by_id(self, reservation_id: int) -> Reservation | None:
        stmt = select(Reservation).where(Reservation.id == reservation_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_expired_pending(self, now: datetime) -> list[Reservation]:
        """Used by the background sweep job to release abandoned reservations."""
        stmt = select(Reservation).where(
            Reservation.status == ReservationStatus.PENDING,
            Reservation.expires_at <= now,
        )
        return list(self.db.execute(stmt).scalars().all())

    def add_item(
        self,
        reservation_id: int,
        product_inventory_id: int,
        sku: str,
        quantity: int,
        status: ReservationItemStatus,
    ) -> ReservationItem:
        item = ReservationItem(
            reservation_id=reservation_id,
            product_inventory_id=product_inventory_id,
            sku=sku,
            quantity=quantity,
            status=status,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def get_items_for_reservation(self, reservation_id: int) -> list[ReservationItem]:
        stmt = select(ReservationItem).where(
            ReservationItem.reservation_id == reservation_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def flush(self) -> None:
        self.db.flush()

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def transaction(self) -> SessionTransaction:
        return self.db.begin_nested()  # use savepoints

    def find_by_client_idempotency_key(self, user_id: int, key: str):
        return (
            self.db.query(Reservation)
            .filter_by(user_id=user_id, client_idempotency_key=key)
            .first()
        )

    def get_item_by_id(self, item_id: int):
        return self.db.query(ReservationItem).filter_by(id=item_id).first()

    def update_status_with_version(
        self,
        reservation_id: int,
        current_version: int,
        new_status: ReservationStatus,
        **extra_fields,
    ) -> bool:
        values = {"status": new_status, "version": current_version + 1, **extra_fields}
        stmt = (
            update(Reservation)
            .where(
                Reservation.id == reservation_id, Reservation.version == current_version
            )
            .values(**values)
        )
        result = self.db.execute(stmt)
        return result.rowcount == 1

    def find_expired_and_lock(self) -> list[Reservation]:
        now = datetime.now()
        stmt = (
            select(Reservation)
            .where(
                Reservation.status.in_(
                    [ReservationStatus.PENDING_LOCAL, ReservationStatus.PENDING]
                ),
                Reservation.expires_at <= now,
            )
            .with_for_update(skip_locked=True)
        )
        return list(self.db.execute(stmt).scalars().all())


def get_reservation_repository(
    db: Session = Depends(get_db_postgres),
) -> ReservationRepository:
    return ReservationRepository(db)
