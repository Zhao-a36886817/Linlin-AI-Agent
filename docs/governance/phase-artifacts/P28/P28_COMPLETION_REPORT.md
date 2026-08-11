# P28 Completion Report — Workspace-Safe Code Generation

## Stage

P28 — Workspace-Safe Code Generation

## Root cause

Chat could ask a model for code as unstructured text, but Linlin had no safe
product contract that associated output with a target file, validated it, showed
a diff, required explicit apply consent, or prevented workspace escape and stale
overwrites.

## Changes

- Added a Provider-Runtime-backed code proposal service with dynamic model
  selection and explicit cloud-context consent.
- Added bounded workspace context loading with untrusted-data prompting.
- Added JSON/fenced/raw response normalization, output limits, hard-coded
  credential rejection, and Python/JSON syntax validation.
- Added complete-file preview, unified diff, warnings, in-memory history,
  discard, and exact-confirmation apply operations.
- Added Workspace Runtime path enforcement, protected targets, SHA-256 stale-base
  detection, and atomic UTF-8 writes. Generated code is never executed.
- Added a responsive Code UI and API/security tests proving valid code generation
  and apply behavior.

## Modified implementation files

- `backend/app/services/code_generation_service.py`
- `backend/app/api/routes/code_generation.py`
- `backend/app/api/router.py`
- `backend/tests/test_code_generation_api.py`
- `frontend/src/App.tsx`
- `frontend/src/App.css`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `docs/development/CODE_GENERATION.md`

## Validation results

- P28 code generation/security tests: 5 passed.
- Backend Ruff: PASS.
- Frontend production build: PASS; 18 modules, JS 234.92 kB (72.12 kB gzip),
  CSS 22.14 kB (5.92 kB gzip).
- Frontend ESLint: PASS.
- Full Supervisor results are recorded in `.laes/SUPERVISOR_RESULTS.json` and
  the generated P28 review package.

## Security and privacy impact

- Models cannot directly read/write files or execute code.
- Every target/context path crosses Workspace Runtime; protected and credential
  targets are denied.
- Cloud code/context transfer requires explicit consent.
- Hard-coded credential-looking model output is rejected.
- Apply is explicit, stale-safe, and atomic.

## Cross-platform impact

Paths use `pathlib` and the shared Workspace Runtime. Diffing, hashing, syntax
validation, and atomic replace use Python standard-library APIs supported on
Windows, Linux, and macOS.

## Remaining risks and blockers

- Static syntax validation is currently language-aware for Python and JSON;
  other languages require operator review and downstream project tests.
- Model-generated code may still contain semantic, dependency, license, or
  security defects. Linlin intentionally does not execute it automatically.
- Proposals/history are process-local and disappear on restart.
- Existing FastAPI/Starlette deprecation warnings remain.

## Deviations

None. P28 writes only inside the configured workspace and does not add shell or
automatic execution.
