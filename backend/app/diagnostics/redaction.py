from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "content",
    "cookie",
    "credential",
    "input",
    "output",
    "password",
    "prompt",
    "secret",
    "token",
}
_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+"),
    re.compile(r"(?i)\bsk-[a-z0-9_-]{8,}\b"),
    re.compile(r"(?i)((?:password|token|api[_-]?key|secret)\s*[:=]\s*)\S+"),
)


class Redactor:
    def __init__(self, known_secrets: list[str] | None = None) -> None:
        self._known = sorted((item for item in known_secrets or [] if item), key=len, reverse=True)

    def text(self, value: str) -> str:
        redacted = value
        for secret in self._known:
            redacted = redacted.replace(secret, "[REDACTED]")
        redacted = _PATTERNS[0].sub(r"\1[REDACTED]", redacted)
        redacted = _PATTERNS[1].sub("[REDACTED]", redacted)
        return _PATTERNS[2].sub(r"\1[REDACTED]", redacted)

    def value(self, value: Any, *, key: str | None = None) -> Any:
        if key is not None and key.casefold() in _SENSITIVE_KEYS:
            return "[REDACTED]"
        if isinstance(value, str):
            return self.text(value)
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, dict):
            return {
                self.text(str(item)): self.value(content, key=str(item))
                for item, content in value.items()
            }
        if isinstance(value, (list, tuple, set, frozenset)):
            return [self.value(item) for item in value]
        return self.text(str(value))
