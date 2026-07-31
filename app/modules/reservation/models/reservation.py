import enum
from datetime import datetime
from sqlalchemy import Integer, DateTime, Enum
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.utils.base_model import BaseModel

__all__ = ["Reservation", "ReservationStatus"]


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Reservation(BaseModel):
    __tablename__ = "reservations"

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), nullable=False, default=ReservationStatus.PENDING
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    items: Mapped[list["ReservationItem"]] = relationship(back_populates="reservation")