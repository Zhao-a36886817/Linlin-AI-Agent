from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.providers.service import provider_service

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    settings.output_root.mkdir(parents=True, exist_ok=True)
    settings.log_root.mkdir(parents=True, exist_ok=True)
    settings.data_root.mkdir(parents=True, exist_ok=True)

    await provider_service.initialize()

    print("Linlin Agent backend started")

    yield

    print("Linlin Agent backend stopped")


app = FastAPI(
    title=settings.linlin_app_name,
    version=settings.linlin_app_version,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.linlin_frontend_origin,
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
