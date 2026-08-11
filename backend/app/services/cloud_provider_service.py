from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from app.providers.adapters.cloud import DynamicCloudProvider
from app.providers.manager import ProviderManager, provider_manager
from app.providers.models import (
    ProviderCostClass,
    ProviderCreate,
    ProviderKind,
)
from app.providers.service import ProviderService, provider_service
from app.security.credential_store import (
    CredentialNotFoundError,
    CredentialStore,
    credential_store,
)


class CloudProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class CloudTrainingConnection:
    runtime_name: str
    label: str
    kind: ProviderKind
    base_url: str
    api_key: str = field(repr=False)
    timeout: int = 120


class CloudProviderService:
    """Activates configured cloud adapters without persisting raw credentials."""

    def __init__(
        self,
        *,
        providers: ProviderService | None = None,
        manager: ProviderManager | None = None,
        credentials: CredentialStore | None = None,
    ) -> None:
        self.providers = providers or provider_service
        self.manager = manager or provider_manager
        self.credentials = credentials or credential_store
        self._models: dict[UUID, list[dict[str, Any]]] = {}

    @staticmethod
    def runtime_name(provider_id: UUID) -> str:
        return f"cloud:{provider_id}"

    async def initialize(self) -> None:
        for config in await self.providers.list_configs():
            if not config.enabled or not config.base_url or not config.api_key_env:
                continue
            try:
                key = self.credentials.get(config.api_key_env)
                self.manager.register(
                    self.runtime_name(config.id),
                    self._adapter(
                        name=self.runtime_name(config.id),
                        kind=config.kind,
                        base_url=config.base_url,
                        api_key=key,
                        timeout=config.timeout_seconds,
                    ),
                )
            except (CredentialNotFoundError, RuntimeError, TypeError, ValueError):
                continue

    async def connect(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str | None,
        credential_env: str | None,
        kind: ProviderKind | None,
        default_model: str | None,
        consent: bool,
    ) -> dict[str, Any]:
        if not consent:
            raise CloudProviderError("Explicit cloud data-transfer consent is required.")
        endpoint = self.validate_endpoint(base_url)
        if api_key:
            secret = api_key.strip()
        elif credential_env:
            secret = self.credentials.get(credential_env).strip()
        else:
            raise CloudProviderError("Enter an API key or credential environment name.")
        if not secret:
            raise CloudProviderError("API key cannot be empty.")
        if (
            DynamicCloudProvider.is_nvidia_hosted_endpoint(endpoint)
            and not secret.startswith("nvapi-")
        ):
            raise CloudProviderError(
                "NVIDIA Hosted Inference requires an 'nvapi-' API key from "
                "https://build.nvidia.com/settings/api-keys. NGC personal keys are "
                "not valid for this endpoint.",
            )
        detected = kind or self.detect_kind(secret, endpoint)
        credential_ref = credential_env or f"LINLIN_PROVIDER_{uuid4().hex.upper()}"
        temporary_name = f"cloud:pending:{uuid4()}"
        adapter = self._adapter(
            name=temporary_name,
            kind=detected,
            base_url=endpoint,
            api_key=secret,
            timeout=120,
        )
        try:
            models = await adapter.list_models()
        except Exception:
            await adapter.close()
            raise
        await adapter.close()

        wrote_secret = bool(api_key)
        if wrote_secret:
            self.credentials.set(credential_ref, secret)
        try:
            created = await self.providers.create_provider(
                ProviderCreate(
                    name=name,
                    kind=detected,
                    cost_class=ProviderCostClass.UNKNOWN,
                    base_url=endpoint,
                    api_key_env=credential_ref,
                    default_model=default_model,
                    enabled=True,
                ),
            )
        except Exception:
            if wrote_secret:
                self.credentials.delete(credential_ref)
            raise
        runtime_name = self.runtime_name(created.id)
        self.manager.register(
            runtime_name,
            self._adapter(
                name=runtime_name,
                kind=detected,
                base_url=endpoint,
                api_key=secret,
                timeout=created.timeout_seconds,
            ),
        )
        self._models[created.id] = models
        return {
            "provider": created.model_dump(mode="json"),
            "runtime_name": runtime_name,
            "detected_kind": detected.value,
            "credential_persistent": self.credentials.persistent,
            "models": models,
        }

    async def discover(self, provider_id: UUID, *, consent: bool) -> dict[str, Any]:
        if not consent:
            raise CloudProviderError("Explicit cloud discovery consent is required.")
        config = await self.providers.get_config(provider_id)
        if not config.enabled or not config.base_url or not config.api_key_env:
            raise CloudProviderError("Cloud provider is not fully configured.")
        runtime_name = self.runtime_name(config.id)
        instance = self.manager.provider(runtime_name)
        models = await instance.list_models()
        self._models[config.id] = models
        return {"runtime_name": runtime_name, "models": models}

    async def model_items(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for config in await self.providers.list_configs():
            if not config.enabled or not config.base_url or not config.api_key_env:
                continue
            runtime_name = self.runtime_name(config.id)
            models = self._models.get(config.id, [])
            for model in models:
                if not isinstance(model, dict):
                    continue
                identifier = model.get("name")
                if not isinstance(identifier, str) or not identifier:
                    continue
                items.append({
                    "provider": runtime_name,
                    "provider_label": config.name,
                    "name": identifier,
                    "local": False,
                    "family": config.kind.value,
                    "capabilities": model.get("capabilities", ["completion", "stream"]),
                })
        return items

    async def training_model_items(self) -> list[dict[str, Any]]:
        """Return only dynamically discovered candidates for a real fine-tuning API."""
        eligible_kinds = {ProviderKind.OPENAI, ProviderKind.OPENAI_COMPATIBLE}
        configs = {config.id: config for config in await self.providers.list_configs()}
        items: list[dict[str, Any]] = []
        for provider_id, models in self._models.items():
            config = configs.get(provider_id)
            if (
                config is None
                or not config.enabled
                or config.kind not in eligible_kinds
                or not config.api_key_env
            ):
                continue
            for model in models:
                name = model.get("name") if isinstance(model, dict) else None
                if isinstance(name, str) and name:
                    items.append({
                        "engine": "openai_compatible",
                        "provider": self.runtime_name(provider_id),
                        "provider_label": config.name,
                        "model": name,
                        "local": False,
                    })
        return items

    async def training_connection(self, runtime_name: str) -> CloudTrainingConnection:
        """Resolve a backend-only fine-tuning connection without exposing its key."""
        prefix = "cloud:"
        if not runtime_name.startswith(prefix):
            raise CloudProviderError("Training requires a configured cloud provider runtime.")
        try:
            provider_id = UUID(runtime_name.removeprefix(prefix))
        except ValueError as exc:
            raise CloudProviderError("Training provider identity is invalid.") from exc
        config = await self.providers.get_config(provider_id)
        if config.kind not in {ProviderKind.OPENAI, ProviderKind.OPENAI_COMPATIBLE}:
            raise CloudProviderError("This provider does not expose the supported fine-tuning protocol.")
        if not config.enabled or not config.base_url or not config.api_key_env:
            raise CloudProviderError("Training provider is not fully configured.")
        return CloudTrainingConnection(
            runtime_name=runtime_name,
            label=config.name,
            kind=config.kind,
            base_url=config.base_url,
            api_key=self.credentials.get(config.api_key_env),
            timeout=config.timeout_seconds,
        )

    async def delete(self, provider_id: UUID) -> None:
        config = await self.providers.get_config(provider_id)
        await self.manager.unregister(self.runtime_name(provider_id))
        await self.providers.delete_provider(provider_id)
        self._models.pop(provider_id, None)
        if config.api_key_env:
            self.credentials.delete(config.api_key_env)

    @staticmethod
    def validate_endpoint(value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise CloudProviderError("Provider endpoint must be an absolute HTTP URL.")
        if parsed.username or parsed.password or parsed.fragment:
            raise CloudProviderError("Provider endpoint cannot contain credentials or fragments.")
        if parsed.scheme == "http":
            loopback = parsed.hostname == "localhost"
            if not loopback:
                try:
                    loopback = ipaddress.ip_address(parsed.hostname).is_loopback
                except ValueError:
                    loopback = False
            if not loopback:
                raise CloudProviderError("Remote cloud endpoints must use HTTPS.")
        return value.strip().rstrip("/")

    @staticmethod
    def detect_kind(api_key: str, base_url: str) -> ProviderKind:
        key = api_key.strip()
        host = (urlparse(base_url).hostname or "").lower()
        if key.startswith("sk-ant-") or "anthropic" in host:
            return ProviderKind.ANTHROPIC
        if key.startswith("AIza") or "googleapis" in host:
            return ProviderKind.GEMINI
        if key.startswith("sk-or-") or "openrouter" in host:
            return ProviderKind.OPENROUTER
        if key.startswith("gsk_") or "groq" in host:
            return ProviderKind.GROQ
        if "deepseek" in host:
            return ProviderKind.DEEPSEEK
        if "mistral" in host:
            return ProviderKind.MISTRAL
        if "openai" in host:
            return ProviderKind.OPENAI
        return ProviderKind.OPENAI_COMPATIBLE

    @staticmethod
    def _adapter(**kwargs: Any) -> DynamicCloudProvider:
        return DynamicCloudProvider(**kwargs)


cloud_provider_service = CloudProviderService()
