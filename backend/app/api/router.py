from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.models import router as models_router
from app.api.routes.providers import router as providers_router
from app.api.routes.system import router as system_router

api_router = APIRouter(prefix="/api")

api_router.include_router(health_router)
api_router.include_router(system_router)
api_router.include_router(providers_router)
api_router.include_router(models_router)