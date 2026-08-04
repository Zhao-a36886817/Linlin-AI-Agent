from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.chat import ChatStreamEvent
from app.services.chat_service import chat_service

client = TestClient(app)


async def fake_stream(_: Any) -> AsyncIterator[ChatStreamEvent]:
    yield ChatStreamEvent(
        provider="ollama",
        model="llama3.2:3b",
        content="你",
        done=False,
    )

    yield ChatStreamEvent(
        provider="ollama",
        model="llama3.2:3b",
        content="好",
        done=False,
    )

    yield ChatStreamEvent(
        provider="ollama",
        model="llama3.2:3b",
        content="",
        done=True,
        done_reason="stop",
    )


def test_chat_stream_api(monkeypatch: Any) -> None:
    monkeypatch.setattr(chat_service, "stream", fake_stream)

    with client.stream(
        "POST",
        "/api/chat/stream",
        json={
            "provider": "ollama",
            "model": "llama3.2:3b",
            "messages": [
                {
                    "role": "user",
                    "content": "你好",
                },
            ],
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            "text/event-stream",
        )

        body = "".join(response.iter_text())

    assert "event: message" in body
    assert "event: done" in body
    assert '"content": "你"' in body
    assert '"content": "好"' in body


def test_chat_stream_rejects_invalid_request() -> None:
    response = client.post(
        "/api/chat/stream",
        json={
            "provider": "ollama",
            "model": "llama3.2:3b",
            "messages": [],
        },
    )

    assert response.status_code == 422
