from __future__ import annotations

from typing import Protocol

from app.providers.manager import ProviderManager


class RagCloudConsentRequired(RuntimeError):
    pass


class EmbeddingBackend(Protocol):
    async def embed(self, texts: list[str], *, cloud_consent: bool = False) -> list[list[float]]: ...


class ProviderEmbeddingBackend:
    """Provider-neutral adapter; cloud transfer requires explicit consent."""

    def __init__(self, manager: ProviderManager, provider: str, model: str) -> None:
        self._manager = manager
        self._provider = provider
        self._model = model

    async def embed(self, texts: list[str], *, cloud_consent: bool = False) -> list[list[float]]:
        instance = self._manager.provider(self._provider)
        if not instance.local and not cloud_consent:
            raise RagCloudConsentRequired("Cloud embedding requires explicit consent.")
        if not instance.supports_embeddings:
            raise RuntimeError(f"Provider '{self._provider}' does not support embeddings.")
        return await instance.embeddings(model=self._model, inputs=texts)
