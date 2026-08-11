from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.providers.adapters.base import BaseProvider
from app.providers.factory import ProviderFactory


class ProviderManager:
    """Canonical runtime entry point for discovering and using providers."""

    def __init__(self) -> None:
        self._instances: dict[str, BaseProvider] = {}

    def provider(self, name: str) -> BaseProvider:
        normalized_name = name.strip().lower()

        if not normalized_name:
            raise ValueError("Provider name cannot be empty.")

        if normalized_name not in self._instances:
            self._instances[normalized_name] = ProviderFactory.create(
                normalized_name,
            )

        return self._instances[normalized_name]

    def register(self, name: str, provider: BaseProvider) -> None:
        normalized_name = name.strip().lower()
        if not normalized_name:
            raise ValueError("Provider name cannot be empty.")
        self._instances[normalized_name] = provider

    async def unregister(self, name: str) -> None:
        provider = self._instances.pop(name.strip().lower(), None)
        if provider is not None:
            await provider.close()

    async def health(self, provider: str) -> bool:
        return await self.provider(provider).health()

    async def list_models(
        self,
        provider: str,
    ) -> list[dict[str, Any]]:
        return await self.provider(provider).list_models()

    async def chat(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await self.provider(provider).chat(
            model=model,
            messages=messages,
            **kwargs,
        )

    async def stream(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        instance = self.provider(provider)

        if not instance.supports_stream:
            raise RuntimeError(
                f"Provider '{provider}' does not support streaming.",
            )

        async for event in instance.stream(
            model=model,
            messages=messages,
            **kwargs,
        ):
            yield event

    async def close(self) -> None:
        for provider in self._instances.values():
            await provider.close()

        self._instances.clear()


provider_manager = ProviderManager()
