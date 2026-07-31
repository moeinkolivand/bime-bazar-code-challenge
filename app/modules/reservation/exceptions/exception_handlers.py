from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.modules.reservation.exceptions.reservation_exceptions import (
    ReservationServiceError,
    ReservationNotFoundError,
    ReservationNotPendingError,
    InsufficientStockError,
    ReservationFailedError,
    ReservationConfirmationIncompleteError,
)


def register_reservation_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ReservationNotFoundError)
    async def not_found_handler(request: Request, exc: ReservationNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ReservationNotPendingError)
    async def not_pending_handler(request: Request, exc: ReservationNotPendingError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InsufficientStockError)
    async def insufficient_stock_handler(request: Request, exc: InsufficientStockError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ReservationFailedError)
    async def reservation_failed_handler(request: Request, exc: ReservationFailedError):
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc), "failed_skus": exc.failed_skus},
        )

    @app.exception_handler(ReservationConfirmationIncompleteError)
    async def confirmation_incomplete_handler(
        request: Request, exc: ReservationConfirmationIncompleteError
    ):
        return JSONResponse(status_code=202, content={"detail": str(exc)})

    @app.exception_handler(ReservationServiceError)
    async def reservation_service_error_handler(
        request: Request, exc: ReservationServiceError
    ):
        return JSONResponse(status_code=400, content={"detail": str(exc)})
