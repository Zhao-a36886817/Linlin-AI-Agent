# P15 Completion Report — Multi-Agent Orchestration

## Scope and root cause

The repository had no bounded contract for delegating work between agent roles.
Without a central boundary, delegation could amplify permissions, cost, iterations,
depth, or concurrency. P15 adds only contracts and an injected execution boundary;
it does not add providers, tools, background workers, or multimodal behavior.

## Changes

- Added immutable role, context, request, budget, execution, and result contracts.
- Added a disabled-by-default runtime with registered caller contexts, explicit
  child permissions, role allowlists, depth and role-loop checks, and a global
  concurrency cap.
- Added atomic budget reservation and usage settlement so concurrent children
  cannot each claim the caller's full budget.
- Added recursive cancellation signals for active descendants.
- Added focused tests for privilege escalation, forged contexts, aggregate budget
  amplification, depth, loops, concurrency, cancellation, and reported usage.
- Added the configuration flag and P15 Supervisor policy.

## Security and privacy

Children receive only permissions explicitly requested and present in both the
registered caller context and target role. No provider, tool, workspace, credential,
network, or process access is implemented. Task data is passed only to the injected
executor and is not persisted or logged by this runtime.

## Cross-platform and migrations

The implementation uses platform-neutral Python and asyncio primitives. There are
no filesystem assumptions, database migrations, or OS-specific services.

## Validation

- `python -m ruff check app/orchestration tests/test_orchestration_runtime.py`: PASS.
- `python -m pytest tests/test_orchestration_runtime.py -q`: 7 passed.
- Complete Supervisor validation is recorded in
  `P15_SUPERVISOR_REVIEW_PACKAGE.md`.

## Rollback

Remove `backend/app/orchestration`, its focused test, the configuration flag, and
the P15 policy/report entries. No stored data requires migration.

## Remaining risks and deviations

The injected executor must report inclusive iteration and cost usage accurately;
an over-budget report is rejected and its reservation remains consumed
conservatively. Cross-process/distributed coordination is intentionally absent.
There are no known deviations from P15.
