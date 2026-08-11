# P12 Completion Report

## Scope and root cause

No MCP runtime or trust boundary existed. P12 adds only an injected transport
contract, deny-by-default server allowlist, untrusted schema validation, bounded
operations, and a Tool Runtime adapter. No network transport or server is
configured by default.

## Changes and evidence

- Added explicit server authorization and deterministic discovery.
- Rejected invalid, duplicate, and path-like capability names and malformed schemas.
- Required discovery before invocation and normalized remote results.
- Added timeout handling and transport close lifecycle.
- Routed approved capabilities through `McpTool` and `ToolManager`; schemas use
  a specialized profile and are not globally exposed.
- Targeted Ruff passed and five offline permission/malicious-server tests passed.
  Full evidence is in `P12_SUPERVISOR_REVIEW_PACKAGE.md`.

## Security, portability, rollback, and risks

Remote inputs are untrusted, no server/network/filesystem/credential access is
enabled by default, and all code is platform-neutral. Rollback removes the MCP
package, tests, and policy. Argument JSON Schema is preserved for model/runtime
validation but this phase does not implement a network transport. No P13 work
or specification deviation is present.
