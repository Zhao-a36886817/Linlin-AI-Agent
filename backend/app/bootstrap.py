from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config import Settings, get_settings
from app.portability import PortabilityRuntime

if TYPE_CHECKING:
    from fastapi import APIRouter

    from app.providers.manager import ProviderManager
    from app.providers.service import ProviderService
    from app.services.advanced_runtime import AdvancedRuntimeService
    from app.services.cloud_provider_service import CloudProviderService


@dataclass(frozen=True, slots=True)
class BackendBootstrap:
    settings: Settings
    api_router: APIRouter
    provider_manager: ProviderManager
    provider_service: ProviderService
    advanced_runtime_service: AdvancedRuntimeService
    cloud_provider_service: CloudProviderService
    recovered_workspace: bool


def bootstrap_backend() -> BackendBootstrap:
    """Recover Workspace before imports that construct runtime singletons."""

    settings = get_settings()
    recovered = PortabilityRuntime.recover_workspace(settings.workspace_root)
    settings.workspace_root.mkdir(parents=True, exist_ok=True)

    from app.api.router import api_router
    from app.providers.manager import provider_manager
    from app.providers.service import provider_service
    from app.services.advanced_runtime import advanced_runtime_service
    from app.services.cloud_provider_service import cloud_provider_service

    return BackendBootstrap(
        settings=settings,
        api_router=api_router,
        provider_manager=provider_manager,
        provider_service=provider_service,
        advanced_runtime_service=advanced_runtime_service,
        cloud_provider_service=cloud_provider_service,
        recovered_workspace=recovered,
    )
