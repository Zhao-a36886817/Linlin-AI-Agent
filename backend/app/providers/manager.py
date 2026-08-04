from __future__ import annotations

from typing import Any

from app.providers.factory import ProviderFactory


class ProviderManager:
    """
    Central runtime for every Provider.

    Frontend、Agent、API
    全部只跟這個類別溝通。
    """

    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}

    def provider(
        self,
        name: str,
    ):

        key = name.lower()

        if key not in self._instances:
            self._instances[key] = ProviderFactory.create(key)

        return self._instances[key]

    async def health(
        self,
        provider: str,
    ) -> bool:

        return await self.provider(provider).health()

    async def list_models(
        self,
        provider: str,
    ) -> list[dict]:

        return await self.provider(provider).list_models()

    async def chat(
        self,
        provider: str,
        model: str,
        messages: list[dict],
        **kwargs,
    ):

        return await self.provider(provider).chat(
            model=model,
            messages=messages,
            **kwargs,
        )

    async def close(self) -> None:

        for provider in self._instances.values():
            if hasattr(provider, "close"):
                await provider.close()

        self._instances.clear()


provider_manager = ProviderManager()
