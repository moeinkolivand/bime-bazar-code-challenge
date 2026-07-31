import enum
from sqlalchemy import Integer, Enum, ForeignKey, String
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.utils.base_model import BaseModel

__all__ = ["ReservationItem", "ReservationItemStatus"]


class ReservationItemStatus(str, enum.Enum):
    PENDING = "pending"
    HELD = "held"
    FAILED = "failed"
    RELEASED = "released"
    CONFIRMED = "confirmed"


class ReservationItem(BaseModel):
    __tablename__ = "reservation_items"
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product_inventories.id"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReservationItemStatus] = mapped_column(
        Enum(ReservationItemStatus),
        nullable=False,
        default=ReservationItemStatus.PENDING,
    )
    provider_reservation_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    reservation: Mapped["Reservation"] = relationship(back_populates="items")
