from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.scheduler.models import AuditEvent, ScheduledJob

Action = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class SchedulerError(RuntimeError):
    pass


class SchedulerDisabledError(SchedulerError):
    pass


class SchedulerPermissionError(SchedulerError):
    pass


class SchedulerRuntime:
    """Explicitly ticked scheduler for approved application actions only."""

    def __init__(self, actions: dict[str, Action], *, enabled: bool = False, clock: Callable[[], datetime] | None = None) -> None:
        self._actions = dict(actions)
        self.enabled = enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._jobs: dict[UUID, ScheduledJob] = {}
        self._audit: list[AuditEvent] = []

    def schedule(self, *, action: str, arguments: dict[str, Any], run_at: datetime, consent: bool, max_attempts: int = 1) -> ScheduledJob:
        self._require_enabled()
        if not consent:
            raise SchedulerPermissionError("Explicit scheduling consent is required.")
        if action not in self._actions:
            raise SchedulerPermissionError(f"Action '{action}' is not approved.")
        job = ScheduledJob(id=uuid4(), action=action, arguments=arguments, run_at=run_at, max_attempts=max_attempts)
        self._jobs[job.id] = job
        self._record(job.id, "scheduled")
        return job

    def list_jobs(self) -> list[ScheduledJob]:
        self._require_enabled()
        return [self._jobs[key] for key in sorted(self._jobs, key=str)]

    def cancel(self, job_id: UUID) -> bool:
        self._require_enabled()
        job = self._jobs.get(job_id)
        if job is None or job.status != "scheduled":
            return False
        self._jobs[job_id] = job.model_copy(update={"status": "cancelled"})
        self._record(job_id, "cancelled")
        return True

    async def run_due(self) -> list[UUID]:
        self._require_enabled()
        completed: list[UUID] = []
        for job in list(self.list_jobs()):
            if job.status != "scheduled" or job.run_at > self._clock():
                continue
            attempt = job.attempts + 1
            try:
                await self._actions[job.action](dict(job.arguments))
            except Exception:  # noqa: BLE001 - action boundary converts failures to job state
                status = "failed" if attempt >= job.max_attempts else "scheduled"
                self._jobs[job.id] = job.model_copy(update={"attempts": attempt, "status": status})
                self._record(job.id, status)
                continue
            self._jobs[job.id] = job.model_copy(update={"attempts": attempt, "status": "completed"})
            self._record(job.id, "completed")
            completed.append(job.id)
        return completed

    def audit(self) -> list[AuditEvent]:
        return list(self._audit)

    def export_state(self) -> dict[str, list[dict[str, Any]]]:
        self._require_enabled()
        return {
            "jobs": [job.model_dump(mode="json") for job in self.list_jobs()],
            "audit": [event.model_dump(mode="json") for event in self._audit],
        }

    def import_state(self, state: dict[str, Any]) -> None:
        self._require_enabled()
        jobs = [ScheduledJob.model_validate(item) for item in state.get("jobs", [])]
        audit = [AuditEvent.model_validate(item) for item in state.get("audit", [])]
        self._jobs = {job.id: job for job in jobs}
        self._audit = audit

    def _record(self, job_id: UUID, event: str) -> None:
        self._audit.append(AuditEvent(job_id=job_id, event=event, occurred_at=self._clock()))

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise SchedulerDisabledError("Scheduler is disabled.")
