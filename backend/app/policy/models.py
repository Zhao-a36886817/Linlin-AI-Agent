from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class Identity(BaseModel):
    model_config = _FROZEN

    subject_id: str = Field(pattern=r"^[A-Za-z0-9_.@-]{1,100}$")
    tenant_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    roles: frozenset[str] = Field(default_factory=frozenset)


class PolicyRule(BaseModel):
    model_config = _FROZEN

    rule_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    effect: Literal["allow", "deny"]
    roles: frozenset[str] = Field(min_length=1)
    actions: frozenset[str] = Field(min_length=1)
    tenant_ids: frozenset[str] = Field(default_factory=frozenset)


class PolicyRequest(BaseModel):
    model_config = _FROZEN

    correlation_id: UUID
    identity: Identity
    action: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,100}$")
    resource_tenant_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    workspace_tenant_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")


class PolicyDecision(BaseModel):
    model_config = _FROZEN

    correlation_id: UUID
    subject_id: str
    tenant_id: str
    action: str
    allowed: bool
    reason: str
    matched_rule_ids: tuple[str, ...] = ()
