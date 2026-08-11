# P11 Completion Report

## Scope and root cause

No RAG package or Loader/Chunk/Embedding/Retriever/Citation contracts existed.
P11 adds a disabled-by-default, Workspace-constrained retrieval pipeline without
API, frontend, MCP, plugin, or provider-owned RAG behavior.

## Changes

- Added UTF-8 text loading exclusively through Workspace Runtime with size and
  binary limits.
- Added deterministic overlapping chunks with stable source spans and IDs.
- Added a provider-neutral embedding protocol and Provider Runtime adapter;
  non-local embedding requires explicit cloud consent.
- Added deterministic cosine retrieval and citations that map to source spans.
- Marked prompt-like document instructions as untrusted data.
- Added Agent Runtime facade, disabled setting, tests, and P11 policy.

## Validation and impact

Targeted Ruff passed and the five loader/chunk/retrieval/citation/injection tests
passed. Full Supervisor evidence is in `P11_SUPERVISOR_REVIEW_PACKAGE.md`.
No document is uploaded automatically, no secrets are introduced, and all paths
remain platform-neutral.

## Migration, rollback, risks, and deviations

No migration is required. Rollback removes the new RAG package, facade, setting,
tests, and policy entry. The phase intentionally provides retrieval results but
does not generate answers or expose an API. Injection detection is advisory;
retrieved text must always remain untrusted. No P12 work or specification
deviation is present.
