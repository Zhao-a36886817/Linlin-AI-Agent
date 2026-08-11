from __future__ import annotations

import time
from pathlib import Path
from threading import Event
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.routes import training as route_module
from app.main import app
from app.services.cloud_provider_service import CloudTrainingConnection
from app.training.local_lora import LocalTrainingCancelled
from app.training.models import TrainingMessage
from app.training.service import TrainingService

client = TestClient(app)


class FakeCloudTraining:
    def __init__(self) -> None:
        self.key = "test-" + "credential-fragment"

    async def training_model_items(self) -> list[dict[str, Any]]:
        return [{
            "engine": "openai_compatible",
            "provider": "cloud:11111111-1111-1111-1111-111111111111",
            "provider_label": "Training Cloud",
            "model": "eligible-model",
            "local": False,
        }]

    async def training_connection(self, runtime_name: str) -> CloudTrainingConnection:
        assert runtime_name == "cloud:11111111-1111-1111-1111-111111111111"
        return CloudTrainingConnection(
            runtime_name=runtime_name,
            label="Training Cloud",
            kind=__import__("app.providers.models", fromlist=["ProviderKind"]).ProviderKind.OPENAI,
            base_url="https://training.example.test/v1",
            api_key=self.key,
        )


@pytest.fixture
def training_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[TrainingService, FakeCloudTraining, list[httpx.Request]]:
    cloud = FakeCloudTraining()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == f"Bearer {cloud.key}"
        path = request.url.path
        if path == "/v1/files" and request.method == "POST":
            assert b'"messages"' in request.content
            assert cloud.key.encode() not in request.content
            return httpx.Response(200, json={"id": "file-training"})
        if path == "/v1/files/file-training" and request.method == "DELETE":
            return httpx.Response(200, json={"deleted": True})
        if path == "/v1/fine_tuning/jobs" and request.method == "POST":
            return httpx.Response(200, json={"id": "ft-job", "status": "queued"})
        if path == "/v1/fine_tuning/jobs/ft-job" and request.method == "GET":
            return httpx.Response(200, json={"id": "ft-job", "status": "running"})
        if path == "/v1/fine_tuning/jobs/ft-job/checkpoints" and request.method == "GET":
            return httpx.Response(200, json={"data": [
                {"step_number": 1, "metrics": {"train_loss": 1.25, "valid_loss": 1.4}},
                {"step_number": 2, "metrics": {"train_loss": 0.8, "valid_loss": 1.0}},
            ]})
        if path == "/v1/fine_tuning/jobs/ft-job/cancel" and request.method == "POST":
            return httpx.Response(200, json={"id": "ft-job", "status": "cancelled"})
        raise AssertionError(f"Unexpected training request: {request.method} {path}")

    service = TrainingService(
        cloud=cloud,  # type: ignore[arg-type]
        transport=httpx.MockTransport(handler),
        model_root=tmp_path / "models",
        output_root=tmp_path / "outputs",
    )
    monkeypatch.setattr(route_module, "training_service", service)
    return service, cloud, requests


def payload(*, consent: bool = True) -> dict[str, Any]:
    return {
        "conversation_id": "conversation-1",
        "provider": "cloud:11111111-1111-1111-1111-111111111111",
        "model": "eligible-model",
        "messages": [
            {"role": "user", "content": "Question one"},
            {"role": "assistant", "content": "Answer one"},
            {"role": "user", "content": "Question two"},
            {"role": "assistant", "content": "Answer two"},
        ],
        "cloud_consent": consent,
    }


def test_capabilities_are_truthful_and_never_return_credentials(
    training_runtime: tuple[TrainingService, FakeCloudTraining, list[httpx.Request]],
) -> None:
    _, cloud, _ = training_runtime
    response = client.get("/api/training/capabilities")
    assert response.status_code == 200
    document = response.json()
    assert document["models"][0]["model"] == "eligible-model"
    assert document["models"][0]["local"] is False
    assert document["local"]["available"] is False
    assert document["polling_interval_seconds"] == 2
    assert cloud.key not in response.text


def test_training_requires_consent_and_complete_conversation(
    training_runtime: tuple[TrainingService, FakeCloudTraining, list[httpx.Request]],
) -> None:
    _, _, requests = training_runtime
    response = client.post("/api/training/jobs", json=payload(consent=False))
    assert response.status_code == 422
    assert "consent" in response.text
    assert requests == []

    incomplete = payload()
    incomplete["messages"] = [{"role": "user", "content": "Only a question"}]
    assert client.post("/api/training/jobs", json=incomplete).status_code == 422
    assert requests == []


