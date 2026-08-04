from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Base interface implemented by every Linlin Agent tool."""

    name: str
    description: str

    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """Return the JSON Schema used by model tool calling."""

        raise NotImplementedError

    def definition(self) -> dict[str, Any]:
        """Return an OpenAI-compatible function tool definition."""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema(),
            },
        }

    @abstractmethod
    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the tool and return a normalized result."""

        raise NotImplementedError
