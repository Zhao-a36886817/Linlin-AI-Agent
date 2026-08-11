# P29 Completion Report — One-click Launcher Reliability Hotfix

## Stage

P29 — One-click Launcher Reliability Hotfix

## Root cause

`Stop-Linlin` performed one recursive deletion while global PowerShell error
handling was set to Stop. Edge/Chrome could still be deleting or holding files in
its temporary profile, so a disappearing metadata/hash file or locked Extension
Scripts directory raised a fatal exception. Because startup begins with the same
cleanup function, one profile race prevented every later `.bat run`.

## Changes

- Every app launch now creates a unique dedicated browser profile.
- The profile path is stored beside the PID/start-time ownership record.
- Shutdown finds and stops only Edge/Chrome children whose command line contains
  that exact validated dedicated profile path.
- Temporary launcher cleanup retries eight times across Chromium deletion races.
- A final locked temporary artifact becomes a clear warning and is retried next
  time; it no longer aborts startup or shutdown.
- Preserved exact `%TEMP%/Linlin-Agent-launcher` deletion guard, owned PID/start
  validation, hidden service windows, browser-close shutdown, and user-data
  retention.

## Modified files

- `scripts/windows_launcher.ps1`
- `tests/test_windows_launcher.py`
- `docs/development/DESKTOP_RELEASE.md`

## Validation results

- Launcher tests: 7 passed, including real startup/cleanup smoke.
- Two additional consecutive `Linlin-Agent.bat smoke` runs: PASS/PASS.
- Full Supervisor validation is recorded in `.laes/SUPERVISOR_RESULTS.json` and
  the generated P29 review package.

## Security and privacy impact

Process cleanup remains deny-by-default: PID reuse is rejected and child browser
cleanup requires both an allowed executable name and the exact validated
launcher-owned profile path. Only the fixed temporary launcher root is removed;
workspace, credentials, configuration, logs outside the temporary session, and
the nested repository remain untouched.

## Cross-platform impact

This is an isolated Windows `.bat`/PowerShell adapter hotfix. Shared frontend,
backend, Tauri, and runtime code are unchanged.

## Remaining risks and blockers

- Endpoint security software can keep temporary Chromium files locked beyond the
  two-second retry window. This now produces a warning but does not block the next
  unique-profile launch; the later cleanup will retry.
- Existing FastAPI/Starlette deprecation warnings remain unrelated.

## Deviations

None.
