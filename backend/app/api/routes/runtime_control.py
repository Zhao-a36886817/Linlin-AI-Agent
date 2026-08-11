from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.memory import (
    MemoryConsentRequiredError,
    MemoryDisabledError,
    MemoryRuntime,
    MemorySensitiveDataError,
)
from app.services.advanced_runtime import advanced_runtime_service

router = APIRouter(prefix="/runtime-control", tags=["Runtime control"])
settings = get_settings()
memory_runtime = MemoryRuntime(
    enabled=settings.memory_enabled,
    default_ttl_seconds=settings.memory_default_ttl_seconds,
)

OwnerHeader = Annotated[str, Header(alias="X-Linlin-Owner", min_length=1, max_length=200)]


class RuntimeFeature(BaseModel):
    key: Literal["memory", "rag", "mcp", "orchestration", "scheduler"]
    label: str
    enabled: bool
    configured: bool
    status: Literal["ready", "disabled", "setup_required"]
    summary: str
    safety: str


class RuntimeOverview(BaseModel):
    local_first: bool = True
    features: list[RuntimeFeature]


class MemoryEnableRequest(BaseModel):
    enabled: bool
    confirmation: str


class MemoryCreateRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=200)
    content: str = Field(min_length=1, max_length=4000)
    ttl_seconds: int | None = Field(default=None, ge=1, le=31_536_000)
    consent: bool


def _feature(
    key: Literal["memory", "rag", "mcp", "orchestration", "scheduler"],
    label: str,
    *,
    enabled: bool,
    configured: bool,
    summary: str,
    safety: str,
) -> RuntimeFeature:
    current = "ready" if enabled and configured else "disabled" if configured else "setup_required"
    return RuntimeFeature(
        key=key,
        label=label,
        enabled=enabled,
        configured=configured,
        status=current,
        summary=summary,
        safety=safety,
    )


def _memory_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MemoryDisabledError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, (MemoryConsentRequiredError, MemorySensitiveDataError)):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    return HTTPException(status.HTTP_400_BAD_REQUEST, "Memory operation was rejected.")


@router.get("", response_model=RuntimeOverview)
async def overview() -> RuntimeOverview:
    advanced = advanced_runtime_service.status()
    return RuntimeOverview(features=[
        _feature(
            "memory",
            "Memory",
            enabled=memory_runtime.enabled,
            configured=True,
            summary="需明確同意、依工作階段隔離的本機記憶。",
            safety="疑似憑證內容會被拒絕，且記憶會依期限自動到期。",
        ),
        _feature(
            "rag",
            "Knowledge / RAG",
            enabled=advanced["rag"]["enabled"],
            configured=advanced["rag"]["configured"],
            summary="具工作區邊界與來源引用的文件檢索。",
            safety="啟用前必須設定經審查的 Embedding Provider。",
        ),
        _feature(
            "mcp",
            "MCP",
            enabled=advanced["mcp"]["connected"],
            configured=advanced["mcp"]["connected"],
            summary="預設拒絕的外部能力探索與管理。",
            safety="必須設定核准的 Transport 與 Server allowlist。",
        ),
        _feature(
            "orchestration",
            "Multi-agent",
            enabled=advanced["orchestration"]["enabled"],
            configured=True,
            summary="受深度、併發與成本上限約束的任務分派。",
            safety="必須設定核准角色與 Agent Runtime executor。",
        ),
        _feature(
            "scheduler",
            "Scheduler",
            enabled=advanced["scheduler"]["enabled"],
            configured=True,
            summary="需同意且只能執行核准應用程式動作的排程。",
            safety="必須設定 Action allowlist，永遠不接受任意命令。",
        ),
    ])


@router.put("/memory/enabled", response_model=RuntimeFeature)
async def set_memory_enabled(request: MemoryEnableRequest) -> RuntimeFeature:
    expected = "ENABLE MEMORY" if request.enabled else "DISABLE MEMORY"
    if request.confirmation != expected:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Type {expected} to confirm this change.",
        )
    memory_runtime.enabled = request.enabled
    return (await overview()).features[0]


@router.get("/memory/records")
async def list_memory_records(
    owner_id: OwnerHeader,
    session_id: Annotated[str | None, Query(max_length=200)] = None,
) -> list[dict[str, object]]:
    try:
        return [
            record.model_dump(mode="json")
            for record in memory_runtime.list_records(owner_id=owner_id, session_id=session_id)
        ]
    except Exception as exc:
        raise _memory_error(exc) from exc


@router.post("/memory/records", status_code=status.HTTP_201_CREATED)
async def create_memory_record(
    request: MemoryCreateRequest,
    owner_id: OwnerHeader,
) -> dict[str, object]:
    try:
        record = memory_runtime.remember(
            owner_id=owner_id,
            session_id=request.session_id,
            content=request.content,
            consent=request.consent,
            ttl_seconds=request.ttl_seconds,
        )
        return record.model_dump(mode="json")
    except Exception as exc:
        raise _memory_error(exc) from exc


@router.delete("/memory/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_record(
    record_id: UUID,
    owner_id: OwnerHeader,
    session_id: Annotated[str | None, Query(max_length=200)] = None,
) -> None:
    try:
        removed = memory_runtime.delete(
            owner_id=owner_id,
            session_id=session_id,
            record_id=record_id,
        )
    except Exception as exc:
        raise _memory_error(exc) from exc
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory record was not found.")
