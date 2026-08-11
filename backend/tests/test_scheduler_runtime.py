from datetime import UTC, datetime, timedelta

import pytest

from app.scheduler import (
    SchedulerDisabledError,
    SchedulerPermissionError,
    SchedulerRuntime,
)


@pytest.mark.asyncio
async def test_scheduler_is_disabled_and_actions_are_allowlisted() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(SchedulerDisabledError):
        await SchedulerRuntime({}).run_due()
    runtime = SchedulerRuntime({}, enabled=True, clock=lambda: now)
    with pytest.raises(SchedulerPermissionError):
        runtime.schedule(action="shell.exec", arguments={}, run_at=now, consent=True)


def test_schedule_requires_consent_and_can_be_cancelled_and_audited() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    async def action(_: dict[str, object]) -> dict[str, object]: return {"ok": True}
    runtime = SchedulerRuntime({"approved.action": action}, enabled=True, clock=lambda: now)
    with pytest.raises(SchedulerPermissionError):
        runtime.schedule(action="approved.action", arguments={}, run_at=now, consent=False)
    job = runtime.schedule(action="approved.action", arguments={}, run_at=now, consent=True)
    assert runtime.cancel(job.id) is True
    assert [event.event for event in runtime.audit()] == ["scheduled", "cancelled"]


@pytest.mark.asyncio
async def test_due_job_runs_once_without_duplicate_delivery() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    calls: list[dict[str, object]] = []
    async def action(arguments: dict[str, object]) -> dict[str, object]: calls.append(arguments); return {"ok": True}
    runtime = SchedulerRuntime({"approved.action": action}, enabled=True, clock=lambda: now)
    job = runtime.schedule(action="approved.action", arguments={"value": 1}, run_at=now, consent=True)
    assert await runtime.run_due() == [job.id]
    assert await runtime.run_due() == []
    assert calls == [{"value": 1}]


@pytest.mark.asyncio
async def test_future_jobs_wait_for_clock() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    current = [now]
    async def action(_: dict[str, object]) -> dict[str, object]: return {"ok": True}
    runtime = SchedulerRuntime({"approved.action": action}, enabled=True, clock=lambda: current[0])
    job = runtime.schedule(action="approved.action", arguments={}, run_at=now + timedelta(seconds=1), consent=True)
    assert await runtime.run_due() == []
    current[0] += timedelta(seconds=1)
    assert await runtime.run_due() == [job.id]


@pytest.mark.asyncio
async def test_state_round_trip_preserves_completed_idempotency() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    calls: list[int] = []
    async def action(_: dict[str, object]) -> dict[str, object]: calls.append(1); return {"ok": True}
    first = SchedulerRuntime({"approved.action": action}, enabled=True, clock=lambda: now)
    first.schedule(action="approved.action", arguments={}, run_at=now, consent=True)
    await first.run_due()
    restarted = SchedulerRuntime({"approved.action": action}, enabled=True, clock=lambda: now)
    restarted.import_state(first.export_state())
    assert await restarted.run_due() == []
    assert calls == [1]
