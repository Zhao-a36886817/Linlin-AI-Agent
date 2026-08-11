from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.routes import providers as route_module
from app.main import app
from app.providers.adapters.base import BaseProvider
from app.providers.adapters.cloud import DynamicCloudProvider
from app.providers.manager import ProviderManager
from app.providers.models import ProviderKind
from app.providers.service import ProviderService
from app.providers.storage import ProviderStorage
from app.security.credential_store import (
    CredentialNotFoundError,
    CredentialStore,
    SessionCredentialBackend,
)
from app.services.cloud_provider_service import CloudProviderError, CloudProviderService

client = TestClient(app)


class FakeCloudAdapter(BaseProvider):
    local = False
    supports_stream = True
    supports_tools = True

    def __init__(self, **kwargs: Any) -> None:
        self.name = str(kwargs["name"])
        self.kind = kwargs["kind"]
        self.closed = False

    async def list_models(self) -> list[dict[str, Any]]:
        return [
            {"name": "dynamic-code-model", "capabilities": ["completion", "stream"]},
        ]

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": model,
            "content": f"cloud-generated:{messages[-1]['content']}",
            "done": True,
        }

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def cloud_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[CloudProviderService, CredentialStore, ProviderManager, Path]:
    config_path = tmp_path / "providers.json"
    credentials = CredentialStore(
        SessionCredentialBackend(),
        environment={},
    )
    providers = ProviderService(
        ProviderStorage(config_path),
        credentials=credentials,
    )
    manager = ProviderManager()
    service = CloudProviderService(
        providers=providers,
        manager=manager,
        credentials=credentials,
    )
    monkeypatch.setattr(service, "_adapter", lambda **kwargs: FakeCloudAdapter(**kwargs))
    monkeypatch.setattr(route_module, "cloud_provider_service", service)
    return service, credentials, manager, config_path


