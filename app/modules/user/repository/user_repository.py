from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, update, func
from typing import Optional
from app.modules.user.models import Otp, User


class UserRepository:
    """Handles all database operations for Users and Otps."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_phone(self, phone_number: str) -> Optional[User]:
        """Fetch a user by phone number."""
        stmt = select(User).where(User.phone_number == phone_number)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Fetch a user by ID."""
        stmt = select(User).where(User.id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_user(self, phone_number: str) -> User:
        """Create a new user (only phone number for now)."""
        user = User(phone_number=phone_number, is_active=True)
        self.db.add(user)
        self.db.flush()
        return user

    def update_last_login(self, user_id: int) -> None:
        """Update the last_login_at timestamp."""
        stmt = update(User).where(User.id == user_id).values(last_login_at=func.now())
        self.db.execute(stmt)

    def save_otp(self, phone_number: str, otp_code: str) -> Otp:
        """Store an Otp in the database (fallback for Redis)."""
        otp = Otp(phone_number=phone_number, otp_code=otp_code, is_used=False)
        self.db.add(otp)
        self.db.flush()
        return otp

    def get_valid_otp(self, phone_number: str, otp_code: str) -> Optional[Otp]:
        """
        Fetch an unused, non-expired Otp for verification.
        Used only if Redis is down (fallback).
        """
        stmt = (
            select(Otp)
            .where(
                Otp.phone_number == phone_number,
                Otp.otp_code == otp_code,
                Otp.is_used.is_(True),
                Otp.expires_at > datetime.now(),
            )
            .order_by(Otp.created_at.desc())
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def mark_otp_used(self, otp_id: int) -> None:
        """Mark an Otp as used to prevent replay attacks."""
        stmt = update(Otp).where(Otp.id == otp_id).values(is_used=True)
        self.db.execute(stmt)
