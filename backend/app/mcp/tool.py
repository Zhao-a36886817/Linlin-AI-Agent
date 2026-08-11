from __future__ import annotations

from typing import Any

from app.mcp.runtime import McpRuntime
from app.tools.base import BaseTool


class McpTool(BaseTool):
    """Tool Runtime adapter for one explicitly discovered MCP capability."""

    def __init__(self, runtime: McpRuntime, definition: dict[str, Any]) -> None:
        self._runtime = runtime
        self.name = str(definition["name"])
        self.description = str(definition["description"])
        self._schema = dict(definition["inputSchema"])

    def parameters_schema(self) -> dict[str, Any]:
        return self._schema

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._runtime.invoke(self.name, arguments)
