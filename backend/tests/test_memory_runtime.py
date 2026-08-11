from datetime import UTC, datetime, timedelta

import pytest

from app.agents.memory import AgentMemory
from app.memory import (
    MemoryConsentRequiredError,
    MemoryDisabledError,
    MemoryRuntime,
    MemorySensitiveDataError,
)


def test_memory_is_disabled_by_default() -> None:
    memory = AgentMemory(MemoryRuntime())
    with pytest.raises(MemoryDisabledError):
        memory.recall(owner_id="owner-a", session_id="session-a")


def test_memory_requires_consent_and_rejects_likely_secrets() -> None:
    memory = AgentMemory(MemoryRuntime(enabled=True))
    with pytest.raises(MemoryConsentRequiredError):
        memory.remember(owner_id="owner", session_id="session", content="preference", consent=False)
    with pytest.raises(MemorySensitiveDataError):
        memory.remember(owner_id="owner", session_id="session", content="api_key=not-a-real-key", consent=True)


def test_owner_and_session_scopes_do_not_leak() -> None:
    memory = AgentMemory(MemoryRuntime(enabled=True))
    saved = memory.remember(owner_id="owner-a", session_id="one", content="prefers concise answers", consent=True)
    assert memory.recall(owner_id="owner-a", session_id="one") == [saved]
    assert memory.recall(owner_id="owner-a", session_id="two") == []
    assert memory.recall(owner_id="owner-b", session_id="one") == []
    assert memory.forget(owner_id="owner-b", session_id="one", record_id=saved.id) is False


def test_retention_delete_and_export_are_deterministic() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    current = [now]
    memory = AgentMemory(MemoryRuntime(enabled=True, clock=lambda: current[0]))
    saved = memory.remember(owner_id="owner", session_id=None, content="remember me", consent=True, ttl_seconds=10)
    assert memory.export(owner_id="owner", session_id=None, consent=True)[0]["content"] == "remember me"
    current[0] = now + timedelta(seconds=10)
    assert memory.recall(owner_id="owner", session_id=None) == []
    assert memory.forget(owner_id="owner", session_id=None, record_id=saved.id) is False


def test_export_requires_consent() -> None:
    memory = AgentMemory(MemoryRuntime(enabled=True))
    with pytest.raises(MemoryConsentRequiredError):
        memory.export(owner_id="owner", session_id=None, consent=False)
