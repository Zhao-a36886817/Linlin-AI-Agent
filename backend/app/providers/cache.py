from __future__ import annotations

from typing import Any


class ProviderCache:
    """
    Cache provider instances.

    Each provider is created only once and reused.
    """

    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}

    def has(self, name: str) -> bool:
        return name in self._instances

    def get(self, name: str) -> Any | None:
        return self._instances.get(name)

    def set(self, name: str, provider: Any) -> None:
        self._instances[name] = provider

    async def close_all(self) -> None:
        for provider in self._instances.values():
            close = getattr(provider, "close", None)

            if callable(close):
                await close()

        self._instances.clear()


provider_cache = ProviderCache()
