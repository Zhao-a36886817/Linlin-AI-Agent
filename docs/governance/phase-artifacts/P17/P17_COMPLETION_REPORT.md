# P17 Completion Report — Observability, Audit, and Diagnostics

## Scope and root cause

The runtime lacked one bounded, privacy-preserving contract for correlating failures
and exporting local diagnostics. P17 adds a local in-memory diagnostics boundary;
it does not instrument unrelated subsystems, introduce telemetry, or redesign
performance-sensitive paths.

## Changes

- Added immutable structured event and health snapshot contracts.
- Added correlation IDs, bounded FIFO retention, cumulative health counters,
  attributable actors, failure summaries, correlation filtering, and JSON-safe
  diagnostic bundles.
- Added recursive redaction for configured secrets, secret-bearing keys, common
  credential patterns, dictionary keys, and private prompt/content/input/output
  fields.
- Documented local-only behavior, retention, privacy requirements, and export
  semantics in `docs/development/DIAGNOSTICS.md`.
- Added focused redaction, retention, correlation, failure, and bundle tests plus
  the retention setting and P17 policy.

## Security and privacy

The service has no transport and does not automatically collect prompts or file
content. Every accepted event field passes through redaction before retention.
Bundles contain only already-redacted retained events and aggregate counters.

## Cross-platform and migrations

The implementation uses only platform-neutral Python collections, UUIDs, and UTC
timestamps. There is no persistent store, schema migration, or platform adapter.

## Validation

- `python -m ruff check app/diagnostics tests/test_diagnostics_runtime.py`: PASS.
- `python -m pytest tests/test_diagnostics_runtime.py -q`: 6 passed.
- Complete Supervisor results are recorded in
  `P17_SUPERVISOR_REVIEW_PACKAGE.md`.

## Rollback

Remove `backend/app/diagnostics`, its test, the diagnostics guide and retention
setting, and P17 policy/report entries. No stored diagnostic data requires cleanup.

## Remaining risks and deviations

Redaction is defense-in-depth, not permission to submit arbitrary private payloads;
callers must continue to use static operational summaries and omit raw content.
Counters reset on process restart by design. There are no known P17 deviations.
