from sqlalchemy import String
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.utils.base_model import BaseModel

__all__ = ["Product"]


class Product(BaseModel):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String, nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
