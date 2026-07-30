from datetime import datetime
from sqlalchemy import ForeignKey, Integer, DateTime, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.modules.inventory.models.inventory_provider import InventoryProvider

from app.core.utils.base_model import BaseModel

__all__ = ["ProductInventory"]



class ProductInventory(BaseModel):
    __tablename__ = "product_inventories"
    __table_args__ = (
        UniqueConstraint("product_id", "provider_id", name="uq_product_provider"),
    )

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    provider_id: Mapped[int] = mapped_column(ForeignKey("inventory_providers.id"), nullable=False)
    qty_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider: Mapped["InventoryProvider"] = relationship()