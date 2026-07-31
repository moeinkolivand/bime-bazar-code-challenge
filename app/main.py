from fastapi import APIRouter, FastAPI
from app.modules.reservation.exceptions.exception_handlers import (
    register_reservation_exception_handlers,
)
from app.modules.user import user_router, register_user_exception_handlers
from app.modules.reservation import reservation_router


def create_app() -> FastAPI:
    app = FastAPI(title="BimeBazar API", version="1.0.0")
    api_v1_router = APIRouter(prefix="/api/v1")

    api_v1_router.include_router(user_router)
    api_v1_router.include_router(reservation_router)
    app.include_router(api_v1_router)
    return app


app = create_app()
register_user_exception_handlers(app)
register_reservation_exception_handlers(app)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
