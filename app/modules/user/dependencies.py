from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.conf.config import Settings, get_settings
from app.core.database import get_db_postgres, RedisRepository
from app.core.database.redis.redis_client import get_redis_dependency
from app.core.security.jwt_service import JwtService
from app.modules.user.repository.user_repository import UserRepository
from app.modules.user.repository.otp_repository import (
    OtpFallbackRepository,
    OtpRedisRepository,
    OtpRepositoryDb,
)
from app.modules.user.services.otp_service import OTPGenerator, OtpService
from app.modules.user.services.user_service import UserService


def get_user_repository(db: Session = Depends(get_db_postgres)) -> UserRepository:
    return UserRepository(db)


def get_otp_redis_repository(
    config: Settings = Depends(get_settings),
) -> OtpRedisRepository:
    repo = RedisRepository(
        client=get_redis_dependency(),
        prefix="otp",
        default_ttl=config.OTP_EXPIRE_SECONDS,
    )
    return OtpRedisRepository(redis_repository=repo)


def get_otp_generator(config: Settings = Depends(get_settings)) -> OTPGenerator:
    return OTPGenerator(expiry_seconds=config.OTP_EXPIRE_SECONDS)


def get_otp_repository_db(db: Session = Depends(get_db_postgres)) -> OtpRepositoryDb:
    return OtpRepositoryDb(db)


def get_otp_fallback_repository(
    redis_repo: OtpRedisRepository = Depends(get_otp_redis_repository),
    db_repo: OtpRepositoryDb = Depends(get_otp_repository_db),
    settings: Settings = Depends(get_settings),
) -> OtpFallbackRepository:
    return OtpFallbackRepository(
        redis_repo=redis_repo,
        db_repo=db_repo,
        default_expiry_seconds=settings.OTP_EXPIRE_SECONDS,
    )


def get_otp_service(
    otp_repo: OtpFallbackRepository = Depends(get_otp_fallback_repository),
    otp_generator: OTPGenerator = Depends(get_otp_generator),
) -> OtpService:
    return OtpService(otp_repo=otp_repo, otp_generator=otp_generator)


def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository),
    otp_service: OtpService = Depends(get_otp_service),
    jwt_service: JwtService = Depends(JwtService),
) -> UserService:
    return UserService(user_repository, otp_service, jwt_service)
