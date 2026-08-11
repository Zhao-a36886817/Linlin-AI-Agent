from __future__ import annotations

from typing import Any

REDACTED = "[REDACTED]"


def redact_secrets(value: Any, secrets: list[str]) -> Any:
    """Return a copy with known non-empty secret values removed."""

    active = [secret for secret in secrets if secret]
    if isinstance(value, str):
        result = value
        for secret in active:
            result = result.replace(secret, REDACTED)
        return result
    if isinstance(value, dict):
        return {key: redact_secrets(item, active) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secrets(item, active) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item, active) for item in value)
    return value
