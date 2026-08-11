from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ArtifactKind = Literal["image", "audio", "document"]


class ArtifactProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1, max_length=500)
    imported_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Artifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    path: str
    kind: ArtifactKind
    content_type: str
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    temporary: bool
    provenance: ArtifactProvenance


class MultimodalRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt: str = Field(min_length=1, max_length=100_000)
    artifacts: tuple[Artifact, ...] = ()
    handling: Literal["local", "cloud"] = "local"
    cloud_consent: bool = False

    @model_validator(mode="after")
    def require_visible_cloud_consent(self) -> MultimodalRequest:
        if self.handling == "cloud" and not self.cloud_consent:
            raise ValueError("Cloud artifact handling requires explicit consent.")
        if self.handling == "local" and self.cloud_consent:
            raise ValueError("Cloud consent must not be set for local handling.")
        return self
