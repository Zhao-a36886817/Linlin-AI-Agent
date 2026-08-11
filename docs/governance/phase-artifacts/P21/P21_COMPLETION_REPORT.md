# P21 Completion Report — CI/CD, Signing, and Supply-Chain Security

## Scope and root cause

The repository had local release verification but no protected cross-platform CI,
SBOM/provenance evidence, dependency/secret scanning, or manual production
promotion workflow. P21 adds those release controls without changing application
APIs or runtime architecture. Gate reruns also exposed a Windows-only reliability
problem: fixed pytest temporary directories could remain locked, and npm audit
assumed the user-profile cache was writable.

## Changes

- Added Windows, Linux and macOS validation for backend, frontend and Tauri with
  read-only permissions and checkout credentials disabled.
- Pinned every external GitHub Action to a full official commit SHA.
- Added deterministic CycloneDX 1.5 SBOM generation across pinned Python, npm and
  Cargo dependencies, exact backend audit requirements, SLSA/in-toto-style local
  provenance, high-confidence secret scanning and compromise-drill tests.
- Added Python and npm dependency audits; both report no known vulnerability.
- Made local Gate reruns use P21-dedicated ignored pytest/npm cache directories;
  CI behavior remains unchanged.
- Added manual-only native release candidates protected by a `production`
  Environment, explicit `PROMOTE` input, secret-backed Tauri signing, short artifact
  retention and GitHub/Sigstore attestations. Nothing publishes automatically.
- Ignored root-local `*API.txt` secret files to prevent accidental commits while
  preserving the existing untracked file untouched.

## Security and privacy

Workflow secrets are referenced only through the protected environment and never
printed or passed as command-line arguments. Artifact promotion needs manual input
and environment approval. Secret scan reports paths/type only, never matched values.
The local API-key file detected during review is untracked, absent from Git history,
preserved, and now ignored; its key should still be rotated as a precaution.

## Cross-platform and migrations

The validation matrix represents all three first-class operating systems and
installs Linux Tauri prerequisites only on Linux. SBOM/provenance tooling uses
platform-neutral Python paths. There is no data or database migration.

## Validation

- Supply-chain Ruff: PASS.
- Workflow/SBOM/provenance/secret/compromise tests: 10 passed.
- Repository secret scan: PASS.
- CycloneDX SBOM: generated with 604 components.
- `pip-audit` on exact backend requirements: no known vulnerabilities.
- `npm audit` across production and development dependencies: 0 vulnerabilities.
- Full Supervisor results are recorded in `P21_SUPERVISOR_REVIEW_PACKAGE.md`.

## Rollback

Remove the two workflows, supply-chain script/tests/documentation, ignore entries,
and P21 policy/report entries. Disable the GitHub production Environment and rotate
signing secrets if any candidate workflow was executed.

## Remaining risks and deviations

Repository administrators must configure required reviewers and signing secrets on
the GitHub `production` Environment before a release candidate can succeed. GitHub
hosted matrix execution itself occurs after push; local tests validate its structure
and commands but cannot impersonate three native hosted runners. There are no known
P21 specification deviations.
