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

    def register(
        self,
        tool: BaseTool,
        *,
        replace: bool = False,
    ) -> None:
        name = tool.name.strip().lower()

        if not name:
            raise ToolRegistrationError("Tool name cannot be empty.")

        if name in self._tools and not replace:
            raise ToolRegistrationError(
                f"Tool '{name}' is already registered.",
            )

        self._tools[name] = tool

    def unregister(self, name: str) -> bool:
        normalized = name.strip().lower()
        return self._tools.pop(normalized, None) is not None

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

    def definitions(self) -> list[dict[str, Any]]:
        return [self._tools[name].definition() for name in self.names()]

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
