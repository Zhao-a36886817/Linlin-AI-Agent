from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.routes import advanced_runtime as route_module
from app.core.config import Settings
from app.main import app
from app.services import advanced_runtime as service_module
from app.services.advanced_runtime import AdvancedRuntimeService, McpHttpTransport

client = TestClient(app)


class FakeProvider:
    local = True
    supports_embeddings = True

    async def embeddings(
        self,
        model: str,
        inputs: list[str],
        **_: Any,
    ) -> list[list[float]]:
        del model
        return [[float(text.lower().count("alpha") + 1), 1.0] for text in inputs]


class FakeManager:
    def __init__(self) -> None:
        self.instance = FakeProvider()
        self.calls: list[tuple[str, str]] = []

    def provider(self, _: str) -> FakeProvider:
        return self.instance

    async def chat(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        self.calls.append((provider, model))
        return {
            "provider": provider,
            "model": model,
            "content": f"generated:{messages[-1]['content']}",
            "usage": {"completion_tokens": 1},
        }


@pytest.fixture
def runtime_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AdvancedRuntimeService:
    settings = Settings(
        workspace_root=tmp_path / "workspace",
        data_root=tmp_path / "data",
        output_root=tmp_path / "outputs",
        log_root=tmp_path / "logs",
    )
    service = AdvancedRuntimeService(settings=settings, manager=FakeManager())
    monkeypatch.setattr(route_module, "advanced_runtime_service", service)
    return service


def test_rag_ingests_workspace_files_and_returns_citations(
    runtime_service: AdvancedRuntimeService,
) -> None:
    (runtime_service.settings.workspace_root / "facts.txt").write_text(
        "alpha facts",
        encoding="utf-8",
    )
    configured = client.put(
        "/api/advanced-runtime/rag",
        json={"enabled": True, "provider": "ollama", "model": "embed"},
    )
    assert configured.status_code == 200
    assert client.post(
        "/api/advanced-runtime/rag/ingest",
        json={"path": "facts.txt", "consent": True},
    ).json()["added"] == 1
    results = client.post(
        "/api/advanced-runtime/rag/search",
        json={"query": "alpha", "limit": 3},
    ).json()
    assert results[0]["citation"]["source"] == "facts.txt"

    escaped = client.post(
        "/api/advanced-runtime/rag/ingest",
        json={"path": "../outside.txt", "consent": True},
    )
    assert escaped.status_code == 422


def test_mcp_requires_consent_loopback_and_tool_runtime(
    runtime_service: AdvancedRuntimeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rejected = client.post(
        "/api/advanced-runtime/mcp/connect",
        json={
            "server_id": "local",
            "endpoint": "https://example.com/mcp",
            "consent": True,
        },
    )
    assert rejected.status_code == 422
    no_consent = client.post(
        "/api/advanced-runtime/mcp/connect",
        json={
            "server_id": "local",
            "endpoint": "http://127.0.0.1:3001/mcp",
            "consent": False,
        },
    )
    assert no_consent.status_code == 422

    class FakeTransport:
        async def list_tools(self) -> list[dict[str, Any]]:
            return [{
                "name": "local_calc",
                "description": "Local calculation",
                "inputSchema": {"type": "object", "properties": {}},
            }]

        async def call_tool(
            self,
            name: str,
            arguments: dict[str, Any],
        ) -> dict[str, Any]:
            return {"name": name, "arguments": arguments, "real": True}

        async def close(self) -> None:
            return None

    monkeypatch.setattr(service_module, "McpHttpTransport", lambda _: FakeTransport())
    connected = client.post(
        "/api/advanced-runtime/mcp/connect",
        json={
            "server_id": "local",
            "endpoint": "http://127.0.0.1:3001/mcp",
            "consent": True,
        },
    )
    assert connected.status_code == 200
    invoked = client.post(
        "/api/advanced-runtime/mcp/invoke",
        json={"name": "local_calc", "arguments": {"value": 3}},
    )
    assert invoked.json() == {
        "name": "local_calc",
        "arguments": {"value": 3},
        "real": True,
    }


def test_streamable_http_transport_handles_mcp_session() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content)
        methods.append(body["method"])
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        if body["method"] == "initialize":
            return httpx.Response(
                200,
                headers={"mcp-session-id": "session-1"},
                json={"jsonrpc": "2.0", "id": body["id"], "result": {}},
            )
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {"tools": []},
            },
        )

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            transport = McpHttpTransport("http://localhost:3001/mcp", client=http)
            assert await transport.list_tools() == []

    import asyncio

    asyncio.run(exercise())
    assert methods == ["initialize", "notifications/initialized", "tools/list"]


def test_multi_agent_run_is_bounded_and_cancelable(
    runtime_service: AdvancedRuntimeService,
) -> None:
    started = client.post(
        "/api/advanced-runtime/orchestration/runs",
        json={
            "provider": "ollama",
            "model": "local-model",
            "task": "Analyze this",
            "iterations": 4,
            "cost_units": 100,
        },
    )
    assert started.status_code == 202
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        runs = client.get("/api/advanced-runtime/orchestration/runs").json()
        if runs[0]["status"] == "completed":
            break
        time.sleep(0.01)
    assert runs[0]["output"]["analysis"].startswith("generated:")
    assert runs[0]["output"]["review"].startswith("generated:")


def test_scheduler_uses_only_approved_consented_chat_action(
    runtime_service: AdvancedRuntimeService,
) -> None:
    wrong = client.put(
        "/api/advanced-runtime/scheduler",
        json={"enabled": True, "confirmation": "yes"},
    )
    assert wrong.status_code == 422
    enabled = client.put(
        "/api/advanced-runtime/scheduler",
        json={"enabled": True, "confirmation": "ENABLE SCHEDULER"},
    )
    assert enabled.status_code == 200
    job = client.post(
        "/api/advanced-runtime/scheduler/jobs",
        json={
            "provider": "ollama",
            "model": "local-model",
            "prompt": "scheduled work",
            "run_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
            "consent": True,
        },
    )
    assert job.status_code == 201
    completed = client.post("/api/advanced-runtime/scheduler/tick").json()
    assert completed["completed"] == [job.json()["id"]]
    state = client.get("/api/advanced-runtime/scheduler/jobs").json()
    assert state["jobs"][0]["status"] == "completed"
    assert state["results"][job.json()["id"]]["content"].startswith("generated:")
