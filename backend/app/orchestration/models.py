from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentRole(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    capabilities: frozenset[str] = Field(default_factory=frozenset)


class DelegationBudget(BaseModel):
    model_config = ConfigDict(frozen=True)

    iterations: int = Field(ge=1, le=100)
    cost_units: int = Field(ge=0, le=1_000_000)


class AgentContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent_id: UUID
    role: str
    permissions: frozenset[str]
    budget: DelegationBudget
    depth: int = Field(ge=0)
    role_path: tuple[str, ...]


class DelegationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_role: str
    task: str = Field(min_length=1, max_length=10_000)
    permissions: frozenset[str] = Field(default_factory=frozenset)
    budget: DelegationBudget


class ExecutionReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    output: Any = None
    iterations_used: int = Field(ge=0)
    cost_units_used: int = Field(ge=0)


class DelegationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent_id: UUID
    status: Literal["completed", "cancelled"]
    output: Any = None
    iterations_used: int = Field(ge=0)
    cost_units_used: int = Field(ge=0)
