from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.code_generation_service import (
    CodeGenerationError,
    code_generation_service,
)

router = APIRouter(prefix="/code-generation", tags=["Code generation"])


class CodeProposalRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=300)
    instruction: str = Field(min_length=1, max_length=20_000)
    target_path: str = Field(min_length=1, max_length=1000)
    context_paths: list[str] = Field(default_factory=list, max_length=20)
    cloud_consent: bool = False


class CodeApplyRequest(BaseModel):
    confirmation: str
    consent: bool


def rejected(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(exc),
    )


@router.post("/proposals", status_code=status.HTTP_201_CREATED)
async def propose_code(request: CodeProposalRequest) -> dict[str, Any]:
    try:
        return await code_generation_service.propose(**request.model_dump())
    except (CodeGenerationError, RuntimeError, TypeError, ValueError) as exc:
        raise rejected(exc) from exc


@router.get("/proposals")
async def list_code_proposals() -> list[dict[str, Any]]:
    return code_generation_service.list_proposals()


@router.delete("/proposals/{proposal_id}")
async def discard_code_proposal(proposal_id: UUID) -> dict[str, bool]:
    return {"discarded": code_generation_service.discard(proposal_id)}


@router.post("/proposals/{proposal_id}/apply")
async def apply_code_proposal(
    proposal_id: UUID,
    request: CodeApplyRequest,
) -> dict[str, Any]:
    try:
        return code_generation_service.apply(proposal_id, **request.model_dump())
    except (CodeGenerationError, RuntimeError, TypeError, ValueError) as exc:
        raise rejected(exc) from exc
