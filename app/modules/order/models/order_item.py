# modules/order/models/order_item.py
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.utils.base_model import BaseModel

__all__ = ["OrderItem"]


class OrderItem(BaseModel):
    """Immutable snapshot of a reservation item at confirm time."""

    __tablename__ = "order_items"

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_inventory_id: Mapped[int] = mapped_column(
        ForeignKey("product_inventories.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
