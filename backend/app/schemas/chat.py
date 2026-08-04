from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ChatRole = Literal["system", "user", "assistant", "tool"]


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1)
    name: str | None = None
    tool_call_id: str | None = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        content = value.strip()

        if not content:
            raise ValueError("Message content cannot be empty.")

        return content


class ChatOptions(BaseModel):
    temperature: float | None = Field(default=0.3, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=512, ge=1, le=32768)
    seed: int | None = None
    think: bool | None = None
    keep_alive: str | int | None = None


class ChatRequest(BaseModel):
    provider: str = Field(default="ollama", min_length=1)
    model: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    options: ChatOptions = Field(default_factory=ChatOptions)

    @field_validator("provider", "model")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        identifier = value.strip()

        if not identifier:
            raise ValueError("Provider and model cannot be empty.")

        return identifier


class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_duration_ns: int = 0
    load_duration_ns: int = 0


class ChatResponse(BaseModel):
    provider: str
    model: str
    role: str = "assistant"
    content: str
    thinking: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    done: bool = True
    done_reason: str | None = None
    usage: ChatUsage = Field(default_factory=ChatUsage)


class ChatStreamEvent(BaseModel):
    provider: str
    model: str
    role: str = "assistant"
    content: str = ""
    thinking: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    done: bool = False
    done_reason: str | None = None
    usage: ChatUsage = Field(default_factory=ChatUsage)
