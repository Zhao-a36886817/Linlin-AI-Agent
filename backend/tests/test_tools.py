from __future__ import annotations

import pytest

from app.tools import (
    CalculatorExpressionError,
    CalculatorTool,
    SafeCalculator,
    ToolManager,
    ToolNotFoundError,
    ToolRegistrationError,
    tool_manager,
)


def test_safe_calculator_arithmetic() -> None:
    calculator = SafeCalculator()

    assert calculator.evaluate("(12 + 8) * 3") == 60
    assert calculator.evaluate("2 ** 8") == 256
    assert calculator.evaluate("10 / 4") == 2.5


def test_safe_calculator_constants() -> None:
    calculator = SafeCalculator()

    assert calculator.evaluate("pi * 2") == pytest.approx(
        6.283185307179586,
    )


@pytest.mark.parametrize(
    "expression",
    [
        '__import__("os").system("dir")',
        'open("secret.txt")',
        "[1, 2, 3]",
        "lambda: 1",
        "1 / 0",
        "2 ** 1000",
    ],
)
def test_safe_calculator_rejects_unsafe_expressions(
    expression: str,
) -> None:
    calculator = SafeCalculator()

    with pytest.raises(CalculatorExpressionError):
        calculator.evaluate(expression)


def test_builtin_registry_contains_calculator() -> None:
    assert "calculator" in tool_manager.names()


@pytest.mark.asyncio
async def test_tool_manager_executes_calculator() -> None:
    manager = ToolManager()
    manager.register(CalculatorTool())

    result = await manager.execute(
        "calculator",
        {
            "expression": "(25 + 5) * 8",
        },
    )

    assert result == {
        "tool": "calculator",
        "ok": True,
        "expression": "(25 + 5) * 8",
        "result": 240,
    }


def test_tool_manager_returns_openai_definition() -> None:
    manager = ToolManager()
    manager.register(CalculatorTool())

    definitions = manager.definitions()

    assert len(definitions) == 1

    definition = definitions[0]

    assert definition["type"] == "function"
    assert definition["function"]["name"] == "calculator"
    assert definition["function"]["parameters"]["required"] == [
        "expression",
    ]


def test_tool_manager_rejects_duplicate_registration() -> None:
    manager = ToolManager()
    manager.register(CalculatorTool())

    with pytest.raises(ToolRegistrationError):
        manager.register(CalculatorTool())


def test_tool_profiles_limit_schema_exposure_without_removing_capability() -> None:
    manager = ToolManager()
    core = CalculatorTool()
    specialized = CalculatorTool()
    specialized.name = "specialized_calculator"

    manager.register(core)
    manager.register(specialized, profiles=("specialized",))

    assert [item["function"]["name"] for item in manager.definitions()] == [
        "calculator",
    ]
    assert [
        item["function"]["name"]
        for item in manager.definitions("specialized")
    ] == ["specialized_calculator"]
    assert manager.get("specialized_calculator") is specialized


@pytest.mark.asyncio
async def test_tool_manager_rejects_unknown_tool() -> None:
    manager = ToolManager()

    with pytest.raises(ToolNotFoundError):
        await manager.execute(
            "missing_tool",
            {},
        )


@pytest.mark.asyncio
async def test_tool_manager_rejects_invalid_arguments() -> None:
    manager = ToolManager()
    manager.register(CalculatorTool())

    with pytest.raises(TypeError):
        await manager.execute(
            "calculator",
            "12 * 8",  # type: ignore[arg-type]
        )
