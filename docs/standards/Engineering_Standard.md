# Linlin Agent Engineering Standard

**LAES Version:** 1.1  
**Status:** Accepted

## 1. Purpose

This standard defines implementation rules for Linlin Agent. It is subordinate to `AI_COLLABORATION_CHARTER.md` and applies to all human and AI contributors.

## 2. Normative Language

The keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative requirements.

## 3. Architecture Preservation

- Existing accepted runtime boundaries MUST be preserved.
- Architecture redesign MUST require approved RFC/ADR work.
- Framework replacement MUST NOT happen as incidental implementation work.
- Public interfaces SHOULD remain backward compatible unless an approved change requires otherwise.

## 4. Minimum Change Standard

Every change MUST:

- solve the assigned root cause;
- remain within the current P-stage scope;
- minimize unrelated file changes;
- avoid speculative cleanup;
- be reviewable and reversible;
- preserve unrelated working behavior.

## 5. Backend Standard

Python code SHOULD:

- target the repository-approved Python version;
- use type hints for public interfaces;
- prefer `pathlib` for path handling;
- avoid hard-coded machine-specific paths;
- keep configuration externalized;
- use shared error/logging conventions;
- avoid duplicate provider/tool/workspace abstractions.

## 6. Frontend Standard

Frontend code MUST:

- keep UI concerns separate from backend runtime logic;
- avoid storing long-lived provider secrets in browser storage;
- use shared API types/contracts where available;
- preserve build compatibility for supported desktop/web targets.

## 7. Provider Standard

Providers MUST use the shared provider runtime contract.

Capabilities SHOULD be expressed explicitly, including where applicable:

- chat
- streaming
- tools
- thinking/reasoning
- embeddings
- vision
- audio
- image/video
- local/cloud
- credential requirement
- experimental/stable state

A provider MUST NOT execute tools directly.

## 8. Tool Standard

Tool calls MUST be normalized through the shared Tool Parser/Registry/Runtime path.

Tool definitions SHOULD be loaded according to context rather than blindly exposing every tool to every model call.

## 9. Workspace Standard

Agent-visible file operations MUST be constrained by Workspace Runtime.

Security-sensitive operations MUST defend against:

- path traversal;
- absolute-path escape;
- symbolic-link escape where applicable;
- ZIP/archive traversal;
- unsafe shell working-directory escape.

## 10. Credential Standard

Secrets MUST NOT be committed, logged, exposed to frontend code, or returned in model-visible output.

Long-lived credentials SHOULD use an approved OS credential/keyring mechanism or another explicitly accepted secure backend.

## 11. Cross-Platform Standard

Core behavior MUST support Windows, Linux, and macOS.

OS-specific implementations MUST be isolated behind platform adapters or explicit platform checks.

## 12. Test Standard

Contributors MUST run validation required by the active P-stage specification.

Tests MUST NOT be disabled, deleted, or weakened solely to produce a green build.

## 13. Documentation Standard

If a change modifies a documented contract, the corresponding document MUST be updated in the same approved scope.

## 14. Phase Gate

Completion of one P stage does not authorize work on the next P stage.

Every stage ends with STOP, ChatGPT review, and explicit owner approval.
