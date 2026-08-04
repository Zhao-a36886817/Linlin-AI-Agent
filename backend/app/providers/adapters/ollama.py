from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Self

import httpx

from app.providers.adapters.base import BaseProvider
from app.providers.tool_parser import ToolParser


class OllamaProvider(BaseProvider):
    """Ollama local model provider."""

    name = "ollama"
    supports_stream = True
    supports_tools = True
    supports_embeddings = True
    supports_vision = False

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 600.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self.client.request(
                method=method,
                url=endpoint,
                json=payload,
            )
            response.raise_for_status()

            data = response.json()

            if not isinstance(data, dict):
                raise TypeError("Ollama returned an invalid response.")

            return data

        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Ollama request timed out after {self.timeout} seconds.",
            ) from exc

        except httpx.ConnectError as exc:
            raise RuntimeError(
                "Unable to connect to Ollama at "
                f"{self.base_url}. Confirm that Ollama is running.",
            ) from exc

        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()

            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code}: {detail}",
            ) from exc

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Ollama returned invalid JSON.",
            ) from exc

    async def health(self) -> bool:
        try:
            await self._request("GET", "/api/tags")
            return True
        except RuntimeError:
            return False

    async def version(self) -> dict[str, Any]:
        return await self._request("GET", "/api/version")

    async def list_models(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/api/tags")
        models = response.get("models", [])

        if not isinstance(models, list):
            return []

        return [model for model in models if isinstance(model, dict)]

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        payload.update(kwargs)
        payload["stream"] = False

        from pprint import pprint

        print("\n" + "=" * 80)
        print("OLLAMA PAYLOAD")
        print("=" * 80)
        pprint(payload, width=120)
        print("=" * 80 + "\n")

        raw = await self._request(
            "POST",
            "/api/chat",
            payload,
        )

        print("=" * 80)
        print("OLLAMA RAW RESPONSE")
        from pprint import pprint

        pprint(raw, width=120)
        print("=" * 80)

        message = raw.get("message", {})

        if not isinstance(message, dict):
            message = {}

        prompt_tokens = self._as_int(
            raw.get("prompt_eval_count"),
        )
        completion_tokens = self._as_int(
            raw.get("eval_count"),
        )

        return {
            "provider": self.name,
            "model": str(raw.get("model", model)),
            "role": str(message.get("role", "assistant")),
            "content": str(message.get("content", "")),
            "thinking": message.get("thinking"),
            "tool_calls": ToolParser.parse(raw),
            "done": bool(raw.get("done", False)),
            "done_reason": raw.get("done_reason"),
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "total_duration_ns": self._as_int(
                    raw.get("total_duration"),
                ),
                "load_duration_ns": self._as_int(
                    raw.get("load_duration"),
                ),
            },
            "raw": raw,
        }

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        payload.update(kwargs)
        payload["stream"] = True

        try:
            async with self.client.stream(
                method="POST",
                url="/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise RuntimeError(
                            "Ollama returned an invalid streaming event.",
                        ) from exc

                    if not isinstance(raw, dict):
                        continue

                    message = raw.get("message", {})

                    if not isinstance(message, dict):
                        message = {}

                    prompt_tokens = self._as_int(
                        raw.get("prompt_eval_count"),
                    )
                    completion_tokens = self._as_int(
                        raw.get("eval_count"),
                    )

                    yield {
                        "provider": self.name,
                        "model": str(raw.get("model", model)),
                        "role": str(
                            message.get("role", "assistant"),
                        ),
                        "content": str(
                            message.get("content", ""),
                        ),
                        "thinking": message.get("thinking"),
                        "tool_calls": ToolParser.parse(raw),
                        "done": bool(raw.get("done", False)),
                        "done_reason": raw.get("done_reason"),
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": (prompt_tokens + completion_tokens),
                        },
                        "raw": raw,
                    }

        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Ollama stream timed out after {self.timeout} seconds.",
            ) from exc

        except httpx.ConnectError as exc:
            raise RuntimeError(
                "Unable to connect to the Ollama server.",
            ) from exc

        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}",
            ) from exc

    async def embeddings(
        self,
        model: str,
        inputs: list[str],
        **kwargs: Any,
    ) -> list[list[float]]:
        if not inputs:
            return []

        payload: dict[str, Any] = {
            "model": model,
            "input": inputs,
        }
        payload.update(kwargs)

        raw = await self._request(
            "POST",
            "/api/embed",
            payload,
        )

        embeddings = raw.get("embeddings", [])

        if not isinstance(embeddings, list):
            raise TypeError(
                "Ollama did not return a valid embeddings list.",
            )

        return [
            [float(value) for value in embedding]
            for embedding in embeddings
            if isinstance(embedding, list)
        ]

    async def show_model(
        self,
        model: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/show",
            {"model": model},
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        await self.close()

    @staticmethod
    def _as_int(value: Any) -> int:
        if isinstance(value, bool):
            return int(value)

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return int(value)

        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0

        return 0
