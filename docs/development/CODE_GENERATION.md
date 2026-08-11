# Workspace-safe code generation

P28 provides a model-driven code workflow without giving a model direct file or
process access.

## Product flow

1. The operator selects any dynamically discovered local or cloud model.
2. The operator supplies a workspace-relative target path, an instruction, and
   optional workspace-relative context files.
3. Cloud selections require a separate data-transfer consent checkbox before the
   instruction or code context is sent.
4. The Provider Runtime returns a complete-file proposal. The service normalizes
   strict JSON, fenced-code, or common JSON-like triple-quoted responses, enforces
   size/text constraints, rejects ambiguous structured wrappers and likely hard-coded
   credentials, and validates Python AST or JSON syntax when relevant. Model output
   is parsed as data only and is never evaluated or executed.
5. Linlin stores the proposal only in process memory and returns its complete
   content, summary, warnings, and unified diff. No file is changed yet.
6. The operator reviews the diff and chooses Discard or Confirm and Apply.
7. Apply requires the exact backend confirmation, re-resolves the path through
   Workspace Runtime, and compares the current file hash with the previewed
   version. A stale proposal is rejected.
8. Accepted content is written atomically inside the workspace. Linlin never
   executes generated code.

The same workflow is available directly in Chat. Switching the conversation mode
to Code keeps the selected provider/model, adds workspace target and optional
context controls, and renders the proposal as an assistant card in that same
conversation. The card requires the literal `APPLY CODE` confirmation before the
existing apply API can be invoked. The standalone Code page remains available.

## Workspace policy

- Absolute paths, parent traversal, symlink escape, and non-file targets are
  rejected by `WorkspaceRuntime`.
- `.git`, `.laes`, `.ssh`, credential/secrets directories, and `.env` targets are
  not valid generation destinations.
- Credential-looking context files cannot be sent to models.
- Context is limited to 20 paths and 200 KB; generated output is limited to
  500 KB.
- Common source, script, markup, configuration, and data-language text extensions
  are allowed. Script files may be written after approval but are never launched.

## Concurrency and review safety

Each proposal records whether the target existed and a SHA-256 hash of the exact
previewed content. If another program edits, creates, or removes the target before
Apply, the operation fails and the operator must generate a new preview. This
prevents a reviewed diff from being applied to an unexpected base version.

## Provider behavior

The service calls the selected provider/model through `ProviderManager`; it does
not embed or choose a model identifier. Providers receive code context as data
inside an explicit untrusted-context delimiter. They do not receive Workspace or
Tool Runtime access.
