from __future__ import annotations

import ast
import math
import operator
from typing import Any, Final

from app.tools.base import BaseTool


class CalculatorExpressionError(ValueError):
    """Raised when a calculator expression is invalid or unsafe."""


_BINARY_OPERATORS: Final = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS: Final = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_ALLOWED_CONSTANTS: Final = {
    "pi": math.pi,
    "e": math.e,
}

_MAX_EXPRESSION_LENGTH: Final = 256
_MAX_ABSOLUTE_RESULT: Final = 1e100
_MAX_POWER: Final = 100


class SafeCalculator:
    """Evaluate restricted arithmetic expressions without eval()."""

    def evaluate(self, expression: str) -> int | float:
        normalized = expression.strip()

        if not normalized:
            raise CalculatorExpressionError(
                "Expression cannot be empty.",
            )

        if len(normalized) > _MAX_EXPRESSION_LENGTH:
            raise CalculatorExpressionError(
                "Expression is too long.",
            )

        try:
            parsed = ast.parse(
                normalized,
                mode="eval",
            )
        except SyntaxError as exc:
            raise CalculatorExpressionError(
                "Expression syntax is invalid.",
            ) from exc

        result = self._evaluate_node(parsed.body)

        if isinstance(result, bool) or not isinstance(
            result,
            (int, float),
        ):
            raise CalculatorExpressionError(
                "Expression did not produce a number.",
            )

        if not math.isfinite(float(result)):
            raise CalculatorExpressionError(
                "Expression produced a non-finite result.",
            )

        if abs(result) > _MAX_ABSOLUTE_RESULT:
            raise CalculatorExpressionError(
                "Expression result is too large.",
            )

        return result

    def _evaluate_node(
        self,
        node: ast.AST,
    ) -> int | float:
        if isinstance(node, ast.Constant):
            value = node.value

            if isinstance(value, bool) or not isinstance(
                value,
                (int, float),
            ):
                raise CalculatorExpressionError(
                    "Only numeric constants are allowed.",
                )

            return value

        if isinstance(node, ast.Name):
            try:
                return _ALLOWED_CONSTANTS[node.id]
            except KeyError as exc:
                raise CalculatorExpressionError(
                    f"Unknown constant: {node.id}",
                ) from exc

        if isinstance(node, ast.BinOp):
            operator_type = type(node.op)

            try:
                operation = _BINARY_OPERATORS[operator_type]
            except KeyError as exc:
                raise CalculatorExpressionError(
                    "This arithmetic operator is not allowed.",
                ) from exc

            left = self._evaluate_node(node.left)
            right = self._evaluate_node(node.right)

            if operator_type is ast.Pow and abs(right) > _MAX_POWER:
                raise CalculatorExpressionError(
                    "Exponent is too large.",
                )

            try:
                return operation(left, right)
            except ZeroDivisionError as exc:
                raise CalculatorExpressionError(
                    "Division by zero is not allowed.",
                ) from exc
            except OverflowError as exc:
                raise CalculatorExpressionError(
                    "Expression result is too large.",
                ) from exc

        if isinstance(node, ast.UnaryOp):
            operator_type = type(node.op)

            try:
                operation = _UNARY_OPERATORS[operator_type]
            except KeyError as exc:
                raise CalculatorExpressionError(
                    "This unary operator is not allowed.",
                ) from exc

            return operation(
                self._evaluate_node(node.operand),
            )

        raise CalculatorExpressionError(
            f"Unsupported expression element: {type(node).__name__}",
        )


class CalculatorTool(BaseTool):
    """Safe arithmetic calculator tool."""

    name = "calculator"
    description = (
        "Safely evaluate an arithmetic expression. "
        "Supports numbers, parentheses, +, -, *, /, //, %, **, pi and e."
    )

    def __init__(self) -> None:
        self._calculator = SafeCalculator()

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": (
                        "Arithmetic expression such as '(12 + 8) * 3' or 'pi * 5 ** 2'."
                    ),
                    "minLength": 1,
                    "maxLength": _MAX_EXPRESSION_LENGTH,
                },
            },
            "required": ["expression"],
            "additionalProperties": False,
        }

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        expression = arguments.get("expression")

        if not isinstance(expression, str):
            raise CalculatorExpressionError(
                "The expression argument must be a string.",
            )

        result = self._calculator.evaluate(expression)

        return {
            "tool": self.name,
            "ok": True,
            "expression": expression,
            "result": result,
        }
