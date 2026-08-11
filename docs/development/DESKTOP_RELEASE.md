# Desktop Install, Update, Rollback, and Uninstall

## Reproducible package check

Build each supported Tauri target in a clean environment from the locked Node and
Cargo dependency files. Run `build_manifest()` over the completed package directory;
its canonical JSON is stable, sorted, and records every file's relative path, byte
length, and SHA-256 digest. Symbolic links and empty packages are rejected.

The release service signs the canonical manifest with an Ed25519 private key held
outside the repository and build artifacts. Distribute the manifest, detached
signature, and package together. `verify_signed_package()` must receive the trusted
public key through release configuration and pass before installation. Invalid
signatures, changed bytes, missing files, and added files fail closed.

## Install and update

Installers are produced by Tauri for the current platform. Back up user-controlled
data before changing its schema; P20 introduces no user-data migration. Automatic
download/install remains disabled until the project owner provisions a production
updater endpoint and trusted public key. An unsigned or unverified package must
never be installed.

## Rollback

The signed manifest identifies the approved `rollback_version`. Preserve that
previous signed installer until the new release passes smoke tests. Rollback uses
the same signature/content verification and must not replace or delete user data.

## Uninstall

Use the platform installer uninstall path. Remove application binaries and shortcuts
only. Workspace, configuration, credentials, logs, and user artifacts are retained
unless the user separately and explicitly requests their deletion.

Windows, Linux, and macOS packages must each run frontend build/lint and Tauri Cargo
checks on their native release runner before publishing. A package from one OS is
not evidence for another OS.

## Single-window Windows launcher

`Linlin-Agent.bat` is the Windows entry point for installation, execution, stop,
install-and-run, and verification. With no argument it presents one menu; the same
actions are available as command arguments for automation. Run builds the frontend,
starts only its own backend and preview processes in hidden windows, waits for both
health endpoints, and opens a dedicated Edge or Chrome app window with an isolated
temporary browser profile.

Closing that app window triggers shutdown using the recorded backend, frontend,
and dedicated browser PIDs. Each PID is paired with its process start time, so a
reused PID or an unrelated existing browser is never stopped. Cleanup verifies
that the resolved target is exactly
`%TEMP%\Linlin-Agent-launcher` before removing logs, PID files and the temporary
browser profile. Workspace, configuration, credentials and user artifacts are not
deleted. Each launch uses a unique dedicated profile. The launcher also closes
browser child processes only when their command line references that exact
recorded profile. Temporary-profile deletion is retried to tolerate Chromium
cleanup races; a still-locked temporary artifact is reported as a warning and
retried on the next launch instead of blocking application startup. The launcher
intentionally exposes the existing API/UI integration; it
does not imply that contract-only advanced runtimes have public UI controls.

If `frontend/node_modules` is absent or incomplete, Run repairs it from the
committed `package-lock.json` before building. The executable smoke command runs a
real build, starts both hidden services, probes their health endpoints, then proves
that shutdown and temporary-state cleanup succeed:

```bat
Linlin-Agent.bat smoke
```
