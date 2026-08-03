from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
    ),
]


class ProviderKind(StrEnum):
    """Provider families supported by Linlin Agent."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    GROQ = "groq"
    DEEPSEEK = "deepseek"
    MISTRAL = "mistral"
    OPENAI_COMPATIBLE = "openai_compatible"


class ProviderCreate(BaseModel):
    """Data accepted when creating a provider."""

    model_config = ConfigDict(extra="forbid")

    name: NonEmptyString
    kind: ProviderKind

    base_url: str | None = Field(
        default=None,
        max_length=1000,
    )

    api_key_env: str | None = Field(
        default=None,
        pattern=r"^[A-Z][A-Z0-9_]*$",
        max_length=100,
        description="Environment variable containing the API key.",
    )

    default_model: str | None = Field(
        default=None,
        max_length=300,
    )

    enabled: bool = True

    timeout_seconds: int = Field(
        default=120,
        ge=5,
        le=600,
    )

    max_concurrency: int = Field(
        default=2,
        ge=1,
        le=16,
    )

    priority: int = Field(
        default=100,
        ge=1,
        le=1000,
    )

    metadata: dict[str, str] = Field(default_factory=dict)


class ProviderUpdate(BaseModel):
    """Data accepted when updating a provider."""

    model_config = ConfigDict(extra="forbid")

    name: NonEmptyString | None = None
    kind: ProviderKind | None = None

    base_url: str | None = Field(
        default=None,
        max_length=1000,
    )

    api_key_env: str | None = Field(
        default=None,
        pattern=r"^[A-Z][A-Z0-9_]*$",
        max_length=100,
    )

    default_model: str | None = Field(
        default=None,
        max_length=300,
    )

    enabled: bool | None = None

    timeout_seconds: int | None = Field(
        default=None,
        ge=5,
        le=600,
    )

    max_concurrency: int | None = Field(
        default=None,
        ge=1,
        le=16,
    )

    priority: int | None = Field(
        default=None,
        ge=1,
        le=1000,
    )

    metadata: dict[str, str] | None = None


class ProviderConfig(BaseModel):
    """Complete provider configuration stored on disk."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: NonEmptyString
    kind: ProviderKind

    base_url: str | None = None
    api_key_env: str | None = None
    default_model: str | None = None

    enabled: bool = True
    timeout_seconds: int = 120
    max_concurrency: int = 2
    priority: int = 100

    metadata: dict[str, str] = Field(default_factory=dict)

    created_at: datetime
    updated_at: datetime


class ProviderPublic(BaseModel):
    """Provider information safe to return through the API."""

    id: UUID
    name: str
    kind: ProviderKind

    base_url: str | None
    api_key_env: str | None
    has_api_key: bool
    default_model: str | None

    enabled: bool
    timeout_seconds: int
    max_concurrency: int
    priority: int

    metadata: dict[str, str]

    created_at: datetime
    updated_at: datetime


class ProviderListResponse(BaseModel):
    """Provider listing response."""

    items: list[ProviderPublic]
    total: int
    enabled: int


class ProviderDeleteResponse(BaseModel):
    """Provider deletion response."""

    deleted: bool
    provider_id: UUID
