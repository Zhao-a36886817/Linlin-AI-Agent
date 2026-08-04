from __future__ import annotations

from typing import Any

import pytest

from app.agents.tool_loop import (
    ToolCallFormatError,
    ToolLoop,
    ToolLoopLimitError,
)
from app.tools.calculator import CalculatorTool
from app.tools.manager import ToolManager


class FakeProviderManager:
    def __init__(
        self,
        responses: list[dict[str, Any]],
    ) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    async def chat(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.requests.append(
            {
                "provider": provider,
                "model": model,
                "messages": [dict(message) for message in messages],
                "kwargs": kwargs,
            },
        )

        if not self.responses:
            raise RuntimeError("No fake response available.")

        return self.responses.pop(0)


def create_tool_manager() -> ToolManager:
    manager = ToolManager()
    manager.register(CalculatorTool())
    return manager


@pytest.mark.asyncio
async def test_tool_loop_returns_direct_answer() -> None:
    provider_manager = FakeProviderManager(
        [
            {
                "provider": "ollama",
                "model": "qwen3:4b",
                "content": "??? 240?",
                "tool_calls": [],
                "done": True,
            },
        ],
    )

    loop = ToolLoop(
        provider_manager=provider_manager,  # type: ignore[arg-type]
        tool_manager=create_tool_manager(),
    )

    response = await loop.run(
        provider="ollama",
        model="qwen3:4b",
        messages=[
            {
                "role": "user",
                "content": "??????",
            },
        ],
    )

    assert response["content"] == "??? 240?"
    assert len(provider_manager.requests) == 1


@pytest.mark.asyncio
async def test_tool_loop_executes_calculator() -> None:
    provider_manager = FakeProviderManager(
        [
            {
                "provider": "ollama",
                "model": "qwen3:4b",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "calculator",
                            "arguments": {
                                "expression": "(25 + 5) * 8",
                            },
                        },
                    },
                ],
                "done": False,
            },
            {
                "provider": "ollama",
                "model": "qwen3:4b",
                "content": "(25 + 5) ? 8 = 240?",
                "tool_calls": [],
                "done": True,
            },
        ],
    )

    loop = ToolLoop(
        provider_manager=provider_manager,  # type: ignore[arg-type]
        tool_manager=create_tool_manager(),
    )

    response = await loop.run(
        provider="ollama",
        model="qwen3:4b",
        messages=[
            {
                "role": "user",
                "content": "??? (25 + 5) * 8?",
            },
        ],
    )

    assert response["content"] == "(25 + 5) ? 8 = 240?"
    assert len(provider_manager.requests) == 2

    second_messages = provider_manager.requests[1]["messages"]

    assert second_messages[-2]["role"] == "assistant"
    assert second_messages[-1]["role"] == "tool"
    assert second_messages[-1]["name"] == "calculator"
    assert second_messages[-1]["tool_call_id"] == "call-1"
    assert '"result": 240' in second_messages[-1]["content"]


@pytest.mark.asyncio
async def test_tool_loop_accepts_json_string_arguments() -> None:
    provider_manager = FakeProviderManager(
        [
            {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "calculator",
                            "arguments": '{"expression": "12 * 8"}',
                        },
                    },
                ],
            },
            {
                "content": "12 ? 8 = 96?",
                "tool_calls": [],
            },
        ],
    )

    loop = ToolLoop(
        provider_manager=provider_manager,  # type: ignore[arg-type]
        tool_manager=create_tool_manager(),
    )

    response = await loop.run(
        provider="ollama",
        model="qwen3:4b",
        messages=[
            {
                "role": "user",
                "content": "12 * 8 ????",
            },
        ],
    )

    assert response["content"] == "12 ? 8 = 96?"


@pytest.mark.asyncio
async def test_tool_loop_rejects_invalid_tool_call() -> None:
    provider_manager = FakeProviderManager(
        [
            {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "arguments": {},
                        },
                    },
                ],
            },
        ],
    )

    loop = ToolLoop(
        provider_manager=provider_manager,  # type: ignore[arg-type]
        tool_manager=create_tool_manager(),
    )

    with pytest.raises(ToolCallFormatError):
        await loop.run(
            provider="ollama",
            model="qwen3:4b",
            messages=[
                {
                    "role": "user",
                    "content": "??",
                },
            ],
        )


@pytest.mark.asyncio
async def test_tool_loop_stops_at_iteration_limit() -> None:
    repeated_response = {
        "content": "",
        "tool_calls": [
            {
                "function": {
                    "name": "calculator",
                    "arguments": {
                        "expression": "1 + 1",
                    },
                },
            },
        ],
    }

    provider_manager = FakeProviderManager(
        [
            repeated_response,
            repeated_response,
        ],
    )

    loop = ToolLoop(
        provider_manager=provider_manager,  # type: ignore[arg-type]
        tool_manager=create_tool_manager(),
        max_iterations=2,
    )

    with pytest.raises(ToolLoopLimitError):
        await loop.run(
            provider="ollama",
            model="qwen3:4b",
            messages=[
                {
                    "role": "user",
                    "content": "??????",
                },
            ],
        )
