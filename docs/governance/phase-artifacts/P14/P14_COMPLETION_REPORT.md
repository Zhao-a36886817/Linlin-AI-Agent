# P14 Completion Report — Scheduler and Automation Runtime

## Scope and root cause

P14 required a bounded automation runtime, but the repository had no schedule model,
approved-action dispatch boundary, persistence contract, cancellation path, retry
limit, or audit history. The implementation adds only that phase scope.

## Changes

- Added immutable schedule and audit models.
- Added an explicitly enabled scheduler that accepts only injected, allowlisted
  application actions and requires scheduling consent.
- Added deterministic list/cancel, bounded retry, audit, due-job execution, and
  state export/import behavior.
- Preserved completed state across restart so a completed job is not delivered
  twice.
- Added the disabled-by-default configuration flag and focused authorization,
  clock, cancellation, persistence, and idempotency tests.

## Security and privacy

Raw shell scheduling and implicit actions are absent. Unknown actions and schedules
without explicit consent are rejected. Arguments stay within the caller-provided
application action boundary; no credential or workspace boundary is bypassed.

## Cross-platform and migrations

The implementation uses only Python runtime abstractions and UTC-aware clocks; it
has no OS-specific process or filesystem behavior. There is no database migration.
Persisted state is exposed as validated JSON-compatible data for the owning host to
store atomically.

## Validation

- `python -m ruff check app/scheduler tests/test_scheduler_runtime.py`: PASS.
- `python -m pytest tests/test_scheduler_runtime.py -q`: 5 passed.
- The complete Supervisor validation results are recorded in
  `P14_SUPERVISOR_REVIEW_PACKAGE.md`.

## Rollback

Remove `backend/app/scheduler`, its focused test, the `scheduler_enabled` setting,
and the P14 Supervisor policy/report entries. No persistent schema rollback is
required.

## Remaining risks and deviations

The host application is responsible for durable, atomic storage of exported state
and for ensuring only one scheduler worker owns a given state store. Distributed
leases and multi-agent orchestration are intentionally outside P14. There are no
known deviations from the phase specification.
