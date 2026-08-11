from __future__ import annotations

from uuid import UUID

from app.memory import MemoryRecord, MemoryRuntime


class AgentMemory:
    """Agent Runtime facade; providers never own or invoke memory."""

    def __init__(self, runtime: MemoryRuntime) -> None:
        self._runtime = runtime

    def remember(self, **kwargs: object) -> MemoryRecord:
        return self._runtime.remember(**kwargs)  # type: ignore[arg-type]

    def recall(self, *, owner_id: str, session_id: str | None) -> list[MemoryRecord]:
        return self._runtime.list_records(owner_id=owner_id, session_id=session_id)

    def forget(self, *, owner_id: str, session_id: str | None, record_id: UUID) -> bool:
        return self._runtime.delete(owner_id=owner_id, session_id=session_id, record_id=record_id)

    def export(self, *, owner_id: str, session_id: str | None, consent: bool) -> list[dict[str, object]]:
        return self._runtime.export(owner_id=owner_id, session_id=session_id, consent=consent)
