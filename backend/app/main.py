from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.contracts import (
    API_STABILITY_HEADER,
    API_VERSION_HEADER,
    ApiContractMiddleware,
)
from app.bootstrap import bootstrap_backend

_bootstrap = bootstrap_backend()
settings = _bootstrap.settings
api_router = _bootstrap.api_router
provider_manager = _bootstrap.provider_manager
provider_service = _bootstrap.provider_service
advanced_runtime_service = _bootstrap.advanced_runtime_service
cloud_provider_service = _bootstrap.cloud_provider_service


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    settings.output_root.mkdir(parents=True, exist_ok=True)
    settings.log_root.mkdir(parents=True, exist_ok=True)
    settings.data_root.mkdir(parents=True, exist_ok=True)

    await provider_service.initialize()
    await cloud_provider_service.initialize()

    if _bootstrap.recovered_workspace:
        print("Linlin Agent recovered an interrupted workspace restore")
    print("Linlin Agent backend started")

    yield

    await advanced_runtime_service.close()
    await provider_manager.close()
    print("Linlin Agent backend stopped")


app = FastAPI(
    title=settings.linlin_app_name,
    version=settings.linlin_app_version,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(ApiContractMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.linlin_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[API_VERSION_HEADER, API_STABILITY_HEADER],
)

app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": settings.linlin_app_name,
        "version": settings.linlin_app_version,
        "docs": "/docs",
        "health": "/api/health",
    }
