from __future__ import annotations

from pydantic import BaseModel


class ModelInfo(BaseModel):
    provider: str
    name: str
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    context_length: int | None = None
    embedding_length: int | None = None
    capabilities: list[str] = []


class ModelListResponse(BaseModel):
    items: list[ModelInfo]
    total: int
