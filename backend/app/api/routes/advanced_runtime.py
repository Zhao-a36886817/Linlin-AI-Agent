from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from app.services.advanced_runtime import (
    AdvancedRuntimeError,
    advanced_runtime_service,
)

router = APIRouter(prefix="/advanced-runtime", tags=["Advanced runtime"])


class RagConfigureRequest(BaseModel):
    enabled: bool
    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=300)


class RagIngestRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    consent: bool


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10_000)
    limit: int = Field(default=5, ge=1, le=20)


class McpConnectRequest(BaseModel):
    server_id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    endpoint: HttpUrl
    consent: bool


class McpInvokeRequest(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    arguments: dict[str, Any] = Field(default_factory=dict)


class OrchestrationRunRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=300)
    task: str = Field(min_length=1, max_length=10_000)
    iterations: int = Field(default=4, ge=2, le=10)
    cost_units: int = Field(default=4096, ge=2, le=100_000)


class SchedulerEnableRequest(BaseModel):
    enabled: bool
    confirmation: str


class SchedulerJobRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=300)
    prompt: str = Field(min_length=1, max_length=10_000)
    run_at: datetime
    consent: bool


def rejected(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(exc),
    )


@router.get("")
async def advanced_status() -> dict[str, Any]:
    return advanced_runtime_service.status()


@router.put("/rag")
async def configure_rag(request: RagConfigureRequest) -> dict[str, Any]:
    try:
        return advanced_runtime_service.configure_rag(**request.model_dump())
    except Exception as exc:
        raise rejected(exc) from exc


@router.post("/rag/ingest")
async def ingest_rag(request: RagIngestRequest) -> dict[str, Any]:
    try:
        return await advanced_runtime_service.ingest_rag(**request.model_dump())
    except Exception as exc:
        raise rejected(exc) from exc


@router.post("/rag/search")
async def search_rag(request: RagSearchRequest) -> list[dict[str, Any]]:
    try:
        return await advanced_runtime_service.search_rag(**request.model_dump())
    except Exception as exc:
        raise rejected(exc) from exc


@router.post("/mcp/connect")
async def connect_mcp(request: McpConnectRequest) -> dict[str, Any]:
    try:
        tools = await advanced_runtime_service.connect_mcp(
            server_id=request.server_id,
            endpoint=str(request.endpoint),
            consent=request.consent,
        )
        return {"connected": True, "tools": tools}
    except Exception as exc:
        raise rejected(exc) from exc


@router.delete("/mcp", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_mcp() -> None:
    await advanced_runtime_service.disconnect_mcp()


@router.post("/mcp/invoke")
async def invoke_mcp(request: McpInvokeRequest) -> dict[str, Any]:
    try:
        return await advanced_runtime_service.invoke_mcp(
            request.name,
            request.arguments,
        )
    except Exception as exc:
        raise rejected(exc) from exc


@router.post("/orchestration/runs", status_code=status.HTTP_202_ACCEPTED)
async def start_orchestration(request: OrchestrationRunRequest) -> dict[str, Any]:
    try:
        return advanced_runtime_service.start_orchestration(**request.model_dump())
    except Exception as exc:
        raise rejected(exc) from exc


@router.get("/orchestration/runs")
async def list_orchestration() -> list[dict[str, Any]]:
    return advanced_runtime_service.list_orchestration()


@router.delete("/orchestration/runs/{run_id}")
async def cancel_orchestration(run_id: UUID) -> dict[str, bool]:
    return {"cancelled": advanced_runtime_service.cancel_orchestration(run_id)}


@router.put("/scheduler")
async def configure_scheduler(request: SchedulerEnableRequest) -> dict[str, Any]:
    expected = "ENABLE SCHEDULER" if request.enabled else "DISABLE SCHEDULER"
    if request.confirmation != expected:
        raise rejected(AdvancedRuntimeError(f"Type {expected} to confirm."))
    try:
        return await advanced_runtime_service.set_scheduler_enabled(request.enabled)
    except Exception as exc:
        raise rejected(exc) from exc


@router.get("/scheduler/jobs")
async def scheduler_jobs() -> dict[str, Any]:
    return advanced_runtime_service.scheduler_state()


@router.post("/scheduler/jobs", status_code=status.HTTP_201_CREATED)
async def schedule_job(request: SchedulerJobRequest) -> dict[str, Any]:
    try:
        return advanced_runtime_service.schedule_chat(**request.model_dump())
    except Exception as exc:
        raise rejected(exc) from exc


@router.delete("/scheduler/jobs/{job_id}")
async def cancel_job(job_id: UUID) -> dict[str, bool]:
    try:
        return {"cancelled": advanced_runtime_service.cancel_scheduled(job_id)}
    except Exception as exc:
        raise rejected(exc) from exc


@router.post("/scheduler/tick")
async def scheduler_tick() -> dict[str, list[str]]:
    try:
        return {"completed": await advanced_runtime_service.run_scheduler_due()}
    except Exception as exc:
        raise rejected(exc) from exc
