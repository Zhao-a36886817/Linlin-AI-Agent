from fastapi import APIRouter

from app.schemas.system import AgentStatusResponse, SystemInfoResponse
from app.services.system_service import system_service

router = APIRouter(tags=["System"])


@router.get("/system/info", response_model=SystemInfoResponse)
async def get_system_info() -> SystemInfoResponse:
    return system_service.get_system_info()


@router.get("/agents/status", response_model=AgentStatusResponse)
async def get_agent_status() -> AgentStatusResponse:
    return system_service.get_agent_status()
