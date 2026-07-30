from pydantic import BaseModel, Field

__all__ = [
    "UserLoginDto",
    "OtpVerificationDto"
]

class UserLoginDto(BaseModel):
    phone_number: str = Field(min_length=11, max_length=11, description="user phone number", examples=["09332823692"])


class OtpVerificationDto(BaseModel):
    phone_number: str = Field(min_length=11, max_length=11, description="user phone number", examples=["09332823692"])
    otp_code: str = Field(min_length=6, max_length=6, description="6-digit OTP", examples=["123456"])
