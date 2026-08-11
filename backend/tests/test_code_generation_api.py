from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import code_generation as route_module
from app.core.config import Settings
from app.main import app
from app.services.code_generation_service import (
    CodeGenerationError,
    CodeGenerationService,
)

client = TestClient(app)


class FakeProvider:
    def __init__(self, *, local: bool) -> None:
        self.local = local


class FakeManager:
    def __init__(self, *, local: bool = True) -> None:
        self.instance = FakeProvider(local=local)
        self.response = json.dumps({
            "summary": "Adds a typed greeting function.",
            "content": "def greet(name: str) -> str:\n    return f\"Hello, {name}!\"\n",
        })
        self.calls: list[dict[str, Any]] = []

    def provider(self, _: str) -> FakeProvider:
        return self.instance

    async def chat(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"provider": kwargs["provider"], "model": kwargs["model"], "content": self.response}


@pytest.fixture
def code_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[CodeGenerationService, FakeManager, Path]:
    workspace = tmp_path / "workspace"
    settings = Settings(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        output_root=tmp_path / "outputs",
        log_root=tmp_path / "logs",
    )
    manager = FakeManager()
    service = CodeGenerationService(settings=settings, manager=manager)
    monkeypatch.setattr(route_module, "code_generation_service", service)
    return service, manager, workspace


def test_generated_python_is_previewed_then_explicitly_applied(
    code_service: tuple[CodeGenerationService, FakeManager, Path],
) -> None:
    _, manager, workspace = code_service
    target = workspace / "src" / "greeting.py"
    response = client.post(
        "/api/code-generation/proposals",
        json={
            "provider": "ollama",
            "model": "dynamic-local-model",
            "instruction": "Create a typed greeting function",
            "target_path": "src/greeting.py",
            "context_paths": [],
            "cloud_consent": False,
        },
    )
    assert response.status_code == 201
    proposal = response.json()
    assert proposal["status"] == "pending"
    assert "+def greet(name: str) -> str:" in proposal["diff"]
    assert not target.exists()
    ast.parse(proposal["content"])
    assert manager.calls[0]["provider"] == "ollama"
    assert manager.calls[0]["model"] == "dynamic-local-model"

    refused = client.post(
        f"/api/code-generation/proposals/{proposal['id']}/apply",
        json={"confirmation": "yes", "consent": True},
    )
    assert refused.status_code == 422
    applied = client.post(
        f"/api/code-generation/proposals/{proposal['id']}/apply",
        json={"confirmation": "APPLY CODE", "consent": True},
    )
    assert applied.status_code == 200
    assert applied.json()["status"] == "applied"
    assert target.read_text(encoding="utf-8") == proposal["content"]


@pytest.mark.asyncio
async def test_workspace_escape_and_protected_targets_are_rejected(
    code_service: tuple[CodeGenerationService, FakeManager, Path],
) -> None:
    service, _, _ = code_service
    common = {
        "provider": "ollama",
        "model": "local",
        "instruction": "write code",
        "context_paths": [],
        "cloud_consent": False,
    }
    with pytest.raises(Exception, match="outside workspace"):
        await service.propose(target_path="../escape.py", **common)
    with pytest.raises(CodeGenerationError, match="credential"):
        await service.propose(target_path=".env", **common)
    with pytest.raises(CodeGenerationError, match="protected"):
        await service.propose(target_path=".git/hook.py", **common)


@pytest.mark.asyncio
async def test_cloud_context_requires_consent_and_target_race_is_blocked(
    code_service: tuple[CodeGenerationService, FakeManager, Path],
) -> None:
    service, manager, workspace = code_service
    manager.instance.local = False
    target = workspace / "existing.py"
    target.write_text("value = 1\n", encoding="utf-8")
    with pytest.raises(CodeGenerationError, match="cloud consent"):
        await service.propose(
            provider="cloud:configured",
            model="dynamic-cloud-model",
            instruction="change the greeting",
            target_path="existing.py",
            context_paths=[],
            cloud_consent=False,
        )
    proposal = await service.propose(
        provider="cloud:configured",
        model="dynamic-cloud-model",
        instruction="change the greeting",
        target_path="existing.py",
        context_paths=[],
        cloud_consent=True,
    )
    assert "value = 1" in manager.calls[-1]["messages"][-1]["content"]
    target.write_text("value = 2\n", encoding="utf-8")
    with pytest.raises(CodeGenerationError, match="changed after preview"):
        service.apply(
            __import__("uuid").UUID(proposal["id"]),
            confirmation="APPLY CODE",
            consent=True,
        )


@pytest.mark.asyncio
async def test_invalid_generated_python_never_becomes_a_proposal(
    code_service: tuple[CodeGenerationService, FakeManager, Path],
) -> None:
    service, manager, _ = code_service
    manager.response = "```python\ndef broken(:\n    pass\n```"
    with pytest.raises(CodeGenerationError, match="syntax validation"):
        await service.propose(
            provider="ollama",
            model="local",
            instruction="generate invalid code",
            target_path="broken.py",
            context_paths=[],
            cloud_consent=False,
        )
    assert service.list_proposals() == []


@pytest.mark.asyncio
async def test_triple_quoted_model_wrapper_yields_actual_python_file(
    code_service: tuple[CodeGenerationService, FakeManager, Path],
) -> None:
    service, manager, _ = code_service
    manager.response = '''```json
{
  "content": """
def add(a: int, b: int) -> int:
    return a + b
""",
  "summary": "Adds two integers."
}
```'''

    proposal = await service.propose(
        provider="ollama",
        model="local",
        instruction="create a typed add function",
        target_path="generated/add.py",
        context_paths=[],
        cloud_consent=False,
    )

    assert proposal["content"].lstrip().startswith("def add(")
    assert '"content"' not in proposal["content"]
    tree = ast.parse(proposal["content"])
    assert any(isinstance(node, ast.FunctionDef) and node.name == "add" for node in tree.body)


@pytest.mark.asyncio
async def test_ambiguous_structured_wrapper_is_rejected(
    code_service: tuple[CodeGenerationService, FakeManager, Path],
) -> None:
    service, manager, _ = code_service
    manager.response = '{"content": "value = 1\\n", "files": ["other.py"]}'

    with pytest.raises(CodeGenerationError, match="unsupported structured wrapper"):
        await service.propose(
            provider="ollama",
            model="local",
            instruction="generate one file",
            target_path="generated/value.py",
            context_paths=[],
            cloud_consent=False,
        )
    assert service.list_proposals() == []


@pytest.mark.asyncio
async def test_generated_hard_coded_credential_is_rejected(
    code_service: tuple[CodeGenerationService, FakeManager, Path],
) -> None:
    service, manager, _ = code_service
    manager.response = "api_" + 'key = "not-a-real-' + 'credential-value"\n'
    with pytest.raises(CodeGenerationError, match="hard-coded credential"):
        await service.propose(
            provider="ollama",
            model="local",
            instruction="do not hardcode credentials",
            target_path="unsafe.py",
            context_paths=[],
            cloud_consent=False,
        )
