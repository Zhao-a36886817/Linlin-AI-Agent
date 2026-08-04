from __future__ import annotations

from app.providers.registry import registry


class ProviderFactory:
    @staticmethod
    def create(
        provider_name: str,
        **kwargs,
    ):

        provider_cls = registry.get(provider_name)

        return provider_cls(**kwargs)
