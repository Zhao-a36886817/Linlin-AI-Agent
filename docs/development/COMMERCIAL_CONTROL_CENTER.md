# Commercial Runtime Control Center

## Start

On Windows, run `Linlin-Agent.bat`. The launcher installs missing dependencies when needed, starts the backend and frontend, and opens the operation page in one browser window. Closing the launched page triggers the launcher's normal shutdown and temporary-file cleanup flow.

## Available now

- **Overview:** honest status for Memory, RAG, MCP, multi-agent orchestration, and Scheduler.
- **Chat:** on-demand discovery of the models currently installed in Ollama, explicit user selection before every new conversation, SSE streaming, stop generation, new conversation, optional thinking and tool modes, Enter/Shift+Enter keyboard behavior, and actionable offline/no-model recovery. The UI requests `local_only` discovery, excludes entries carrying Ollama remote-model metadata, and builds each request from the selected result's provider and model name; no model identifier is embedded as the default. Only provider-returned content is presented as an AI answer, errors are visibly identified as system state, and each answer retains its actual provider/model provenance.
- **Memory:** explicit enable/disable confirmation, local owner/session scoping, create/list/delete, automatic expiry, and credential-like content rejection.
- **Responsive UI:** desktop, compact sidebar, and seven-item mobile navigation without horizontal overflow.

## Setup-required runtimes

The following pages intentionally stay in `setup_required` until their backend dependencies have been formally configured:

- RAG requires a reviewed embedding provider and model.
- MCP requires an approved transport and server allowlist.
- Multi-agent requires approved roles and an Agent Runtime executor.
- Scheduler requires an allowlist of approved application actions.

The UI does not create fake adapters, silently enable remote access, accept arbitrary commands, or move runtime logic into the browser.

## Security behavior

- Runtime status responses contain no credentials.
- Memory operations require an owner scope header and explicit consent.
- Enabling or disabling Memory requires an exact confirmation phrase at the API boundary and a product confirmation dialog in the UI.
- High-risk runtimes remain disabled when their approved dependencies are absent.
- Browser code calls only the API layer; Provider, Tool, Workspace, and Credential boundaries remain backend-owned.

## Current production boundary

The control center is suitable for local commercial evaluation of Chat and Memory. RAG, MCP, multi-agent, and Scheduler are visible and honestly gated, but are not production-operable until their formal adapters and policies are supplied in separately reviewed phases.
