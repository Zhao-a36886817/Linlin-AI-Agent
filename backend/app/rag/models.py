from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RagChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source: str
    text: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    untrusted_instructions: bool = False


class RagCitation(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    start: int
    end: int


class RagResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    score: float
    citation: RagCitation
    untrusted_instructions: bool
