# P22 Completion Report — Public and Plugin API Stability

## Scope and root cause

The backend exposed working `/api` routes and validated plugin manifests, but their
stable versions, negotiation behavior, ownership and deprecation window were not
machine-verifiable public contracts. A client could not explicitly request a known
API contract, an incompatible client was not rejected predictably, and a new route
could be published without an assigned contract owner. P22 fixes those governance
gaps without changing an existing route URL, request payload or response payload.

## Changes and concise diff

- Added a pure ASGI public API contract middleware. Missing version headers remain
  backward-compatible with version `1`; explicit version `1` is accepted; unsupported
  versions receive HTTP `406` with the supported version list.
- Added `X-Linlin-API-Version`, `X-Linlin-API-Stability` and `Vary` to every `/api`
  response, including validation and negotiation errors, and exposed the version
  headers through CORS.
- Published a route-family ownership map and an OpenAPI inventory test that rejects
  new unowned public routes.
- Published plugin manifest schema and SDK version constants while retaining strict
  rejection of incompatible manifests and capabilities.
- Documented semantic compatibility, the two-minor-release/90-day deprecation window,
  versioned migration rules, plugin compatibility and rollback.
- Added machine policy and Gate validation commands for P22.

## Modified files

- `.laes/SUPERVISOR_POLICY.yaml`
- `backend/app/api/contracts.py`
- `backend/app/main.py`
- `backend/app/plugins/__init__.py`
- `backend/app/plugins/models.py`
- `backend/tests/test_api_contracts.py`
- `backend/tests/test_plugin_runtime.py`
- `docs/development/PUBLIC_API_STABILITY.md`
- `P22_COMPLETION_REPORT.md`

## Validation

- Contract, compatibility, migration, deprecation and plugin tests: `13 passed`.
- Backend byte compilation: PASS.
- Ruff across `app` and `tests`: PASS with no findings.
- Full backend regression: `182 passed, 1 skipped`; the skip is the existing
  environment-dependent training execution test.
- Warnings: 24 existing framework deprecation warnings (`TestClient`/`httpx` and
  `ORJSONResponse`); no test or check failure.
- The exact repeated Supervisor commands and captured output are recorded in
  `P22_SUPERVISOR_REVIEW_PACKAGE.md`.

## Security and privacy

Negotiation happens before endpoint execution and accepts only the published
version. Error bodies contain no credential, filesystem or provider details. Plugin
permission approval remains independent of contract compatibility. Provider, Tool,
Workspace and Credential Runtime boundaries were not modified or bypassed. No data
collection, telemetry or secret handling was added.

## Cross-platform and migrations

The middleware and tests use FastAPI/Starlette interfaces and platform-neutral
paths. Windows, Linux and macOS behavior is unchanged. Existing clients need no
migration because an omitted header selects version `1`; clients may add
`X-Linlin-API-Version: 1` incrementally. Any future breaking change requires a new
major contract and documented migration.

## Rollback

Remove the contract middleware registration/header exposure, the contract and test
modules, the exported plugin version constants, and the P22 documentation/policy
entries. Existing route implementations and payloads require no rollback.

## Remaining risks and deviations

The framework deprecation warnings should be addressed in a separately approved
dependency-maintenance phase; they do not alter current contract behavior. Native
clients must opt in to explicit negotiation by sending the header, while legacy
clients intentionally continue as version `1`. There are no known P22 specification
deviations and no frontend, desktop, model, nested-repository or future-phase files
were changed by this phase.
