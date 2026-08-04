from __future__ import annotations

from typing import Any

import pytest

from app.providers.manager import provider_manager
from app.schemas.chat import ChatRequest
from app.services.chat_service import chat_service, tool_loop


def build_request(*, tools_enabled: bool) -> ChatRequest:
    return ChatRequest(
        provider="ollama",
        model="qwen3:4b",
        messages=[
            {
                "role": "user",
                "content": "??? (25 + 5) * 8?",
            },
        ],
        tools_enabled=tools_enabled,
    )


@pytest.mark.asyncio
async def test_chat_uses_tool_loop_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    async def fake_tool_loop_run(**kwargs: Any) -> dict[str, Any]:
        calls["tool_loop"] = kwargs

        return {
            "provider": "ollama",
            "model": "qwen3:4b",
            "role": "assistant",
            "content": "(25 + 5) ? 8 = 240?",
            "thinking": None,
            "tool_calls": [],
            "done": True,
            "done_reason": "stop",
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
            },
        }

    async def fail_direct_chat(**_: Any) -> dict[str, Any]:
        raise AssertionError(
            "provider_manager.chat must not run when tools are enabled.",
        )

    monkeypatch.setattr(tool_loop, "run", fake_tool_loop_run)
    monkeypatch.setattr(provider_manager, "chat", fail_direct_chat)

    response = await chat_service.chat(
        build_request(tools_enabled=True),
    )

    assert response.content == "(25 + 5) ? 8 = 240?"
    assert response.usage.total_tokens == 30
    assert calls["tool_loop"]["provider"] == "ollama"
    assert calls["tool_loop"]["model"] == "qwen3:4b"
    assert calls["tool_loop"]["messages"][0]["role"] == "user"


@pytest.mark.asyncio
async def test_chat_skips_tool_loop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    async def fail_tool_loop(**_: Any) -> dict[str, Any]:
        raise AssertionError(
            "tool_loop.run must not run when tools are disabled.",
        )

    async def fake_direct_chat(**kwargs: Any) -> dict[str, Any]:
        calls["direct_chat"] = kwargs

        return {
            "provider": "ollama",
            "model": "qwen3:4b",
            "role": "assistant",
            "content": "?????",
            "thinking": None,
            "tool_calls": [],
            "done": True,
            "done_reason": "stop",
            "usage": {
                "prompt_tokens": 8,
                "completion_tokens": 4,
                "total_tokens": 12,
            },
        }

    monkeypatch.setattr(tool_loop, "run", fail_tool_loop)
    monkeypatch.setattr(provider_manager, "chat", fake_direct_chat)

    response = await chat_service.chat(
        build_request(tools_enabled=False),
    )

    assert response.content == "?????"
    assert response.usage.total_tokens == 12
    assert calls["direct_chat"]["provider"] == "ollama"
    assert calls["direct_chat"]["model"] == "qwen3:4b"
