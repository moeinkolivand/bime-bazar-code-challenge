from sqlalchemy import Integer, String, Boolean
from sqlalchemy.orm import mapped_column, Mapped

from app.core.utils.base_model import BaseModel


__all__ = [
    "Otp"
]

class Otp(BaseModel):
    __tablename__ = "otps"

    otp_code: Mapped[str] = mapped_column(Integer, nullable=False)
    phone_number: Mapped[str] = mapped_column(String, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
