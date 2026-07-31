from datetime import datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
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

    def create(self, user_id: int, expires_at: datetime) -> Reservation:
        reservation = Reservation(
            user_id=user_id,
            status=ReservationStatus.PENDING,
            expires_at=expires_at,
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
            product_id=product_inventory_id,
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
        """Explicit flush point for services that mutate ORM objects in place
        (item.status = ..., reservation.status = ...) without going through
        a dedicated update method."""
        self.db.flush()


def get_reservation_repository(
    db: Session = Depends(get_db_postgres),
) -> ReservationRepository:
    return ReservationRepository(db)
