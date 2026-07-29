from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean

from app.core.utils.base_model import BaseModel

__all__ = [
    "User"
]

class User(BaseModel):
    __tablename__ = "users"

    phone_number: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
