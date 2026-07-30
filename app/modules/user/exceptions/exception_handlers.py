from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.modules.user.exceptions.user_service_exceptions import (
    UserServiceError,
    UserNotFoundError,
    OtpExpiredError,
    InvalidOtpError,
)


def register_user_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UserNotFoundError)
    async def user_not_found_handler(request: Request, exc: UserNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(OtpExpiredError)
    async def otp_expired_handler(request: Request, exc: OtpExpiredError):
        return JSONResponse(status_code=410, content={"detail": str(exc)})

    @app.exception_handler(InvalidOtpError)
    async def invalid_otp_handler(request: Request, exc: InvalidOtpError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(UserServiceError)
    async def user_service_error_handler(request: Request, exc: UserServiceError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})
