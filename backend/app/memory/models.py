from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MemoryRecord(BaseModel):
    """A bounded memory item owned by one user and optional session."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    session_id: str | None = Field(default=None, max_length=200)
    content: str = Field(min_length=1, max_length=4000)
    created_at: datetime
    expires_at: datetime
