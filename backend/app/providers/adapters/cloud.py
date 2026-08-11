from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.providers.adapters.base import BaseProvider
from app.providers.models import ProviderCostClass, ProviderKind

_OPENAI_PROTOCOLS = {
    ProviderKind.OPENAI,
    ProviderKind.OPENROUTER,
    ProviderKind.GROQ,
    ProviderKind.DEEPSEEK,
    ProviderKind.MISTRAL,
    ProviderKind.OPENAI_COMPATIBLE,
}

_NVIDIA_HOSTED_API_HOSTS = {
    "ai.api.nvidia.com",
    "integrate.api.nvidia.com",
}


class DynamicCloudProvider(BaseProvider):
    """Runtime-configured cloud adapter with normalized provider contracts."""

    supports_stream = True
    supports_tools = True
    requires_api_key = True
    local = False
    cost_class = ProviderCostClass.UNKNOWN

    def __init__(
        self,
        *,
        name: str,
        kind: ProviderKind,
        base_url: str,
        api_key: str,
        timeout: float = 120,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self.kind = kind
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key.strip()
        if not self._api_key:
            raise ValueError("Cloud provider API key cannot be empty.")
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            base_url=f"{self.base_url}/",
            timeout=httpx.Timeout(timeout),
        )

    async def list_models(self) -> list[dict[str, Any]]:
        raw = await self._request("GET", "models")
        source = raw.get("data", raw.get("models", []))
        if not isinstance(source, list):
            raise TypeError("Cloud provider returned an invalid model list.")
        models: list[dict[str, Any]] = []
        for item in source:
            if not isinstance(item, dict):
                continue
            identifier = item.get("id", item.get("name"))
            if not isinstance(identifier, str) or not identifier:
                continue
            models.append({
                "name": identifier,
                "capabilities": ["completion", "stream", "tools"],
            })
        return models

    async def health(self) -> bool:
        try:
            await self.list_models()
            return True
        except RuntimeError:
            return False

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        if self.kind in _OPENAI_PROTOCOLS:
            return await self._openai_chat(model, messages, kwargs)
        if self.kind == ProviderKind.ANTHROPIC:
            return await self._anthropic_chat(model, messages, kwargs)
        if self.kind == ProviderKind.GEMINI:
            return await self._gemini_chat(model, messages, kwargs)
        raise RuntimeError(f"Unsupported cloud provider kind '{self.kind}'.")

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        if self.kind in _OPENAI_PROTOCOLS:
            async for event in self._openai_stream(model, messages, kwargs):
                yield event
            return
        if self.kind == ProviderKind.ANTHROPIC:
            async for event in self._anthropic_stream(model, messages, kwargs):
                yield event
            return
        if self.kind == ProviderKind.GEMINI:
            async for event in self._gemini_stream(model, messages, kwargs):
                yield event
            return
        raise RuntimeError(f"Unsupported cloud provider kind '{self.kind}'.")

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self.client.request(
                method,
                endpoint,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise TypeError("Cloud provider returned invalid JSON.")
            return result
        except httpx.TimeoutException as exc:
            raise RuntimeError("Cloud provider request timed out.") from exc
        except httpx.ConnectError as exc:
            raise RuntimeError("Unable to connect to the cloud provider endpoint.") from exc
        except httpx.HTTPStatusError as exc:
            raise self._http_error(exc.response) from exc
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise RuntimeError("Cloud provider returned invalid JSON.") from exc

    def _headers(self) -> dict[str, str]:
        if self.kind == ProviderKind.ANTHROPIC:
            return {
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        if self.kind == ProviderKind.GEMINI:
            return {"x-goog-api-key": self._api_key, "content-type": "application/json"}
        return {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }

    @staticmethod
    def is_nvidia_hosted_endpoint(base_url: str) -> bool:
        host = (urlparse(base_url).hostname or "").lower()
        return host in _NVIDIA_HOSTED_API_HOSTS

    def _http_error(self, response: httpx.Response) -> RuntimeError:
        status = response.status_code
        if self.is_nvidia_hosted_endpoint(self.base_url):
            if status == 401:
                return RuntimeError(
                    "NVIDIA rejected the API key (HTTP 401). Use a Hosted Inference "
                    "key beginning with 'nvapi-' from "
                    "https://build.nvidia.com/settings/api-keys.",
                )
            if status == 403:
                return RuntimeError(
                    "NVIDIA denied model access (HTTP 403). The API key lacks "
                    "permission for this hosted model; create a new Hosted Inference "
                    "key at https://build.nvidia.com/settings/api-keys and accept any "
                    "model access terms shown by NVIDIA.",
                )
        if status == 401:
            return RuntimeError(
                "Cloud provider rejected the API credential (HTTP 401).",
            )
        if status == 403:
            return RuntimeError(
                "Cloud provider denied access (HTTP 403). Check that the API key is "
                "authorized for the selected endpoint and model.",
            )
        return RuntimeError(f"Cloud provider returned HTTP {status}.")

    @staticmethod
    def _options(kwargs: dict[str, Any]) -> dict[str, Any]:
        source = kwargs.get("options", {})
        return source if isinstance(source, dict) else {}

    def _base_result(
        self,
        model: str,
        *,
        content: str,
        thinking: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        done: bool = True,
        done_reason: str | None = None,
        usage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": model,
            "role": "assistant",
            "content": content,
            "thinking": thinking,
            "tool_calls": tool_calls or [],
            "done": done,
            "done_reason": done_reason,
            "usage": usage or {},
        }

    async def _openai_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        options = self._options(kwargs)
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
        for source, target in (
            ("temperature", "temperature"),
            ("top_p", "top_p"),
            ("num_predict", "max_tokens"),
            ("seed", "seed"),
        ):
            if options.get(source) is not None:
                payload[target] = options[source]
        raw = await self._request("POST", "chat/completions", payload)
        choices = raw.get("choices", [])
        choice = choices[0] if isinstance(choices, list) and choices else {}
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        if not isinstance(message, dict):
            message = {}
        usage = raw.get("usage", {}) if isinstance(raw.get("usage"), dict) else {}
        prompt = int(usage.get("prompt_tokens", 0) or 0)
        completion = int(usage.get("completion_tokens", 0) or 0)
        return self._base_result(
            str(raw.get("model", model)),
            content=str(message.get("content", "") or ""),
            thinking=message.get("reasoning_content"),
            tool_calls=message.get("tool_calls") if isinstance(message.get("tool_calls"), list) else [],
            done_reason=choice.get("finish_reason") if isinstance(choice, dict) else None,
            usage={
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": int(usage.get("total_tokens", prompt + completion) or 0),
            },
        )

    async def _openai_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        options = self._options(kwargs)
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
        if options.get("temperature") is not None:
            payload["temperature"] = options["temperature"]
        if options.get("num_predict") is not None:
            payload["max_tokens"] = options["num_predict"]
        async for raw in self._sse("chat/completions", payload):
            choices = raw.get("choices", [])
            choice = choices[0] if isinstance(choices, list) and choices else {}
            delta = choice.get("delta", {}) if isinstance(choice, dict) else {}
            if not isinstance(delta, dict):
                delta = {}
            finish = choice.get("finish_reason") if isinstance(choice, dict) else None
            yield self._base_result(
                str(raw.get("model", model)),
                content=str(delta.get("content", "") or ""),
                thinking=delta.get("reasoning_content"),
                tool_calls=delta.get("tool_calls") if isinstance(delta.get("tool_calls"), list) else [],
                done=finish is not None,
                done_reason=finish,
            )

    @staticmethod
    def _anthropic_messages(
        messages: list[dict[str, Any]],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        systems = [str(item.get("content", "")) for item in messages if item.get("role") == "system"]
        regular = [item for item in messages if item.get("role") != "system"]
        return ("\n\n".join(systems) or None), regular

    async def _anthropic_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        options = self._options(kwargs)
        system, regular = self._anthropic_messages(messages)
        payload: dict[str, Any] = {
            "model": model,
            "messages": regular,
            "max_tokens": int(options.get("num_predict", 512)),
        }
        if system:
            payload["system"] = system
        if options.get("temperature") is not None:
            payload["temperature"] = options["temperature"]
        raw = await self._request("POST", "messages", payload)
        blocks = raw.get("content", [])
        text = "".join(
            str(block.get("text", ""))
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ) if isinstance(blocks, list) else ""
        usage = raw.get("usage", {}) if isinstance(raw.get("usage"), dict) else {}
        prompt = int(usage.get("input_tokens", 0) or 0)
        completion = int(usage.get("output_tokens", 0) or 0)
        return self._base_result(
            str(raw.get("model", model)),
            content=text,
            done_reason=str(raw.get("stop_reason", "") or "") or None,
            usage={"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion},
        )

    async def _anthropic_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        options = self._options(kwargs)
        system, regular = self._anthropic_messages(messages)
        payload: dict[str, Any] = {
            "model": model,
            "messages": regular,
            "max_tokens": int(options.get("num_predict", 512)),
            "stream": True,
        }
        if system:
            payload["system"] = system
        async for raw in self._sse("messages", payload):
            event_type = raw.get("type")
            delta = raw.get("delta", {}) if isinstance(raw.get("delta"), dict) else {}
            content = str(delta.get("text", "")) if event_type == "content_block_delta" else ""
            done = event_type == "message_stop"
            yield self._base_result(model, content=content, done=done)

    @staticmethod
    def _gemini_contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "role": "model" if item.get("role") == "assistant" else "user",
                "parts": [{"text": str(item.get("content", ""))}],
            }
            for item in messages
        ]

    async def _gemini_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        options = self._options(kwargs)
        payload = {
            "contents": self._gemini_contents(messages),
            "generationConfig": {
                "temperature": options.get("temperature", 0.3),
                "maxOutputTokens": options.get("num_predict", 512),
            },
        }
        model_id = quote(model.removeprefix("models/"), safe="")
        raw = await self._request("POST", f"models/{model_id}:generateContent", payload)
        content, reason = self._gemini_text(raw)
        usage = raw.get("usageMetadata", {}) if isinstance(raw.get("usageMetadata"), dict) else {}
        prompt = int(usage.get("promptTokenCount", 0) or 0)
        completion = int(usage.get("candidatesTokenCount", 0) or 0)
        return self._base_result(
            model,
            content=content,
            done_reason=reason,
            usage={"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": int(usage.get("totalTokenCount", prompt + completion) or 0)},
        )

    async def _gemini_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        options = self._options(kwargs)
        payload = {
            "contents": self._gemini_contents(messages),
            "generationConfig": {"maxOutputTokens": options.get("num_predict", 512)},
        }
        model_id = quote(model.removeprefix("models/"), safe="")
        async for raw in self._sse(f"models/{model_id}:streamGenerateContent?alt=sse", payload):
            content, reason = self._gemini_text(raw)
            yield self._base_result(model, content=content, done=reason is not None, done_reason=reason)

    @staticmethod
    def _gemini_text(raw: dict[str, Any]) -> tuple[str, str | None]:
        candidates = raw.get("candidates", [])
        candidate = candidates[0] if isinstance(candidates, list) and candidates else {}
        content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
        reason = candidate.get("finishReason") if isinstance(candidate, dict) else None
        return text, str(reason) if reason else None

    async def _sse(
        self,
        endpoint: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            async with self.client.stream(
                "POST",
                endpoint,
                headers={**self._headers(), "accept": "text/event-stream"},
                json=payload,
            ) as response:
                if not response.is_success:
                    await response.aread()
                    raise self._http_error(response)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    raw = json.loads(data)
                    if isinstance(raw, dict):
                        yield raw
        except httpx.TimeoutException as exc:
            raise RuntimeError("Cloud provider stream timed out.") from exc
        except httpx.ConnectError as exc:
            raise RuntimeError("Unable to connect to the cloud provider endpoint.") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Cloud provider returned an invalid stream event.") from exc
