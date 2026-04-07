from fastapi import APIRouter

from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.protected import router as protected_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(health_router)
v1_router.include_router(protected_router)
