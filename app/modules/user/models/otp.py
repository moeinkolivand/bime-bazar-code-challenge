from sqlalchemy import Column, Integer, String, Boolean

from app.core.utils.base_model import BaseModel


class Otp(BaseModel):
    __tablename__ = "otps"

    otp_code = Column(Integer, nullable=False)
    phone_number = Column(String, nullable=False)
    is_used = Column(Boolean, default=False)
