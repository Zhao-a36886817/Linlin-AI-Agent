from datetime import datetime

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.system import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    settings = get_settings()

    return HealthResponse(
        status="healthy",
        service=settings.linlin_app_name,
        version=settings.linlin_app_version,
        environment=settings.linlin_env,
        timestamp=datetime.now().astimezone(),
    )
