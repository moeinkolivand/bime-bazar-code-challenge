from fastapi import APIRouter, Depends, status

from app.modules.user.dependencies import get_user_service
from app.modules.user.dtoes.user_login_dto import OtpVerificationDto, UserLoginDto
from app.modules.user.dtoes.user_login_response import (
    UserLoginResponseDto,
    UserVerficationResponseDto,
)
from app.modules.user.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login", response_model=UserLoginResponseDto, status_code=status.HTTP_202_ACCEPTED
)
async def user_login(
    data: UserLoginDto, user_service: UserService = Depends(get_user_service)
) -> UserLoginResponseDto:
    return user_service.login(data)


@router.post(
    "/verify-otp",
    response_model=UserVerficationResponseDto,
    status_code=status.HTTP_200_OK,
)
async def user_verify_otp(
    data: OtpVerificationDto, user_service: UserService = Depends(get_user_service)
) -> UserVerficationResponseDto:
    return user_service.otp_verification(data)
