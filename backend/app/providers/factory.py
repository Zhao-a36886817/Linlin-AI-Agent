from __future__ import annotations

from typing import Any

from app.providers.adapters.base import BaseProvider
from app.providers.registry import provider_registry


class ProviderFactory:
    """Create provider adapter instances from the registry."""

    @staticmethod
    def create(
        provider_name: str,
        **kwargs: Any,
    ) -> BaseProvider:
        provider_class = provider_registry.get(provider_name)

        return provider_class(**kwargs)
