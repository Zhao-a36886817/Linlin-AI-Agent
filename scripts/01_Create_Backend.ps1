#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Linlin-Agent"
$BackendRoot = "$ProjectRoot\backend"
$ScriptsRoot = "$ProjectRoot\scripts"
$EnvironmentName = "Linlin_agent"

function Write-Section {
    param([string]$Text)

    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host " $Text" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan
}

function Write-FileUtf8 {
    param(
        [string]$Path,
        [string]$Content
    )

    $Parent = Split-Path -Parent $Path

    if ($Parent) {
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    }

    Set-Content -Path $Path -Value $Content -Encoding UTF8
}

Write-Section "Linlin Agent Backend Installer"

if ($env:CONDA_DEFAULT_ENV -ne $EnvironmentName) {
    throw "隢??瑁?嚗onda activate Linlin_agent"
}

foreach ($Command in @("python", "conda")) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "?曆??唳?隞歹?$Command"
    }
}

Write-Host "Conda Environment: $env:CONDA_DEFAULT_ENV" -ForegroundColor Green
Write-Host "Python: $((Get-Command python).Source)" -ForegroundColor Green

Write-Section "Creating folders"

$Folders = @(
    "$BackendRoot\app",
    "$BackendRoot\app\api",
    "$BackendRoot\app\api\routes",
    "$BackendRoot\app\core",
    "$BackendRoot\app\schemas",
    "$BackendRoot\app\services",
    "$BackendRoot\app\agents",
    "$BackendRoot\app\runtime",
    "$BackendRoot\app\providers",
    "$BackendRoot\app\tools",
    "$BackendRoot\tests",
    "$ProjectRoot\workspace",
    "$ProjectRoot\outputs",
    "$ProjectRoot\logs",
    "$ProjectRoot\data",
    $ScriptsRoot
)

foreach ($Folder in $Folders) {
    New-Item -ItemType Directory -Force -Path $Folder | Out-Null
}

Write-Section "Installing Python packages"

python -m pip install --upgrade pip setuptools wheel

python -m pip install `
    fastapi `
    "uvicorn[standard]" `
    pydantic `
    pydantic-settings `
    python-dotenv `
    httpx `
    aiofiles `
    python-multipart `
    sse-starlette `
    structlog `
    orjson `
    psutil `
    pytest `
    pytest-asyncio `
    ruff

Write-Section "Creating backend source files"

Write-FileUtf8 "$BackendRoot\app\__init__.py" @'
"""Linlin Agent backend."""
'@

Write-FileUtf8 "$BackendRoot\app\api\__init__.py" @'
"""API package."""
'@

Write-FileUtf8 "$BackendRoot\app\api\routes\__init__.py" @'
"""API routes."""
'@

Write-FileUtf8 "$BackendRoot\app\core\__init__.py" @'
"""Core package."""
'@

Write-FileUtf8 "$BackendRoot\app\schemas\__init__.py" @'
"""Schema package."""
'@

Write-FileUtf8 "$BackendRoot\app\services\__init__.py" @'
"""Service package."""
'@

Write-FileUtf8 "$BackendRoot\app\agents\__init__.py" @'
"""Agent package."""
'@

Write-FileUtf8 "$BackendRoot\app\runtime\__init__.py" @'
"""Runtime package."""
'@

Write-FileUtf8 "$BackendRoot\app\providers\__init__.py" @'
"""Provider package."""
'@

Write-FileUtf8 "$BackendRoot\app\tools\__init__.py" @'
"""Tool package."""
'@

Write-FileUtf8 "$BackendRoot\app\core\config.py" @'
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    linlin_env: str = "development"
    linlin_app_name: str = "Linlin Agent"
    linlin_app_version: str = "0.1.0"

    linlin_backend_host: str = "127.0.0.1"
    linlin_backend_port: int = 8000
    linlin_frontend_origin: str = "http://localhost:1420"

    max_parallel_agents: int = 4

    workspace_root: Path = PROJECT_ROOT / "workspace"
    output_root: Path = PROJECT_ROOT / "outputs"
    log_root: Path = PROJECT_ROOT / "logs"
    data_root: Path = PROJECT_ROOT / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()
'@

Write-FileUtf8 "$BackendRoot\app\schemas\system.py" @'
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
'@

Write-FileUtf8 "$BackendRoot\app\services\system_service.py" @'
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
            memory_total_gb=round(memory.total / (1024 ** 3), 2),
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
'@

Write-FileUtf8 "$BackendRoot\app\api\routes\health.py" @'
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
'@

Write-FileUtf8 "$BackendRoot\app\api\routes\system.py" @'
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
'@

Write-FileUtf8 "$BackendRoot\app\api\router.py" @'
from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.system import router as system_router


api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(system_router)
'@

Write-FileUtf8 "$BackendRoot\app\main.py" @'
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.router import api_router
from app.core.config import get_settings


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    settings.output_root.mkdir(parents=True, exist_ok=True)
    settings.log_root.mkdir(parents=True, exist_ok=True)
    settings.data_root.mkdir(parents=True, exist_ok=True)

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
'@

Write-FileUtf8 "$BackendRoot\tests\test_health.py" @'
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_agent_status() -> None:
    response = client.get("/api/agents/status")

    assert response.status_code == 200
    assert response.json()["runtime_status"] == "idle"
'@

Write-FileUtf8 "$ProjectRoot\.env.example" @'
LINLIN_ENV=development
LINLIN_APP_NAME=Linlin Agent
LINLIN_APP_VERSION=0.1.0

LINLIN_BACKEND_HOST=127.0.0.1
LINLIN_BACKEND_PORT=8000
LINLIN_FRONTEND_ORIGIN=http://localhost:1420

MAX_PARALLEL_AGENTS=4

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
'@

if (-not (Test-Path "$ProjectRoot\.env")) {
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
}

Write-FileUtf8 "$ScriptsRoot\start-backend.ps1" @'
#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$EnvironmentName = "Linlin_agent"
$ProjectRoot = "C:\Linlin-Agent"
$BackendRoot = "$ProjectRoot\backend"

if ($env:CONDA_DEFAULT_ENV -ne $EnvironmentName) {
    throw "隢??瑁?嚗onda activate Linlin_agent"
}

if (-not (Test-Path "$BackendRoot\app\main.py")) {
    throw "?曆???backend\app\main.py"
}

Set-Location $BackendRoot
$env:PYTHONPATH = $BackendRoot

Write-Host ""
Write-Host "Linlin Agent Backend" -ForegroundColor Cyan
Write-Host "API  : http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Docs : http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host ""

python -m uvicorn app.main:app `
    --host 127.0.0.1 `
    --port 8000 `
    --reload
'@

Write-FileUtf8 "$ScriptsRoot\test-backend.ps1" @'
#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Linlin-Agent"
$BackendRoot = "$ProjectRoot\backend"

Set-Location $BackendRoot
$env:PYTHONPATH = $BackendRoot

python -m pytest -v
'@

Write-Section "Testing backend"

Set-Location $BackendRoot
$env:PYTHONPATH = $BackendRoot

python -m pytest -v

if ($LASTEXITCODE -ne 0) {
    throw "Backend test failed."
}

Write-Host ""
Write-Host "Backend 建立完成。" -ForegroundColor Green
Write-Host ""
Write-Host "下一步執行：" -ForegroundColor Yellow
Write-Host "cd C:\Linlin-Agent"
Write-Host ".\scripts\start-backend.ps1"
Write-Host ""
