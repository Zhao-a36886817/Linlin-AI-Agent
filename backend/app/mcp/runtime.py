from __future__ import annotations

import asyncio
import re
from typing import Any, Protocol


class McpError(RuntimeError):
    pass


class McpPermissionError(McpError):
    pass


class McpSchemaError(McpError):
    pass


class McpTransport(Protocol):
    async def list_tools(self) -> list[dict[str, Any]]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...
    async def close(self) -> None: ...


_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")


class McpRuntime:
    """Deny-by-default MCP session over an explicitly supplied transport."""

    def __init__(self, *, server_id: str, transport: McpTransport, allowed_servers: set[str] | None = None, timeout: float = 10.0) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive.")
        self.server_id = server_id
        self._transport = transport
        self._allowed_servers = frozenset(allowed_servers or set())
        self._timeout = timeout
        self._tools: dict[str, dict[str, Any]] = {}

    async def discover(self) -> list[dict[str, Any]]:
        self._require_server()
        raw = await self._wait(self._transport.list_tools())
        validated: dict[str, dict[str, Any]] = {}
        for item in raw:
            if not isinstance(item, dict):
                raise McpSchemaError("MCP tool definition must be an object.")
            name, description, schema = item.get("name"), item.get("description"), item.get("inputSchema")
            if not isinstance(name, str) or not _NAME.fullmatch(name):
                raise McpSchemaError("MCP tool name is invalid.")
            if name in validated:
                raise McpSchemaError("MCP tool names must be unique.")
            if not isinstance(description, str) or not isinstance(schema, dict) or schema.get("type") != "object":
                raise McpSchemaError("MCP tool schema is invalid.")
            validated[name] = {"name": name, "description": description, "inputSchema": schema}
        self._tools = validated
        return [validated[name] for name in sorted(validated)]

    async def invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_server()
        if name not in self._tools:
            raise McpPermissionError(f"MCP capability '{name}' is not approved.")
        result = await self._wait(self._transport.call_tool(name, arguments))
        if not isinstance(result, dict):
            raise McpSchemaError("MCP result must be an object.")
        return result

    async def close(self) -> None:
        await self._wait(self._transport.close())

    def _require_server(self) -> None:
        if self.server_id not in self._allowed_servers:
            raise McpPermissionError(f"MCP server '{self.server_id}' is not approved.")

    async def _wait(self, operation: Any) -> Any:
        try:
            return await asyncio.wait_for(operation, timeout=self._timeout)
        except TimeoutError as exc:
            raise McpError("MCP operation timed out.") from exc
