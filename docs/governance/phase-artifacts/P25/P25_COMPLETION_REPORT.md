# P25 Completion Report — Commercial Runtime Control Center

## Stage

P25 — Commercial Runtime Control Center

## Root cause

The advanced runtimes implemented in P10-P15 had no API facade or client controls. The existing React entry point was a minimal single textarea with inline styles, unreadable legacy strings, no navigation, no loading/error/empty states, and no way to see whether advanced capabilities were disabled or missing configuration.

The reopened Chat UI also presented a fixed empty-response fallback inside an
assistant bubble, which could be mistaken for model output. It discarded Ollama's
`thinking` field and labelled every response with the currently selected model
rather than the provider/model that actually produced the event. In addition, the
UI requested up to 2048 output tokens; the local runtime log measured about 2.5
tokens/second and showed one request occupying Ollama for 10 minutes 22 seconds,
which queued later requests and made the runtime appear non-responsive.

## Changes

- Added an owner-scoped, version-bound runtime-control API facade.
- Added honest status for Memory, RAG, MCP, multi-agent orchestration, and Scheduler.
- Added fully functional process-local Memory enable/create/list/delete controls with confirmation, consent, expiry, isolation, and secret-pattern rejection.
- Rebuilt the React UI as a single responsive control center with Overview, Chat, Memory, RAG, MCP, Multi-agent, and Scheduler pages.
- Added production UI states, keyboard focus, reduced-motion behavior, desktop/mobile navigation, confirmation modal, and responsive layouts.
- Added API security/contract tests and operator documentation.
- Added an owner-only Supervisor `reprioritize` command so the P21 FAIL gate was preserved rather than forged or overwritten.
- Reopened P25 after owner rejection and replaced the hard-coded Chat shell with installed-model discovery, model selection, SSE streaming, cancellation, conversation reset, thinking/tool controls, keyboard behavior, truthful runtime health, and offline/no-model guidance.
- Removed the canned empty-response assistant text. Only provider `content` is now
  rendered as an AI answer; errors are visibly labelled as non-model system state,
  actual provider/model provenance is retained per message, and real `thinking`
  output is available separately without masquerading as the final answer.
- Restored the normal 512-token output ceiling and removed an empty pending bubble
  when the user cancels, preventing very long local generations and stale UI state.
- Prevented silent cloud-model selection: startup now prefers an installed local,
  non-reasoning chat model based on capability metadata. Cloud-named Ollama models
  remain manually selectable but are explicitly labelled and show a data-routing
  warning before use.
- Replaced that automatic preference with fully explicit local discovery after the
  owner's follow-up: the models API now classifies Ollama entries from their actual
  remote metadata and supports `local_only=true`; the UI scans that endpoint,
  performs a second local-only check, displays the current count/capabilities, and
  requires the user to choose a model. Requests use the selected result's provider
  and model values rather than a fixed frontend identifier.

## Modified implementation files

- `backend/app/api/router.py`
- `backend/app/api/routes/models.py`
- `backend/app/api/routes/runtime_control.py`
- `backend/app/schemas/models.py`
- `backend/tests/test_models.py`
- `backend/tests/test_runtime_control_api.py`
- `frontend/src/App.tsx`
- `frontend/src/App.css`
- `frontend/src/index.css`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `docs/development/COMMERCIAL_CONTROL_CENTER.md`

Roadmap/governance files were created before P25 `begin` under explicit owner authorization and are not product implementation changes.

## Validation results

- Backend compile: PASS.
- Backend Ruff: PASS.
- P25 API tests: 5 passed.
- Full backend regression: 147 passed, 1 skipped, 8 deprecation warnings.
- Frontend production build: PASS; 18 modules, JS 210.72 kB (66.86 kB gzip), CSS 18.04 kB (5.08 kB gzip).
- Frontend ESLint: PASS.
- Tauri `cargo check --locked`: PASS.
- Windows launcher tests: 5 passed.
- Browser desktop QA: PASS; no horizontal overflow and no console warnings/errors.
- Browser 390x844 QA: PASS; all seven navigation destinations visible and no horizontal overflow.
- Browser Memory workflow: PASS; enable confirmation, create, list, and status update verified against the real API.
- Browser Chat workflow: PASS; discovered 3 installed Ollama models, selected `llama3.2:3b`, submitted with Enter, received the real streamed response `測試成功`, restored send state, and produced no console errors.
- Reopened browser Chat truthfulness QA: PASS; discovered 5 current Ollama models, automatically selected the local non-thinking `llama3.2:3b` instead of the first cloud entry, submitted `Reply with exactly: LIVE-27`, received the real streamed `LIVE-27`, and displayed `ollama · llama3.2:3b` provenance. The removed fixed fallback had zero DOM matches, the manually selected cloud model displayed its warning, and browser error/warning logs were empty.
- Dynamic local-model API tests: 2 passed; remote Ollama metadata is classified as non-local and `local_only=true` returns only installed local entries.
- Dynamic local-model browser QA: PASS; the restarted app discovered exactly 4
  local models and excluded the Ollama cloud entry, selected no default, displayed
  model capabilities, required an explicit selection, then invoked the chosen
  `llama3.2:3b` and streamed `DYNAMIC-LOCAL` with correct provenance. A separate
  request selected `qwen3:4b` and the API reported that exact model. Browser
  error/warning logs were empty.
- Direct backend/model differentiation: PASS; the real `llama3.2:3b` returned `15` for `7+8` and `Tokyo.` for Japan's capital using the same API path, proving responses are model-generated rather than canned.
- Browser mobile Chat QA: PASS; six chat controls are reachable at 390x844 with no horizontal overflow and navigation resets scroll position.
- Test services were stopped; the temporary in-memory QA record was cleared with the backend process.

## Security and privacy impact

- No secret is returned to the frontend.
- No external fonts, telemetry, or hidden cloud calls were added.
- Memory remains explicit-consent and rejects credential-like content without echoing it in errors.
- RAG, MCP, multi-agent, and Scheduler are not falsely enabled without their approved dependencies.
- Existing Provider, Tool, Workspace, Credential, and advanced Runtime implementations were not modified.

## Cross-platform impact

Application logic uses browser APIs and existing platform-neutral FastAPI contracts. No new machine-specific path was added to application code. Windows launcher and Tauri checks pass; the UI remains shared by web and Tauri.

## Remaining risks and blockers

- RAG requires a reviewed embedding-provider configuration.
- MCP requires a concrete approved transport and persisted server allowlist.
- Multi-agent requires production roles and executor integration.
- Scheduler requires a reviewed action registry.
- Memory state remains process-local by the accepted P10 runtime design and is cleared on restart.
- The existing FastAPI/Starlette deprecation warnings remain; they were not introduced by P25.
- P21 remains incomplete and must resume after P25 before P22-P24 and release-candidate review.

## Deviations

The requested UI pages are complete, but four setup-required runtimes are intentionally status/control shells rather than fake operational adapters. This preserves the existing architecture and is explicitly surfaced in the UI and documentation.
