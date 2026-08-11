import pytest

from app.providers.adapters.base import BaseProvider
from app.providers.adapters.factory import ProviderFactory as LegacyProviderFactory
from app.providers.adapters.ollama import OllamaProvider
from app.providers.factory import ProviderFactory
from app.providers.manager import ProviderManager
from app.providers.registry import provider_registry


def test_canonical_provider_registration_and_construction() -> None:
    assert provider_registry.names() == ["ollama"]

    provider = ProviderFactory.create(" OLLAMA ")

    assert isinstance(provider, BaseProvider)
    assert isinstance(provider, OllamaProvider)


def test_legacy_factory_import_uses_canonical_factory() -> None:
    assert LegacyProviderFactory is ProviderFactory


def test_invalid_provider_name_fails_predictably() -> None:
    with pytest.raises(ValueError, match="Provider 'missing' is not registered"):
        ProviderFactory.create("missing")


def test_provider_manager_reuses_canonical_instance() -> None:
    manager = ProviderManager()

    assert manager.provider("ollama") is manager.provider(" OLLAMA ")


def test_ollama_capabilities_are_normalized() -> None:
    assert OllamaProvider.capabilities() == {
        "supports_chat": True,
        "supports_stream": True,
        "supports_tools": True,
        "supports_thinking_with_tools": False,
        "supports_embeddings": True,
        "supports_vision": False,
        "requires_api_key": False,
        "local": True,
        "experimental": False,
        "cost_class": "LOCAL_FREE",
    }
