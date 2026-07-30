from pydantic import BaseModel, Field

__all__ = ["UserLoginResponseDto", "UserVerficationResponseDto"]


class UserLoginResponseDto(BaseModel):
    otp_code: str = Field(min_length=6, max_length=6)


class UserVerficationResponseDto(BaseModel):
    access_token: str
