from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.modules.order.exceptions.order_exceptions import (
    OrderServiceError,
    ReservationNotConfirmedError,
    OrderAlreadyExistsError,
    OrderNotFoundError,
)


def register_order_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(OrderNotFoundError)
    async def order_not_found_handler(request: Request, exc: OrderNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ReservationNotConfirmedError)
    async def reservation_not_confirmed_handler(
        request: Request, exc: ReservationNotConfirmedError
    ):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(OrderAlreadyExistsError)
    async def order_already_exists_handler(
        request: Request, exc: OrderAlreadyExistsError
    ):
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc), "order_id": exc.order_id},
        )

    @app.exception_handler(OrderServiceError)
    async def order_service_error_handler(request: Request, exc: OrderServiceError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})
