from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.training.models import (
    TrainingCapabilities,
    TrainingJob,
    TrainingJobCreate,
)
from app.training.service import TrainingError, training_service

router = APIRouter(prefix="/training", tags=["Training"])


@router.get("/capabilities", response_model=TrainingCapabilities)
async def capabilities() -> TrainingCapabilities:
    try:
        return await training_service.capabilities()
    except (TrainingError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/jobs", response_model=TrainingJob, status_code=status.HTTP_201_CREATED)
async def create_job(payload: TrainingJobCreate) -> TrainingJob:
    try:
        return await training_service.create(payload)
    except (TrainingError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("/jobs", response_model=list[TrainingJob])
async def list_jobs(
    conversation_id: str = Query(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"),
) -> list[TrainingJob]:
    try:
        return await training_service.list(conversation_id)
    except (TrainingError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel", response_model=TrainingJob)
async def cancel_job(
    job_id: UUID,
    conversation_id: str = Query(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"),
) -> TrainingJob:
    try:
        return await training_service.cancel(job_id, conversation_id=conversation_id)
    except TrainingError as exc:
        code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_422_UNPROCESSABLE_CONTENT
        raise HTTPException(status_code=code, detail=str(exc)) from exc

