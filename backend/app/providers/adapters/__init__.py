"""Unified model-provider adapters for Linlin Agent."""

from app.providers.adapters.base import BaseProvider
from app.providers.adapters.ollama import OllamaProvider
from app.providers.registry import provider_registry

provider_registry.register(
    "ollama",
    OllamaProvider,
)

__all__ = [
    "BaseProvider",
    "OllamaProvider",
]
