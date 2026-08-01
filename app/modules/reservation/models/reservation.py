import enum
from datetime import datetime
import uuid
from sqlalchemy import Integer, DateTime, Enum, String
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.utils.base_model import BaseModel

__all__ = ["Reservation", "ReservationStatus"]


class ReservationStatus(enum.Enum):
    CREATING = "CREATING"  # not yet fully reserved
    PENDING_LOCAL = "PENDING_LOCAL"  # local holds committed, upstream pending
    PENDING = "PENDING"  # fully held, waiting for payment
    CONFIRMING = "CONFIRMING"  # ← new: in-progress lock state
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


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
    client_idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, default=str(uuid.uuid4())
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
