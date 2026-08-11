from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResourceRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    cpu_units: int = Field(default=1, ge=1)
    memory_bytes: int = Field(default=1, ge=1)


class ResourceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    active: int = Field(ge=0)
    waiting: int = Field(ge=0)
    cpu_units: int = Field(ge=0)
    memory_bytes: int = Field(ge=0)
    peak_active: int = Field(ge=0)
    peak_cpu_units: int = Field(ge=0)
    peak_memory_bytes: int = Field(ge=0)
    completed: int = Field(ge=0)
    rejected: int = Field(ge=0)
    timed_out: int = Field(ge=0)
    cancelled: int = Field(ge=0)
