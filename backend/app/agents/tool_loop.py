from __future__ import annotations

import json
from typing import Any

from app.providers.manager import ProviderManager
from app.tools.manager import ToolManager


class ToolLoopError(RuntimeError):
    """Raised when a model tool-calling loop cannot be completed."""


class ToolLoopLimitError(ToolLoopError):
    """Raised when the maximum number of tool iterations is reached."""


class ToolCallFormatError(ToolLoopError):
    """Raised when a provider returns an invalid tool call."""


class ToolLoop:
    """Execute model-requested tools and return the final model response."""

    def __init__(
        self,
        provider_manager: ProviderManager,
        tool_manager: ToolManager,
        max_iterations: int = 5,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1.")

        self._provider_manager = provider_manager
        self._tool_manager = tool_manager
        self._max_iterations = max_iterations

    async def run(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        provider_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        working_messages = [dict(message) for message in messages]

        options = dict(provider_options or {})

        options["tools"] = self._tool_manager.definitions()

        for _ in range(self._max_iterations):
            response = await self._provider_manager.chat(
                provider=provider,
                model=model,
                messages=working_messages,
                **options,
            )

            if not isinstance(response, dict):
                raise TypeError(
                    "Provider returned an invalid chat response.",
                )

            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                return response

            if not isinstance(tool_calls, list):
                raise ToolCallFormatError(
                    "Provider tool_calls must be a list.",
                )

            assistant_message = self._assistant_message(
                response,
                tool_calls,
            )
            working_messages.append(assistant_message)

            for tool_call in tool_calls:
                tool_message = await self._execute_tool_call(
                    tool_call,
                )
                working_messages.append(tool_message)

        raise ToolLoopLimitError(
            "Maximum tool-calling iterations reached.",
        )

    @staticmethod
    def _assistant_message(
        response: dict[str, Any],
        tool_calls: list[Any],
    ) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": str(response.get("content", "")),
            "tool_calls": tool_calls,
        }

    async def _execute_tool_call(
        self,
        tool_call: Any,
    ) -> dict[str, Any]:
        if not isinstance(tool_call, dict):
            raise ToolCallFormatError(
                "Tool call must be an object.",
            )

        function = tool_call.get("function")

        if not isinstance(function, dict):
            raise ToolCallFormatError(
                "Tool call function must be an object.",
            )

        name = function.get("name")

        if not isinstance(name, str) or not name.strip():
            raise ToolCallFormatError(
                "Tool call function name is missing.",
            )

        arguments = self._parse_arguments(
            function.get("arguments", {}),
        )

        result = await self._tool_manager.execute(
            name,
            arguments,
        )

        tool_message: dict[str, Any] = {
            "role": "tool",
            "name": name,
            "content": json.dumps(
                result,
                ensure_ascii=False,
            ),
        }

        tool_call_id = tool_call.get("id")

        if isinstance(tool_call_id, str) and tool_call_id:
            tool_message["tool_call_id"] = tool_call_id

        return tool_message

    @staticmethod
    def _parse_arguments(
        arguments: Any,
    ) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments

        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise ToolCallFormatError(
                    "Tool call arguments contain invalid JSON.",
                ) from exc

            if not isinstance(parsed, dict):
                raise ToolCallFormatError(
                    "Tool call arguments must decode to an object.",
                )

            return parsed

        raise ToolCallFormatError(
            "Tool call arguments must be an object or JSON string.",
        )
