from __future__ import annotations

from app.plugins.models import PluginManifest


class PluginError(RuntimeError):
    pass


class PluginPermissionError(PluginError):
    pass


class PluginRuntime:
    """Manifest lifecycle only; arbitrary plugin code is never loaded."""

    def __init__(self) -> None:
        self._installed: dict[str, PluginManifest] = {}
        self._enabled: set[str] = set()
        self._approved: dict[str, frozenset[str]] = {}

    def install(self, manifest: PluginManifest, *, approved_capabilities: set[str] | None = None) -> None:
        if manifest.plugin_id in self._installed:
            raise PluginError(f"Plugin '{manifest.plugin_id}' is already installed.")
        approved = frozenset(approved_capabilities or set())
        requested = set(manifest.capabilities)
        if not requested <= approved:
            raise PluginPermissionError("Plugin requested unapproved capabilities.")
        self._installed[manifest.plugin_id] = manifest
        self._approved[manifest.plugin_id] = approved

    def enable(self, plugin_id: str) -> None:
        if plugin_id not in self._installed:
            raise PluginError(f"Plugin '{plugin_id}' is not installed.")
        self._enabled.add(plugin_id)

    def disable(self, plugin_id: str) -> None:
        self._enabled.discard(plugin_id)

    def uninstall(self, plugin_id: str) -> bool:
        self.disable(plugin_id)
        self._approved.pop(plugin_id, None)
        return self._installed.pop(plugin_id, None) is not None

    def capabilities(self, plugin_id: str) -> tuple[str, ...]:
        if plugin_id not in self._enabled:
            return ()
        return self._installed[plugin_id].capabilities

    def installed(self) -> list[PluginManifest]:
        return [self._installed[key] for key in sorted(self._installed)]
