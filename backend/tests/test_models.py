from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.providers.manager import provider_manager

client = TestClient(app)


async def discovered_models(_: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "local-chat:latest",
            "size": 2_000_000_000,
            "details": {
                "family": "local",
                "parameter_size": "3B",
                "quantization_level": "Q4_K_M",
            },
            "capabilities": ["completion", "tools"],
        },
        {
            "name": "remote-chat:cloud",
            "remote_model": "remote-chat",
            "remote_host": "https://example.invalid",
            "size": 300,
            "details": {"parameter_size": "100B"},
            "capabilities": ["completion"],
        },
    ]


def test_models_report_provider_locality(monkeypatch: Any) -> None:
    monkeypatch.setattr(provider_manager, "list_models", discovered_models)

    response = client.get("/api/models")

    assert response.status_code == 200
    assert [(item["name"], item["local"]) for item in response.json()["items"]] == [
        ("local-chat:latest", True),
        ("remote-chat:cloud", False),
    ]


def test_models_can_be_limited_to_local_discovery(monkeypatch: Any) -> None:
    monkeypatch.setattr(provider_manager, "list_models", discovered_models)

    response = client.get("/api/models", params={"local_only": "true"})

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "provider": "ollama",
                "provider_label": "Ollama",
                "name": "local-chat:latest",
                "local": True,
                "family": "local",
                "parameter_size": "3B",
                "quantization": "Q4_K_M",
                "context_length": None,
                "embedding_length": None,
                "capabilities": ["completion", "tools"],
            },
        ],
        "total": 1,
    }
