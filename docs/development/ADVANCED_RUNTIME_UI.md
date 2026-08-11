# Advanced Runtime Control Center

P26 exposes the existing safety runtimes as bounded product operations in the
single Linlin web console. These controls do not bypass the Provider, Tool,
Workspace, Credential, or runtime boundaries.

## Knowledge Base / RAG

- The operator selects a discovered local provider model explicitly.
- Ingestion accepts a path relative to the configured workspace root and requires
  consent. Workspace escape attempts are rejected by `WorkspaceRuntime`.
- Search returns text, a similarity score, source offsets, and the
  `untrusted_instructions` marker. Retrieved text is data, never trusted control
  input.
- Disabling RAG stops ingestion and search without inventing results.

## MCP

- The operator supplies a server ID and explicitly consents to discovery.
- P26 accepts Streamable HTTP endpoints only on `localhost`, `127.0.0.0/8`, or
  IPv6 loopback. Redirects and remote endpoints are not enabled.
- Discovered definitions are registered as `McpTool` instances and every call
  goes through `ToolManager` schema, timeout, and result handling.
- Disconnect closes the session and removes every registered MCP tool.

## Multi-agent

- Runs use the exact discovered local provider/model selected by the operator.
- The fixed coordinator/analyst/reviewer workflow is limited to depth 1,
  concurrency 2, four iterations, and 4096 cost units from the UI.
- Runs expose pending, running, completed, failed, and cancelled states. Active
  tasks can be cancelled; shutdown cancels remaining tasks.

## Scheduler

- Enabling and disabling require the API's exact confirmation phrase.
- The only approved action is `chat.prompt`; arbitrary commands and paths are not
  accepted.
- Each job requires consent and a selected local provider/model. Jobs, audit
  events, and results persist atomically in the configured local data directory.
- The page shows job state and model output by job ID and permits cancellation
  before execution.

## Operator notes

The Runtime overview is derived from actual service state. A setup-required,
disabled, empty, failed, or disconnected state is intentionally displayed as
such. P26 does not enable cloud transfer; cloud credentials and providers are a
separate gated phase.
