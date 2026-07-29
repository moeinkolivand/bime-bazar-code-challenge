from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.core.utils.base_model import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    phone_number = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
