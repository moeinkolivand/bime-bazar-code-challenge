from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI


from app.modules.order.exceptions.order_exception_handler import (
    register_order_exception_handlers,
)
from app.modules.reservation.exceptions.exception_handlers import (
    register_reservation_exception_handlers,
)
from app.modules.user import user_router, register_user_exception_handlers
from app.modules.reservation.routes.reservation_routes import (
    router as reservation_router,
)
from app.modules.order.routes.order_routes import router as order_router
from app.modules.reservation.workers.expiry_worker import run_expiry_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_expiry_worker(interval_seconds=30)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="BimeBazar API", version="1.0.0", lifespan=lifespan)
    api_v1_router = APIRouter(prefix="/api/v1")

    api_v1_router.include_router(user_router)
    api_v1_router.include_router(reservation_router)
    api_v1_router.include_router(order_router)
    app.include_router(api_v1_router)
    return app


app = create_app()
register_user_exception_handlers(app)
register_reservation_exception_handlers(app)
register_order_exception_handlers(app)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
