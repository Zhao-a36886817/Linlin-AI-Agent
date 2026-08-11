from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool


class ToolNotFoundError(LookupError):
    """Raised when a requested tool is not registered."""


class ToolRegistrationError(ValueError):
    """Raised when a tool cannot be registered."""


class ToolManager:
    """Register, inspect and execute Linlin Agent tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._profiles: dict[str, set[str]] = {}

    def register(
        self,
        tool: BaseTool,
        *,
        replace: bool = False,
        profiles: tuple[str, ...] = ("core",),
    ) -> None:
        name = tool.name.strip().lower()

        if not name:
            raise ToolRegistrationError("Tool name cannot be empty.")

        if name in self._tools and not replace:
            raise ToolRegistrationError(
                f"Tool '{name}' is already registered.",
            )

        normalized_profiles: list[str] = []
        for profile in profiles:
            normalized_profile = profile.strip().lower()
            if not normalized_profile:
                raise ToolRegistrationError("Tool profile cannot be empty.")
            normalized_profiles.append(normalized_profile)

        if replace:
            for profile_tools in self._profiles.values():
                profile_tools.discard(name)

        self._tools[name] = tool

        for normalized_profile in normalized_profiles:
            self._profiles.setdefault(normalized_profile, set()).add(name)

    def unregister(self, name: str) -> bool:
        normalized = name.strip().lower()
        removed = self._tools.pop(normalized, None) is not None
        for profile_tools in self._profiles.values():
            profile_tools.discard(normalized)
        return removed

    def get(self, name: str) -> BaseTool:
        normalized = name.strip().lower()

        try:
            return self._tools[normalized]
        except KeyError as exc:
            raise ToolNotFoundError(
                f"Tool '{name}' is not registered.",
            ) from exc

    def names(self) -> list[str]:
        return sorted(self._tools)

    def definitions(self, profile: str = "core") -> list[dict[str, Any]]:
        """Return deterministic schemas explicitly exposed by a profile."""

        normalized_profile = profile.strip().lower()
        names = sorted(self._profiles.get(normalized_profile, set()))
        return [self._tools[name].definition() for name in names]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise TypeError("Tool arguments must be an object.")

        tool = self.get(name)
        return await tool.execute(arguments)


tool_manager = ToolManager()
