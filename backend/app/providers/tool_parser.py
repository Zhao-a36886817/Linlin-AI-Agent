from __future__ import annotations

import ast
import json
import re
from typing import Any


class ToolParser:
    """Normalize tool-calling responses from different providers."""

    @classmethod
    def parse(
        cls,
        raw: dict[str, Any],
    ) -> list[dict[str, Any]]:
        native_calls = cls._extract_native_tool_calls(raw)

        if native_calls:
            return cls._normalize_calls(native_calls)

        content = cls._extract_content(raw)

        if not content:
            return []

        for parser in (
            cls._parse_xml_tool_calls,
            cls._parse_markdown_json,
            cls._parse_plain_json,
            cls._parse_function_call,
        ):
            calls = parser(content)

            if calls:
                return cls._normalize_calls(calls)

        return []

    @staticmethod
    def _extract_native_tool_calls(
        raw: dict[str, Any],
    ) -> list[Any]:
        direct_calls = raw.get("tool_calls")

        if isinstance(direct_calls, list):
            return direct_calls

        message = raw.get("message", {})

        if isinstance(message, dict):
            message_calls = message.get("tool_calls")

            if isinstance(message_calls, list):
                return message_calls

        return []

    @staticmethod
    def _extract_content(
        raw: dict[str, Any],
    ) -> str:
        message = raw.get("message", {})

        if isinstance(message, dict):
            content = message.get("content")

            if isinstance(content, str):
                return content.strip()

        content = raw.get("content")

        if isinstance(content, str):
            return content.strip()

        return ""

    @classmethod
    def _normalize_calls(
        cls,
        calls: list[Any],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []

        for index, call in enumerate(calls, start=1):
            normalized_call = cls._normalize_call(call, index)

            if normalized_call is not None:
                normalized.append(normalized_call)

        return normalized

    @classmethod
    def _normalize_call(
        cls,
        call: Any,
        index: int,
    ) -> dict[str, Any] | None:
        if not isinstance(call, dict):
            return None

        function = call.get("function")

        if isinstance(function, dict):
            name = function.get("name")
            arguments = function.get("arguments", {})
        else:
            name = call.get("name")
            arguments = call.get("arguments", {})

        if not isinstance(name, str) or not name.strip():
            return None

        parsed_arguments = cls._normalize_arguments(arguments)

        if parsed_arguments is None:
            return None

        call_id = call.get("id")

        if not isinstance(call_id, str) or not call_id.strip():
            call_id = f"tool_{index}"

        return {
            "id": call_id,
            "type": "function",
            "function": {
                "name": name.strip(),
                "arguments": parsed_arguments,
            },
        }

    @staticmethod
    def _normalize_arguments(
        arguments: Any,
    ) -> dict[str, Any] | None:
        if isinstance(arguments, dict):
            return arguments

        if isinstance(arguments, str):
            stripped = arguments.strip()

            if not stripped:
                return {}

            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return None

            if isinstance(parsed, dict):
                return parsed

        return None

    @staticmethod
    def _parse_xml_tool_calls(
        content: str,
    ) -> list[Any]:
        matches = re.findall(
            r"<tool_call>\s*(.*?)\s*</tool_call>",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

        calls: list[Any] = []

        for match in matches:
            try:
                parsed = json.loads(match)
            except json.JSONDecodeError:
                continue

            if isinstance(parsed, list):
                calls.extend(parsed)
            else:
                calls.append(parsed)

        return calls

    @staticmethod
    def _parse_markdown_json(
        content: str,
    ) -> list[Any]:
        matches = re.findall(
            r"```[ \t]*(?:json)?[ \t]*\r?\n(.*?)\r?\n[ \t]*```",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

        calls: list[Any] = []

        for match in matches:
            candidate = match.strip()

            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            if isinstance(parsed, list):
                calls.extend(parsed)
            elif isinstance(parsed, dict):
                calls.append(parsed)

        return calls

    @staticmethod
    def _parse_plain_json(
        content: str,
    ) -> list[Any]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return []

        if isinstance(parsed, list):
            return parsed

        if isinstance(parsed, dict):
            return [parsed]

        return []

    @staticmethod
    def _parse_function_call(
        content: str,
    ) -> list[Any]:
        match = re.fullmatch(
            r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*",
            content,
            flags=re.DOTALL,
        )

        if match is None:
            return []

        name = match.group(1)
        raw_arguments = match.group(2).strip()

        if not raw_arguments:
            arguments: dict[str, Any] = {}
        else:
            arguments = ToolParser._parse_python_arguments(raw_arguments)

            if arguments is None:
                return []

        return [
            {
                "name": name,
                "arguments": arguments,
            },
        ]

    @staticmethod
    def _parse_python_arguments(
        raw_arguments: str,
    ) -> dict[str, Any] | None:
        try:
            expression = ast.parse(
                f"f({raw_arguments})",
                mode="eval",
            )
        except SyntaxError:
            return None

        call = expression.body

        if not isinstance(call, ast.Call):
            return None

        arguments: dict[str, Any] = {}

        if call.args:
            if len(call.args) != 1:
                return None

            try:
                value = ast.literal_eval(call.args[0])
            except (ValueError, SyntaxError):
                return None

            arguments["expression"] = value

        for keyword in call.keywords:
            if keyword.arg is None:
                return None

            try:
                value = ast.literal_eval(keyword.value)
            except (ValueError, SyntaxError):
                return None

            arguments[keyword.arg] = value

        return arguments
