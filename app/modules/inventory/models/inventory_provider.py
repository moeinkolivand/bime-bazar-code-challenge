import enum
from sqlalchemy import String, Boolean, Enum, JSON
from sqlalchemy.orm import mapped_column, Mapped

from app.core.utils.base_model import BaseModel

__all__ = ["InventoryProvider", "ProviderType"]


class ProviderType(str, enum.Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class InventoryProvider(BaseModel):
    __tablename__ = "inventory_providers"

    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    provider_type: Mapped[ProviderType] = mapped_column(Enum(ProviderType), nullable=False)
    capabilities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    credentials_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
