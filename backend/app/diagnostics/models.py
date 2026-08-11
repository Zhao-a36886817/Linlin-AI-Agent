from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DiagnosticEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID
    component: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,63}$")
    severity: Literal["info", "warning", "error"]
    actor: str = Field(default="system", min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=1_000)
    attributes: dict[str, Any] = Field(default_factory=dict)


class HealthSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_events: int = Field(ge=0)
    info_events: int = Field(ge=0)
    warning_events: int = Field(ge=0)
    error_events: int = Field(ge=0)
    retained_events: int = Field(ge=0)
