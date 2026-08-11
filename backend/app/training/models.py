from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

TrainingStatus = Literal[
    "validating",
    "uploading",
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "unknown",
]
TrainingEngine = Literal["openai_compatible", "local_lora"]


class TrainingMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class TrainingJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=300)
    messages: list[TrainingMessage] = Field(min_length=2, max_length=200)
    engine: TrainingEngine = "openai_compatible"
    cloud_consent: bool = False
    local_consent: bool = False
    max_steps: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_roles(self) -> TrainingJobCreate:
        roles = {message.role for message in self.messages}
        if not {"user", "assistant"}.issubset(roles):
            raise ValueError("Training data requires at least one user and assistant message.")
        return self


class TrainingMetric(BaseModel):
    step: int = Field(ge=0)
    train_loss: float | None = None
    valid_loss: float | None = None


class TrainingJob(BaseModel):
    id: UUID
    conversation_id: str
    engine: TrainingEngine
    provider: str
    provider_label: str
    model: str
    provider_job_id: str
    status: TrainingStatus
    examples: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    trained_model: str | None = None
    error: str | None = None
    metrics: list[TrainingMetric] = Field(default_factory=list, max_length=200)


class TrainingModel(BaseModel):
    engine: TrainingEngine
    provider: str
    provider_label: str
    model: str
    local: bool = False
    size_bytes: int | None = Field(default=None, ge=0)


class LocalTrainingCapability(BaseModel):
    available: bool
    engine: Literal["local_lora"] = "local_lora"
    reason: str


class TrainingCapabilities(BaseModel):
    models: list[TrainingModel]
    local: LocalTrainingCapability
    polling_interval_seconds: int = 2
    max_active_jobs: int = 2
