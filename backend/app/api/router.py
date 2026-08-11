from fastapi import APIRouter

from app.api.routes.advanced_runtime import router as advanced_runtime_router
from app.api.routes.chat import router as chat_router
from app.api.routes.code_generation import router as code_generation_router
from app.api.routes.health import router as health_router
from app.api.routes.models import router as models_router
from app.api.routes.providers import router as providers_router
from app.api.routes.runtime_control import router as runtime_control_router
from app.api.routes.system import router as system_router
from app.api.routes.training import router as training_router

api_router = APIRouter(prefix="/api")

api_router.include_router(advanced_runtime_router)
api_router.include_router(health_router)
api_router.include_router(system_router)
api_router.include_router(providers_router)
api_router.include_router(models_router)
api_router.include_router(chat_router)
api_router.include_router(code_generation_router)
api_router.include_router(runtime_control_router)
api_router.include_router(training_router)
