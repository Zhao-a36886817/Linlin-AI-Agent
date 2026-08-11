from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScheduledJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    action: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,100}$")
    arguments: dict[str, Any] = Field(default_factory=dict)
    run_at: datetime
    status: Literal["scheduled", "completed", "cancelled", "failed"] = "scheduled"
    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=1, ge=1, le=5)


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: UUID
    event: str
    occurred_at: datetime
