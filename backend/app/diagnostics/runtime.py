from __future__ import annotations

from collections import Counter, deque
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from app.diagnostics.models import DiagnosticEvent, HealthSnapshot
from app.diagnostics.redaction import Redactor


class DiagnosticsRuntime:
    """Bounded local diagnostics with mandatory redaction and no transport."""

    def __init__(
        self,
        *,
        retention: int = 500,
        known_secrets: list[str] | None = None,
    ) -> None:
        if retention < 1 or retention > 100_000:
            raise ValueError("Diagnostic retention must be between 1 and 100000.")
        self._events: deque[DiagnosticEvent] = deque(maxlen=retention)
        self._counts: Counter[str] = Counter()
        self._redactor = Redactor(known_secrets)

    @staticmethod
    def correlation_id() -> UUID:
        return uuid4()

    def emit(
        self,
        *,
        correlation_id: UUID,
        component: str,
        code: str,
        severity: Literal["info", "warning", "error"],
        summary: str,
        actor: str = "system",
        attributes: dict[str, Any] | None = None,
    ) -> DiagnosticEvent:
        event = DiagnosticEvent(
            correlation_id=correlation_id,
            component=component,
            code=code,
            severity=severity,
            actor=self._redactor.text(actor),
            summary=self._redactor.text(summary),
            attributes=self._redactor.value(attributes or {}),
        )
        self._events.append(event)
        self._counts[severity] += 1
        self._counts[code] += 1
        return event

    def record_failure(
        self,
        *,
        correlation_id: UUID,
        component: str,
        code: str,
        error: BaseException,
        actor: str = "system",
    ) -> DiagnosticEvent:
        return self.emit(
            correlation_id=correlation_id,
            component=component,
            code=code,
            severity="error",
            summary=f"{type(error).__name__}: {error}",
            actor=actor,
            attributes={"exception_type": type(error).__name__},
        )

    def events(self, *, correlation_id: UUID | None = None) -> list[DiagnosticEvent]:
        if correlation_id is None:
            return list(self._events)
        return [item for item in self._events if item.correlation_id == correlation_id]

    def health(self) -> HealthSnapshot:
        return HealthSnapshot(
            total_events=sum(self._counts[level] for level in ("info", "warning", "error")),
            info_events=self._counts["info"],
            warning_events=self._counts["warning"],
            error_events=self._counts["error"],
            retained_events=len(self._events),
        )

    def bundle(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "health": self.health().model_dump(mode="json"),
            "events": [item.model_dump(mode="json") for item in self._events],
        }
