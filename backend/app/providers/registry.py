from __future__ import annotations

from app.providers.adapters.base import BaseProvider


class ProviderRegistry:
    """Registry of available provider adapter classes."""

    def __init__(self) -> None:
        self._providers: dict[str, type[BaseProvider]] = {}

    def register(
        self,
        name: str,
        provider_class: type[BaseProvider],
    ) -> None:
        normalized_name = name.strip().lower()

        if not normalized_name:
            raise ValueError("Provider name cannot be empty.")

        self._providers[normalized_name] = provider_class

    def get(
        self,
        name: str,
    ) -> type[BaseProvider]:
        normalized_name = name.strip().lower()

        try:
            return self._providers[normalized_name]
        except KeyError as exc:
            raise ValueError(
                f"Provider '{name}' is not registered.",
            ) from exc

    def names(self) -> list[str]:
        return sorted(self._providers)


provider_registry = ProviderRegistry()
