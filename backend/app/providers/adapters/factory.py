"""Compatibility import for the canonical provider factory.

New code must import :class:`ProviderFactory` from ``app.providers.factory``.
"""

from app.providers.factory import ProviderFactory

__all__ = ["ProviderFactory"]
