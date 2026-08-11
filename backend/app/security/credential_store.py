from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol


class CredentialNotFoundError(LookupError):
    """Raised when a requested credential is unavailable."""


class CredentialBackend(Protocol):
    persistent: bool
    name: str

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> None: ...


class SessionCredentialBackend:
    """Non-persistent fallback that lasts only for this process."""

    persistent = False
    name = "session"

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def set(self, key: str, value: str) -> None:
        self._values[key] = value

    def delete(self, key: str) -> None:
        self._values.pop(key, None)


class KeyringCredentialBackend:
    """OS-backed adapter for the optional keyring package."""

    persistent = True
    name = "os_keyring"

    def __init__(self, service: str = "linlin-agent") -> None:
        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError("OS keyring support is unavailable.") from exc
        self._keyring = keyring
        self._service = service

    def get(self, key: str) -> str | None:
        return self._keyring.get_password(self._service, key)

    def set(self, key: str, value: str) -> None:
        self._keyring.set_password(self._service, key, value)

    def delete(self, key: str) -> None:
        try:
            self._keyring.delete_password(self._service, key)
        except self._keyring.errors.PasswordDeleteError:
            return


def default_credential_backend() -> CredentialBackend:
    """Prefer the OS credential vault, with an explicit session fallback."""

    try:
        backend = KeyringCredentialBackend()
        selected = backend._keyring.get_keyring()
        if float(getattr(selected, "priority", 0)) > 0:
            return backend
    except (ImportError, RuntimeError, TypeError, ValueError):
        pass
    return SessionCredentialBackend()


class CredentialStore:
    """Credential boundary with explicit persistence and environment fallback."""

    def __init__(
        self,
        backend: CredentialBackend | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.backend = backend or SessionCredentialBackend()
        self._environment = environment if environment is not None else os.environ

    @property
    def persistent(self) -> bool:
        return self.backend.persistent

    def get(self, key: str) -> str:
        normalized = key.strip()
        if not normalized:
            raise ValueError("Credential key cannot be empty.")
        value = self.backend.get(normalized) or self._environment.get(normalized)
        if not value:
            raise CredentialNotFoundError(f"Credential '{normalized}' is unavailable.")
        return value

    def has(self, key: str | None) -> bool:
        if not key:
            return False
        try:
            self.get(key)
        except CredentialNotFoundError:
            return False
        return True

    def set(self, key: str, value: str) -> None:
        if not key.strip() or not value:
            raise ValueError("Credential key and value cannot be empty.")
        self.backend.set(key.strip(), value)

    def delete(self, key: str) -> None:
        self.backend.delete(key.strip())


credential_store = CredentialStore(default_credential_backend())
