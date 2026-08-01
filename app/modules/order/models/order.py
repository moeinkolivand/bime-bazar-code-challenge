import enum
from sqlalchemy import Integer, Enum
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.utils.base_model import BaseModel

__all__ = ["Order", "OrderStatus"]


class OrderStatus(str, enum.Enum):
    CREATED = "created"
    COMPLETED = "completed"
    FAILED = "failed"


class Order(BaseModel):
    __tablename__ = "orders"

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    reservation_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False, default=OrderStatus.CREATED)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")