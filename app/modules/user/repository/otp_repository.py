from app.core.database import RedisRepository
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from app.modules.user.models import Otp
from typing import Optional
from app.core.database.redis.redis_repository import RedisRepository
from datetime import datetime, timedelta
import secrets

from redis.exceptions import RedisError

__all__ = ["OtpRedisRepository", "OtpRepositoryDb", "OtpFallbackRepository"]


class OtpRedisRepository:
    """
    Handles storing/retrieving/deleting OTP codes in Redis, keyed by phone number.
    Expiry is handled by Redis TTL (set via RedisRepository's default_ttl).
    """

    def __init__(self, redis_repository: RedisRepository):
        self.redis_repository = redis_repository

    def save_otp(self, phone_number: str, otp_code: str) -> bool:
        return self.redis_repository.set(phone_number, otp_code)

    def get_otp(self, phone_number: str) -> Optional[str]:
        return self.redis_repository.get(phone_number)

    def delete_otp(self, phone_number: str) -> bool:
        return self.redis_repository.delete(phone_number)

    def exists(self, phone_number: str) -> bool:
        return self.redis_repository.exists(phone_number)


class OtpRepositoryDb:
    """Handles OTP persistence in Postgres (fallback store when Redis is down)."""

    def __init__(self, db: Session):
        self.db = db

    def save_otp(self, phone_number: str, otp_code: str, expires_at: datetime) -> Otp:
        otp = Otp(
            phone_number=phone_number,
            otp_code=otp_code,
            is_used=False,
            expires_at=expires_at,
        )
        self.db.add(otp)
        self.db.flush()
        return otp

    def get_active_otp(self, phone_number: str) -> Optional[Otp]:
        stmt = (
            select(Otp)
            .where(
                Otp.phone_number == phone_number,
                Otp.is_used.is_(False),
                Otp.expires_at > datetime.now(),
            )
            .order_by(Otp.created_at.desc())
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_valid_otp(self, phone_number: str, otp_code: str) -> Optional[Otp]:
        stmt = (
            select(Otp)
            .where(
                Otp.phone_number == phone_number,
                Otp.otp_code == otp_code,
                Otp.is_used.is_(False),
                Otp.expires_at > datetime.now(),
            )
            .order_by(Otp.created_at.desc())
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def mark_otp_used(self, otp_id: int) -> None:
        stmt = update(Otp).where(Otp.id == otp_id).values(is_used=True)
        self.db.execute(stmt)


class OtpFallbackRepository:
    """Tries Redis first for OTPs; falls back to Postgres if Redis is down."""

    def __init__(self, redis_repo: OtpRedisRepository, db_repo: OtpRepositoryDb, default_expiry_seconds: int = 300):
        self.redis_repo = redis_repo
        self.db_repo = db_repo
        self.default_expiry_seconds = default_expiry_seconds

    def save_otp(self, phone_number: str, code: str, expires_at: Optional[datetime] = None) -> None:
        try:
            self.redis_repo.save_otp(phone_number, code)
        except RedisError:
            if expires_at is None:
                expires_at = datetime.now() + timedelta(seconds=self.default_expiry_seconds)
            self.db_repo.save_otp(phone_number, code, expires_at=expires_at)

    def get_otp(self, phone_number: str) -> Optional[str]:
        try:
            return self.redis_repo.get_otp(phone_number)
        except RedisError:
            otp = self.db_repo.get_active_otp(phone_number)
            return otp.otp_code if otp else None

    def exists(self, phone_number: str) -> bool:
        try:
            return self.redis_repo.exists(phone_number)
        except RedisError:
            return self.db_repo.get_active_otp(phone_number) is not None

    def verify_and_consume(self, phone_number: str, code: str) -> bool:
        try:
            stored_code = self.redis_repo.get_otp(phone_number)
        except RedisError:
            otp = self.db_repo.get_valid_otp(phone_number, code)
            if otp is None:
                return False
            self.db_repo.mark_otp_used(otp.id)
            return True

        if stored_code is None:
            return False
        if secrets.compare_digest(stored_code.strip(), code.strip()):
            self.redis_repo.delete_otp(phone_number)
            return True
        return False
