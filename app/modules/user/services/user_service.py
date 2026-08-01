from typing import Optional
from app.core.security.jwt_service import JwtService
from app.modules.user.dtoes import UserLoginDto, OtpVerificationDto
from app.modules.user.dtoes.user_login_response import (
    UserLoginResponseDto,
    UserVerficationResponseDto,
)
from app.modules.user.models.user import User
from app.modules.user.repository.user_repository import UserRepository
from app.modules.user.services.otp_service import OtpService
from app.modules.user.exceptions.exception_handlers import *

__all__ = ["UserService"]


class UserService:

    def __init__(
        self,
        user_repository: UserRepository,
        otp_service: OtpService,
        jwt_service: JwtService,
    ):
        self.user_repository = user_repository
        self.otp_service = otp_service
        self.jwt_service = jwt_service

    def login(self, login_data: UserLoginDto) -> UserLoginResponseDto:
        if self.otp_service.has_active_otp(login_data.phone_number):
            print(self.otp_service.get_otp(login_data.phone_number))
            return UserLoginResponseDto(
                otp_code=self.otp_service.get_otp(login_data.phone_number)
            )
        if self.user_repository.get_by_phone(login_data.phone_number) is None:
            self.user_repository.create_user(login_data.phone_number)
        otp = self.otp_service.generate_otp(login_data.phone_number)
        return UserLoginResponseDto(otp_code=otp)

    def otp_verification(
        self, otp_data: OtpVerificationDto
    ) -> UserVerficationResponseDto:
        user: Optional[User] = self.user_repository.get_by_phone(otp_data.phone_number)
        if user is None:
            raise UserNotFoundError()
        otp_code: Optional[str] = self.otp_service.get_otp(otp_data.phone_number)
        if otp_code is None:
            raise OtpExpiredError()
        if not self.otp_service.verify_otp(otp_data.phone_number, otp_data.otp_code):
            raise InvalidOtpError()
        jwt_token = self.jwt_service.generate_access_token(user.id)
        return UserVerficationResponseDto(access_token=jwt_token)
