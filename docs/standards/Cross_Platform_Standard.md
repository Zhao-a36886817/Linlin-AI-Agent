# Linlin Agent Cross-Platform Standard

Supported first-class platforms:

- Windows
- Linux
- macOS

## Mandatory Rules

- No machine-specific absolute paths in application logic.
- Prefer `pathlib` for Python path handling.
- Use environment/configuration for install and data locations.
- Isolate platform-specific implementations.
- Do not assume PowerShell, Bash, CMD, systemd, Registry, or Keychain exists on every platform.
- Tests SHOULD cover platform-neutral behavior independently from platform adapters.
