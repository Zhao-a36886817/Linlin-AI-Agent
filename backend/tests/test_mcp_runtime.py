import asyncio
from typing import Any

import pytest

from app.mcp import McpError, McpPermissionError, McpRuntime, McpSchemaError, McpTool
from app.tools.manager import ToolManager


class FakeTransport:
    def __init__(self, tools: list[dict[str, Any]], *, delay: float = 0) -> None:
        self.tools, self.delay, self.calls = tools, delay, []

    async def list_tools(self) -> list[dict[str, Any]]:
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        return {"ok": True, "name": name}

    async def close(self) -> None:
        return None


def definition(name: str = "remote_calc") -> dict[str, Any]:
    return {"name": name, "description": "Remote calculation", "inputSchema": {"type": "object", "properties": {}}}


@pytest.mark.asyncio
async def test_no_server_is_allowed_by_default() -> None:
    with pytest.raises(McpPermissionError):
        await McpRuntime(server_id="server", transport=FakeTransport([])).discover()


@pytest.mark.asyncio
async def test_malicious_or_duplicate_schemas_are_rejected() -> None:
    for tools in ([definition("../escape")], [definition(), definition()]):
        runtime = McpRuntime(server_id="server", transport=FakeTransport(tools), allowed_servers={"server"})
        with pytest.raises(McpSchemaError):
            await runtime.discover()


@pytest.mark.asyncio
async def test_undiscovered_capability_cannot_execute() -> None:
    runtime = McpRuntime(server_id="server", transport=FakeTransport([]), allowed_servers={"server"})
    with pytest.raises(McpPermissionError):
        await runtime.invoke("missing", {})


@pytest.mark.asyncio
async def test_timeout_is_bounded() -> None:
    runtime = McpRuntime(server_id="server", transport=FakeTransport([], delay=0.05), allowed_servers={"server"}, timeout=0.001)
    with pytest.raises(McpError, match="timed out"):
        await runtime.discover()


@pytest.mark.asyncio
async def test_capability_executes_only_through_tool_manager() -> None:
    transport = FakeTransport([definition()])
    runtime = McpRuntime(server_id="server", transport=transport, allowed_servers={"server"})
    discovered = await runtime.discover()
    manager = ToolManager()
    manager.register(McpTool(runtime, discovered[0]), profiles=("mcp",))
    assert manager.definitions() == []
    assert (await manager.execute("remote_calc", {}))["ok"] is True
    assert transport.calls == [("remote_calc", {})]
