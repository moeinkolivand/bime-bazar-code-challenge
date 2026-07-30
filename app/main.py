from fastapi import APIRouter, FastAPI
from app.modules.user import user_router, register_user_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="BimeBazar API", version="1.0.0")
    api_v1_router = APIRouter(prefix="/api/v1")

    api_v1_router.include_router(user_router)
    app.include_router(api_v1_router)
    return app


app = create_app()
register_user_exception_handlers(app)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
