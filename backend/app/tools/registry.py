"""Registration of built-in Linlin Agent tools."""

from app.tools.calculator import CalculatorTool
from app.tools.manager import tool_manager


def register_builtin_tools() -> None:
    """Register all built-in tools."""

    if "calculator" not in tool_manager.names():
        tool_manager.register(CalculatorTool())


register_builtin_tools()
