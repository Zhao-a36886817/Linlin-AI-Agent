# P23 Completion Report — Backup, Migration, Data Portability, and Recovery

## Scope and root cause

Linlin Agent had secure individual workspace operations and atomic JSON state writes,
but no versioned workspace export, integrity manifest, complete restore rehearsal,
transaction journal, interruption rollback, or measurable recovery evidence. Ad hoc
ZIP extraction could not satisfy deterministic round trips or recovery safety. P23
adds one bounded portability runtime around the accepted Workspace Runtime root and
does not expose a new API or change another runtime boundary.

## Changes and concise diff

- Added deterministic workspace backup format version `1` with canonical manifest,
  fixed ZIP metadata, stable ordering and streaming file writes.
- Recorded every file/directory's portable relative path, logical `workspace` owner,
  permission mode, size and SHA-256 digest; empty directories are preserved.
- Added complete pre-restore verification for schema, limits, duplicate/case-colliding
  names, undeclared hierarchy, hashes, sizes, symlinks, special files and Windows,
  POSIX and Unicode path hazards.
- Added staged full-workspace restore with atomic directory swaps, a restricted
  recovery journal, automatic rollback and restart recovery for `prepared`,
  `old_moved` and `committed` transaction states.
- Added a missing-root recovery bootstrap that runs before backend startup creates
  or imports any Workspace Runtime singleton, closing the P23-GATE-01 startup-order
  defect found by the first two Gate reviews.
- Added non-mutating restore rehearsal plus measured RTO and zero-loss RPO evidence.
- Kept Credential Store, OS keyring, environment credentials, models, logs and all
  non-workspace paths outside the export boundary.
- Added P23 operational/security documentation, automated tests and Supervisor
  policy.

## Modified files

- `.laes/SUPERVISOR_POLICY.yaml`
- `backend/app/portability/__init__.py`
- `backend/app/portability/runtime.py`
- `backend/app/bootstrap.py`
- `backend/app/main.py`
- `backend/tests/test_portability_runtime.py`
- `docs/development/PORTABILITY_RECOVERY.md`
- `P23_COMPLETION_REPORT.md`

## Validation

- Round-trip, deterministic export, migration rejection, rollback, crash recovery,
  corruption, malicious archive, rehearsal, RPO/RTO, metadata and credential-boundary
  tests: `14 passed, 1 skipped`.
- Backend byte compilation: PASS.
- Ruff across `app` and `tests`: PASS with no findings.
- Full backend regression: `196 passed, 2 skipped`.
- The two skips are environment-dependent: the existing training execution test and
  a source-symlink test when the current Windows account cannot create symlinks. A
  crafted archive symlink rejection test executed and passed.
- Existing framework deprecation warnings: 24; no validation failure.
- Exact repeated Supervisor commands and output are recorded in
  `P23_SUPERVISOR_REVIEW_PACKAGE.md`.

## Security and privacy

The runtime never reads Credential Store or arbitrary roots, never trusts an archive
destination, requires the archive outside the live workspace, rejects links and
cross-platform traversal forms, and validates all bytes before touching live data.
The recovery journal contains only a schema version, random transaction UUID and
state; it contains no path, content or credential. Workspace export is an explicit
user-data operation, so the resulting archive must be protected according to its
user-controlled contents.

## Cross-platform and migrations

Paths use `pathlib` and canonical POSIX archive names. Case collisions, Unicode
normalization, Windows device names/drives and both slash conventions are checked so
an archive accepted on one supported platform remains safe on another. OS-specific
user/group IDs and modification times are not portable and are intentionally omitted;
logical ownership and portable permission bits are preserved. Unknown schema
versions fail closed and require an explicitly reviewed migration.

## Rollback

If a restore fails, the transaction journal restores the pre-restore workspace. On a
later process start, `recover_interrupted()` rolls back incomplete work or completes
committed cleanup. To remove P23 itself, first recover any pending journal, then
remove the portability module, tests, documentation and P23 policy/report entries;
existing workspace data and external backup archives remain unchanged.

## Remaining risks and deviations

RTO is measured on the current filesystem and is not a universal service guarantee;
operators must rehearse representative production sizes. Version `1` covers the
Workspace Runtime only; credentials intentionally require separate provisioning and
no provider/model/log backup was added. Backup encryption and remote retention are
not part of this bounded phase, so operators must secure exported workspace archives.
Callers must serialize restore operations because a cross-process restore lock is not
part of version `1`; backup creation detects content changes by rechecking size and
SHA-256, but operators should still avoid concurrent workspace mutation. The initial
Gate correctly rejected missing-root restart recovery; that defect is now covered by
the startup bootstrap and fresh-runtime regression test. There are no known P23
specification deviations and no frontend, desktop, provider/tool/credential runtime,
model, nested-repository or future-phase files were changed.
