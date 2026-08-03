from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    timestamp: datetime


class SystemInfoResponse(BaseModel):
    app_name: str
    app_version: str
    environment: str
    python_version: str
    platform: str
    architecture: str
    hostname: str
    cpu_count: int
    memory_total_gb: float


class AgentStatusResponse(BaseModel):
    runtime_status: str
    configured_models: int
    active_agents: int
    max_parallel_agents: int
    current_task_id: str | None = None
