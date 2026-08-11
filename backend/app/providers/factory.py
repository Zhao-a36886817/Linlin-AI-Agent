from __future__ import annotations

from typing import Any

from app.providers.adapters.base import BaseProvider
from app.providers.registry import provider_registry


class ProviderFactory:
    """Canonical construction route from ProviderRegistry to BaseProvider."""

    @staticmethod
    def create(
        provider_name: str,
        **kwargs: Any,
    ) -> BaseProvider:
        provider_class = provider_registry.get(provider_name)

        return provider_class(**kwargs)
