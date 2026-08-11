# P20 Completion Report — Desktop Packaging, Installer, and Auto-Update

## Scope and root cause

The Tauri shell could build but had no reproducible package inventory, signed
offline update verification, rollback contract, or complete lifecycle guide. It
also disabled CSP. P20 adds fail-closed release integrity without embedding signing
credentials or inventing a production update endpoint.

## Changes

- Added deterministic, sorted package manifests with relative paths, sizes and
  SHA-256 digests; empty packages and symbolic links reject.
- Added Ed25519 detached-signature verification followed by an exact rebuilt
  package comparison, rejecting changed, missing or added content.
- Added ephemeral-key tests for valid signatures, tampered signatures/content,
  reproducibility, rollback metadata, and symlink safety; no private key is stored.
- Declared the already locked cryptography dependency and replaced the null desktop
  CSP with a restricted local/backend policy.
- Documented native install, signed update, rollback, uninstall/data retention and
  per-platform smoke responsibilities.
- Added one Windows launcher entry point with install, run, install-and-run, stop,
  verify, smoke and help commands. A PowerShell lifecycle helper replaces the
  unreliable detached `start /b` chain. It repairs incomplete locked frontend
  dependencies, builds the UI, starts the owned backend/frontend processes hidden,
  opens one isolated browser app window, then stops and removes only its validated
  temporary session directory when that window closes.
- Records each backend, frontend and dedicated browser PID together with its start
  time. Stop refuses PID reuse and therefore does not close unrelated user
  processes or existing browser windows.

## Security and privacy

Signing private keys stay outside source and packages. Verification requires a
trusted raw Ed25519 public key from release configuration and fails before install.
Automatic update remains disabled until the owner provisions that public key and a
production endpoint; unsigned automatic updates are impossible in this change.

## Cross-platform and migrations

Manifest paths are POSIX-normalized relative paths generated via `pathlib`.
Windows release smoke produced `desktop.exe`; native Linux and macOS installer
smokes remain mandatory on their own release runners. No user-data migration is
introduced, and uninstall/rollback preserve user data.

## Validation

- Release Ruff: PASS.
- Release integrity tests: 4 passed, 1 symlink test skipped due Windows account
  permissions.
- Windows launcher contract and executable smoke tests: 6 passed. A real app-window
  lifecycle test also opened the browser, closed its recorded PID, observed launcher
  exit code 0, removed session state, and confirmed ports 8000/5173 were offline.
- `tauri build --no-bundle`: PASS; optimized Windows `desktop.exe` produced.
- Complete Supervisor results are in `P20_SUPERVISOR_REVIEW_PACKAGE.md`.

## Rollback

Revert the release integrity module/tests, dependency declaration, CSP change,
release guide and P20 policy/report entries. Preserve the previous signed installer
and user data. Generated build output is ignored and need not be deleted.

## Remaining risks and deviations

Production updater activation needs external owner-controlled signing key/public
key and endpoint provisioning; this is intentionally not guessed. Native bundled
installer smoke for Linux/macOS cannot run on Windows and must be completed by the
documented release matrix. Offline signed update verification and Windows release
binary smoke meet P20's locally executable scope; there are no security deviations.
