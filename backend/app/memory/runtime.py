from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.memory.models import MemoryRecord


class MemoryError(RuntimeError):
    """Base error for the bounded memory runtime."""


class MemoryDisabledError(MemoryError):
    """Raised when memory has not been explicitly enabled."""


class MemoryConsentRequiredError(MemoryError):
    """Raised when an operation lacks explicit user consent."""


class MemorySensitiveDataError(MemoryError):
    """Raised when content resembles a credential or secret."""


_LIKELY_SECRET = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+",
)


class MemoryRuntime:
    """Process-local, consent-aware memory with owner/session isolation."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        default_ttl_seconds: int = 3600,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if default_ttl_seconds < 1:
            raise ValueError("default_ttl_seconds must be positive.")
        self.enabled = enabled
        self.default_ttl_seconds = default_ttl_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._records: dict[UUID, MemoryRecord] = {}

    def remember(
        self,
        *,
        owner_id: str,
        session_id: str | None,
        content: str,
        consent: bool,
        ttl_seconds: int | None = None,
    ) -> MemoryRecord:
        self._require_enabled_and_consent(consent)
        normalized = content.strip()
        if _LIKELY_SECRET.search(normalized):
            raise MemorySensitiveDataError("Credential-like content cannot be stored.")
        ttl = ttl_seconds or self.default_ttl_seconds
        if ttl < 1:
            raise ValueError("ttl_seconds must be positive.")
        now = self._clock()
        record = MemoryRecord(
            id=uuid4(), owner_id=owner_id.strip(), session_id=self._session(session_id),
            content=normalized, created_at=now, expires_at=now + timedelta(seconds=ttl),
        )
        self._records[record.id] = record
        return record

    def list_records(self, *, owner_id: str, session_id: str | None) -> list[MemoryRecord]:
        self._require_enabled()
        self._purge_expired()
        owner = owner_id.strip()
        session = self._session(session_id)
        return sorted(
            (item for item in self._records.values() if item.owner_id == owner and item.session_id == session),
            key=lambda item: (item.created_at, str(item.id)),
        )

    def delete(self, *, owner_id: str, session_id: str | None, record_id: UUID) -> bool:
        self._require_enabled()
        record = self._records.get(record_id)
        if record is None:
            return False
        if record.owner_id != owner_id.strip() or record.session_id != self._session(session_id):
            return False
        del self._records[record_id]
        return True

    def export(self, *, owner_id: str, session_id: str | None, consent: bool) -> list[dict[str, object]]:
        self._require_enabled_and_consent(consent)
        return [record.model_dump(mode="json") for record in self.list_records(owner_id=owner_id, session_id=session_id)]

    def _purge_expired(self) -> None:
        now = self._clock()
        expired = [key for key, value in self._records.items() if value.expires_at <= now]
        for key in expired:
            del self._records[key]

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise MemoryDisabledError("Memory is disabled.")

    def _require_enabled_and_consent(self, consent: bool) -> None:
        self._require_enabled()
        if not consent:
            raise MemoryConsentRequiredError("Explicit consent is required.")

    @staticmethod
    def _session(value: str | None) -> str | None:
        return value.strip() if value is not None else None
