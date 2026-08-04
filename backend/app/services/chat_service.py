from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.providers.manager import provider_manager
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
    ChatUsage,
)


class ChatService:
    """Coordinates normalized chat calls through ProviderManager."""

    @staticmethod
    def _build_provider_options(request: ChatRequest) -> dict[str, Any]:
        options: dict[str, Any] = {}

        if request.options.temperature is not None:
            options["temperature"] = request.options.temperature

        if request.options.top_p is not None:
            options["top_p"] = request.options.top_p

        if request.options.max_tokens is not None:
            options["num_predict"] = request.options.max_tokens

        if request.options.seed is not None:
            options["seed"] = request.options.seed

        payload: dict[str, Any] = {}

        if options:
            payload["options"] = options

        if request.options.think is not None:
            payload["think"] = request.options.think

        if request.options.keep_alive is not None:
            payload["keep_alive"] = request.options.keep_alive

        return payload

    @staticmethod
    def _messages(request: ChatRequest) -> list[dict[str, Any]]:
        return [message.model_dump(exclude_none=True) for message in request.messages]

    @staticmethod
    def _usage(raw_usage: Any) -> ChatUsage:
        if not isinstance(raw_usage, dict):
            return ChatUsage()

        return ChatUsage(
            prompt_tokens=int(raw_usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(raw_usage.get("completion_tokens", 0) or 0),
            total_tokens=int(raw_usage.get("total_tokens", 0) or 0),
            total_duration_ns=int(raw_usage.get("total_duration_ns", 0) or 0),
            load_duration_ns=int(raw_usage.get("load_duration_ns", 0) or 0),
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        raw = await provider_manager.chat(
            provider=request.provider,
            model=request.model,
            messages=self._messages(request),
            **self._build_provider_options(request),
        )

        if not isinstance(raw, dict):
            raise TypeError("Provider returned an invalid chat response.")

        return ChatResponse(
            provider=str(raw.get("provider", request.provider)),
            model=str(raw.get("model", request.model)),
            role=str(raw.get("role", "assistant")),
            content=str(raw.get("content", "")),
            thinking=raw.get("thinking"),
            tool_calls=raw.get("tool_calls", []),
            done=bool(raw.get("done", True)),
            done_reason=raw.get("done_reason"),
            usage=self._usage(raw.get("usage")),
        )

    async def stream(
        self,
        request: ChatRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        async for raw in provider_manager.stream(
            provider=request.provider,
            model=request.model,
            messages=self._messages(request),
            **self._build_provider_options(request),
        ):
            if not isinstance(raw, dict):
                continue

            yield ChatStreamEvent(
                provider=str(raw.get("provider", request.provider)),
                model=str(raw.get("model", request.model)),
                role=str(raw.get("role", "assistant")),
                content=str(raw.get("content", "")),
                thinking=raw.get("thinking"),
                tool_calls=raw.get("tool_calls", []),
                done=bool(raw.get("done", False)),
                done_reason=raw.get("done_reason"),
                usage=self._usage(raw.get("usage")),
            )


chat_service = ChatService()