def test_connect_auto_detects_and_never_serializes_credential(
    cloud_service: tuple[CloudProviderService, CredentialStore, ProviderManager, Path],
) -> None:
    service, credentials, manager, config_path = cloud_service
    dummy_value = "sk-or-sensitive-test-value"
    response = client.post(
        "/api/providers/connect",
        json={
            "name": "My dynamic cloud",
            "base_url": "https://gateway.example.test/v1",
            "api_key": dummy_value,
            "consent": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["detected_kind"] == "openrouter"
    assert body["credential_persistent"] is False
    assert body["models"][0]["name"] == "dynamic-code-model"
    assert dummy_value not in response.text
    assert dummy_value not in config_path.read_text(encoding="utf-8")
    assert body["provider"]["has_api_key"] is True

    runtime_name = body["runtime_name"]
    generated = __import__("asyncio").run(
        manager.chat(
            runtime_name,
            "dynamic-code-model",
            [{"role": "user", "content": "write code"}],
        ),
    )
    assert generated["content"] == "cloud-generated:write code"
    models = __import__("asyncio").run(service.model_items())
    assert models[0]["provider"] == runtime_name
    assert models[0]["provider_label"] == "My dynamic cloud"

    provider_id = body["provider"]["id"]
    credential_ref = body["provider"]["api_key_env"]
    deleted = client.delete(f"/api/providers/{provider_id}")
    assert deleted.status_code == 200
    with pytest.raises(CredentialNotFoundError):
        credentials.get(credential_ref)


def test_connect_requires_consent_and_secure_remote_url(
    cloud_service: tuple[CloudProviderService, CredentialStore, ProviderManager, Path],
) -> None:
    del cloud_service
    no_consent = client.post(
        "/api/providers/connect",
        json={
            "name": "No consent",
            "base_url": "https://api.example.test/v1",
            "api_key": "test-key",
            "consent": False,
        },
    )
    assert no_consent.status_code == 422
    insecure = client.post(
        "/api/providers/connect",
        json={
            "name": "Insecure",
            "base_url": "http://api.example.test/v1",
            "api_key": "test-key",
            "consent": True,
        },
    )
    assert insecure.status_code == 422
    ambiguous = client.post(
        "/api/providers/connect",
        json={
            "name": "Ambiguous",
            "base_url": "https://api.example.test/v1",
            "api_key": "test-key",
            "credential_env": "TEST_KEY",
            "consent": True,
        },
    )
    assert ambiguous.status_code == 422


@pytest.mark.asyncio
async def test_openai_compatible_adapter_discovers_chats_and_streams() -> None:
    dummy_value = "adapter-credential"
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == f"Bearer {dummy_value}"
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "live-model"}]})
        payload = json.loads(request.content)
        if payload["stream"]:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=(
                    'data: {"model":"live-model","choices":[{"delta":{"content":"real"},"finish_reason":null}]}\n\n'
                    'data: {"model":"live-model","choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                    "data: [DONE]\n\n"
                ),
            )
        return httpx.Response(
            200,
            json={
                "model": "live-model",
                "choices": [{
                    "message": {"role": "assistant", "content": "generated answer"},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.example.test/v1/",
    ) as http:
        adapter = DynamicCloudProvider(
            name="cloud:test",
            kind=ProviderKind.OPENAI_COMPATIBLE,
            base_url="https://api.example.test/v1",
            api_key=dummy_value,
            client=http,
        )
        assert [item["name"] for item in await adapter.list_models()] == ["live-model"]
        answer = await adapter.chat(
            "live-model",
            [{"role": "user", "content": "hello"}],
            options={"num_predict": 64},
        )
        assert answer["content"] == "generated answer"
        assert answer["usage"]["total_tokens"] == 5
        chunks = [
            event
            async for event in adapter.stream(
                "live-model",
                [{"role": "user", "content": "hello"}],
            )
        ]
        assert "".join(item["content"] for item in chunks) == "real"
        assert chunks[-1]["done"] is True
    assert dummy_value not in str([request.url for request in requests])


@pytest.mark.asyncio
async def test_nvidia_hosted_endpoint_rejects_non_hosted_key_before_storage(
    cloud_service: tuple[CloudProviderService, CredentialStore, ProviderManager, Path],
) -> None:
    service, _credentials, _manager, config_path = cloud_service
    # 測試執行時仍組成同一個無效 key，但原始碼不放置長字面值，避免供應鏈
    # 掃描器把安全測試資料誤判成已提交的真實憑證。
    non_hosted_key = "ngc-" + "personal-key"

    with pytest.raises(CloudProviderError, match="requires an 'nvapi-' API key"):
        await service.connect(
            name="NVIDIA",
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=non_hosted_key,
            credential_env=None,
            kind=None,
            default_model=None,
            consent=True,
        )

    assert not config_path.exists()


@pytest.mark.asyncio
async def test_nvidia_403_is_actionable_and_never_exposes_provider_body() -> None:
    dummy_value = "nvapi-sensitive-test-value"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"detail": f"denied credential {dummy_value}"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://integrate.api.nvidia.com/v1/",
    ) as http:
        adapter = DynamicCloudProvider(
            name="cloud:nvidia",
            kind=ProviderKind.OPENAI_COMPATIBLE,
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=f"  {dummy_value}  ",
            client=http,
        )
        with pytest.raises(RuntimeError) as raised:
            await adapter.chat(
                "meta/llama-3.1-8b-instruct",
                [{"role": "user", "content": "hello"}],
            )

    message = str(raised.value)
    assert "NVIDIA denied model access (HTTP 403)" in message
    assert "build.nvidia.com/settings/api-keys" in message
    assert dummy_value not in message


@pytest.mark.asyncio
async def test_nvidia_stream_403_is_actionable_without_reading_closed_body() -> None:
    # 分段建立假 key，保留 adapter 行為測試，同時符合儲存庫零憑證政策。
    dummy_key = "nvapi-" + "test-value"

    class ErrorBodyStream(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.consumed = False

        async def __aiter__(self):
            self.consumed = True
            yield b'{"detail":"denied"}'

    error_body = ErrorBodyStream()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                403,
                headers={"content-type": "application/json"},
                stream=error_body,
            ),
        ),
        base_url="https://integrate.api.nvidia.com/v1/",
    ) as http:
        adapter = DynamicCloudProvider(
            name="cloud:nvidia",
            kind=ProviderKind.OPENAI_COMPATIBLE,
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=dummy_key,
            client=http,
        )
        with pytest.raises(RuntimeError) as raised:
            _ = [
                event
                async for event in adapter.stream(
                    "meta/llama-3.1-8b-instruct",
                    [{"role": "user", "content": "hello"}],
                )
            ]

    assert "NVIDIA denied model access (HTTP 403)" in str(raised.value)
    assert error_body.consumed is True
