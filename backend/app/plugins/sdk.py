from __future__ import annotations

from typing import Protocol

from app.plugins.models import PluginManifest


class PluginSdk(Protocol):
    """Versioned declaration contract; execution adapters are future reviewed work."""

    manifest: PluginManifest
