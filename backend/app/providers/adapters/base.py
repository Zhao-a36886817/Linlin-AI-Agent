from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from app.providers.models import ProviderCostClass


class BaseProvider(ABC):
    """Base interface implemented by every Linlin Agent model provider."""

    name: str = "base"
    supports_chat: bool = True
    supports_stream: bool = False
    supports_vision: bool = False
    supports_tools: bool = False
    supports_thinking_with_tools: bool = False
    supports_embeddings: bool = False
    requires_api_key: bool = False
    local: bool = False
    experimental: bool = False
    cost_class: ProviderCostClass = ProviderCostClass.UNKNOWN

    @classmethod
    def capabilities(cls) -> dict[str, bool]:
        """Return normalized capability metadata for this adapter."""

        return {
            "supports_chat": cls.supports_chat,
            "supports_stream": cls.supports_stream,
            "supports_tools": cls.supports_tools,
            "supports_thinking_with_tools": cls.supports_thinking_with_tools,
            "supports_embeddings": cls.supports_embeddings,
            "supports_vision": cls.supports_vision,
            "requires_api_key": cls.requires_api_key,
            "local": cls.local,
            "experimental": cls.experimental,
            "cost_class": cls.cost_class.value,
        }

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

    async def close(self) -> None:
        """Release adapter resources when the runtime unregisters it."""

        return
