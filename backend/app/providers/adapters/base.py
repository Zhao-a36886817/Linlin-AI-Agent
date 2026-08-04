from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class BaseProvider(ABC):
    """Base interface implemented by every Linlin Agent model provider."""

    name: str = "base"
    supports_stream: bool = False
    supports_vision: bool = False
    supports_tools: bool = False
    supports_embeddings: bool = False

    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a chat-completion request and return a normalized response."""

        raise NotImplementedError

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream normalized events.
        """

        del model, messages, kwargs

        raise NotImplementedError(f"{self.name} does not support streaming.")

    async def list_models(self) -> list[str]:
        """Return model identifiers available through this provider."""

        return []

    async def embeddings(
        self,
        model: str,
        inputs: list[str],
        **kwargs: Any,
    ) -> list[list[float]]:
        """Generate embeddings through this provider."""

        del model, inputs, kwargs

        raise NotImplementedError(
            f"{self.name} does not support embeddings.",
        )

    async def health(self) -> bool:
        """Return whether the provider service is reachable."""

        return True
