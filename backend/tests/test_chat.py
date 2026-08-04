from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.services.chat_service import chat_service

client = TestClient(app)


async def fake_chat(_: Any) -> dict[str, Any]:
    return {
        "provider": "ollama",
        "model": "llama3.2:3b",
        "role": "assistant",
        "content": "你好，我是 Linlin Agent。",
        "thinking": None,
        "tool_calls": [],
        "done": True,
        "done_reason": "stop",
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 10,
            "total_tokens": 15,
        },
    }


def test_chat_api(monkeypatch: Any) -> None:
    monkeypatch.setattr(chat_service, "chat", fake_chat)

    response = client.post(
        "/api/chat",
        json={
            "provider": "ollama",
            "model": "llama3.2:3b",
            "messages": [
                {
                    "role": "user",
                    "content": "你好",
                },
            ],
            "options": {
                "temperature": 0.3,
                "max_tokens": 100,
            },
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["provider"] == "ollama"
    assert body["model"] == "llama3.2:3b"
    assert body["content"] == "你好，我是 Linlin Agent。"
    assert body["usage"]["total_tokens"] == 15


def test_chat_rejects_empty_messages() -> None:
    response = client.post(
        "/api/chat",
        json={
            "provider": "ollama",
            "model": "qwen3:4b",
            "messages": [],
        },
    )

    assert response.status_code == 422


def test_chat_rejects_blank_content() -> None:
    response = client.post(
        "/api/chat",
        json={
            "provider": "ollama",
            "model": "qwen3:4b",
            "messages": [
                {
                    "role": "user",
                    "content": "   ",
                },
            ],
        },
    )

    assert response.status_code == 422