def test_real_provider_job_metrics_cancel_and_conversation_isolation(
    training_runtime: tuple[TrainingService, FakeCloudTraining, list[httpx.Request]],
) -> None:
    _, cloud, requests = training_runtime
    created = client.post("/api/training/jobs", json=payload())
    assert created.status_code == 201
    job = created.json()
    assert job["status"] == "queued"
    assert job["examples"] == 2
    assert cloud.key not in created.text

    hidden = client.get("/api/training/jobs", params={"conversation_id": "conversation-2"})
    assert hidden.status_code == 200
    assert hidden.json() == []

    refreshed = client.get("/api/training/jobs", params={"conversation_id": "conversation-1"})
    assert refreshed.status_code == 200
    current = refreshed.json()[0]
    assert current["status"] == "running"
    assert current["metrics"] == [
        {"step": 1, "train_loss": 1.25, "valid_loss": 1.4},
        {"step": 2, "train_loss": 0.8, "valid_loss": 1.0},
    ]

    denied = client.post(
        f"/api/training/jobs/{job['id']}/cancel",
        params={"conversation_id": "conversation-2"},
    )
    assert denied.status_code == 404
    cancelled = client.post(
        f"/api/training/jobs/{job['id']}/cancel",
        params={"conversation_id": "conversation-1"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert any(request.url.path.endswith("/cancel") for request in requests)


def test_provider_error_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud = FakeCloudTraining()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": cloud.key}})

    service = TrainingService(cloud=cloud, transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    monkeypatch.setattr(route_module, "training_service", service)
    response = client.post("/api/training/jobs", json=payload())
    assert response.status_code == 422
    assert "HTTP 401" in response.text
    assert cloud.key not in response.text


class FakeLocalRunner:
    def missing_packages(self) -> list[str]:
        return []

    def run(
        self,
        *,
        model_path: Path,
        output_path: Path,
        messages: list[TrainingMessage],
        max_steps: int,
        cancelled: Event,
        progress,
    ) -> None:
        assert model_path.name == "tiny-model"
        assert len(messages) == 4
        assert max_steps == 3
        assert not cancelled.is_set()
        output_path.mkdir(parents=True)
        (output_path / "adapter").mkdir()
        progress(1, 1.2)
        progress(2, 0.7)


class BlockingLocalRunner(FakeLocalRunner):
    def run(self, *, cancelled: Event, **kwargs) -> None:
        while not cancelled.wait(0.01):
            kwargs["progress"](1, 1.0)
        raise LocalTrainingCancelled("cancelled")


def register_tiny_model(root: Path) -> None:
    model = root / "tiny-model"
    model.mkdir(parents=True)
    (model / "config.json").write_text("{}", encoding="utf-8")
    (model / "tokenizer.json").write_text("{}", encoding="utf-8")
    (model / "model.safetensors").write_bytes(b"weights")


def local_payload(*, consent: bool = True, model: str = "tiny-model") -> dict[str, Any]:
    document = payload(consent=False)
    document.update({
        "engine": "local_lora",
        "provider": "local:lora",
        "model": model,
        "local_consent": consent,
        "max_steps": 3,
    })
    return document


def test_local_lora_discovery_real_metrics_and_bounded_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_root = tmp_path / "models"
    output_root = tmp_path / "outputs" / "training"
    register_tiny_model(model_root)
    service = TrainingService(
        cloud=FakeCloudTraining(),
        local_runner=FakeLocalRunner(),
        model_root=model_root,
        output_root=output_root,
    )
    monkeypatch.setattr(route_module, "training_service", service)

    capabilities = client.get("/api/training/capabilities").json()
    local = next(item for item in capabilities["models"] if item["local"])
    assert local["model"] == "tiny-model"
    assert local["engine"] == "local_lora"
    assert capabilities["local"]["available"] is True

    created = client.post("/api/training/jobs", json=local_payload())
    assert created.status_code == 201
    job = created.json()
    deadline = time.monotonic() + 2
    current = job
    while current["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        current = client.get(
            "/api/training/jobs",
            params={"conversation_id": "conversation-1"},
        ).json()[0]
    assert current["status"] == "succeeded"
    assert current["metrics"] == [
        {"step": 1, "train_loss": 1.2, "valid_loss": None},
        {"step": 2, "train_loss": 0.7, "valid_loss": None},
    ]
    assert current["trained_model"].endswith("/adapter")
    adapter = output_root / current["trained_model"]
    assert adapter.is_dir()
    assert adapter.resolve().is_relative_to(output_root.resolve())


def test_local_lora_rejects_missing_consent_and_unregistered_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_root = tmp_path / "models"
    register_tiny_model(model_root)
    service = TrainingService(
        cloud=FakeCloudTraining(),
        local_runner=FakeLocalRunner(),
        model_root=model_root,
        output_root=tmp_path / "outputs",
    )
    monkeypatch.setattr(route_module, "training_service", service)

    denied = client.post("/api/training/jobs", json=local_payload(consent=False))
    assert denied.status_code == 422
    assert "consent" in denied.text
    escaped = client.post("/api/training/jobs", json=local_payload(model="../outside"))
    assert escaped.status_code == 422
    assert "registered" in escaped.text


def test_local_lora_is_cancellable_and_conversation_isolated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_root = tmp_path / "models"
    register_tiny_model(model_root)
    service = TrainingService(
        cloud=FakeCloudTraining(),
        local_runner=BlockingLocalRunner(),
        model_root=model_root,
        output_root=tmp_path / "outputs",
    )
    monkeypatch.setattr(route_module, "training_service", service)
    job = client.post("/api/training/jobs", json=local_payload()).json()

    hidden = client.get(
        "/api/training/jobs",
        params={"conversation_id": "another-conversation"},
    )
    assert hidden.json() == []
    denied = client.post(
        f"/api/training/jobs/{job['id']}/cancel",
        params={"conversation_id": "another-conversation"},
    )
    assert denied.status_code == 404
    cancelled = client.post(
        f"/api/training/jobs/{job['id']}/cancel",
        params={"conversation_id": "conversation-1"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
