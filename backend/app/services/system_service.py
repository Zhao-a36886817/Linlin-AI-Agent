import os
import platform
import socket
import sys

import psutil

from app.core.config import get_settings
from app.schemas.system import AgentStatusResponse, SystemInfoResponse


class SystemService:
    def get_system_info(self) -> SystemInfoResponse:
        settings = get_settings()
        memory = psutil.virtual_memory()

        return SystemInfoResponse(
            app_name=settings.linlin_app_name,
            app_version=settings.linlin_app_version,
            environment=settings.linlin_env,
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            architecture=platform.machine(),
            hostname=socket.gethostname(),
            cpu_count=os.cpu_count() or 1,
            memory_total_gb=round(memory.total / (1024**3), 2),
        )

    def get_agent_status(self) -> AgentStatusResponse:
        settings = get_settings()

        return AgentStatusResponse(
            runtime_status="idle",
            configured_models=0,
            active_agents=0,
            max_parallel_agents=settings.max_parallel_agents,
            current_task_id=None,
        )


system_service = SystemService()
