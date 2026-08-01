import enum
from sqlalchemy import Integer, Enum, ForeignKey, String
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.utils.base_model import BaseModel

__all__ = ["ReservationItem", "ReservationItemStatus"]


class ReservationItemStatus(enum.Enum):
    HELD_LOCAL = "HELD_LOCAL"  # local stock reserved, not yet upstream
    HELD = "HELD"  # both local + upstream hold succeeded
    FAILED = "FAILED"  # reservation attempt failed for this item
    CONFIRMED = "CONFIRMED"  # payment confirmed, stock consumed
    RELEASED = "RELEASED"  # hold returned to available


class ReservationItem(BaseModel):
    __tablename__ = "reservation_items"
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id"), nullable=False
    )
    product_inventory_id: Mapped[int] = mapped_column(
        ForeignKey("product_inventories.id"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReservationItemStatus] = mapped_column(
        Enum(ReservationItemStatus),
        nullable=False,
        default=ReservationItemStatus.HELD_LOCAL,
    )
    provider_reservation_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    reservation: Mapped["Reservation"] = relationship(back_populates="items")
