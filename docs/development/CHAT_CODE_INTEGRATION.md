# Conversational Code Integration

Chat has two explicit modes: normal conversation and Code proposal. Both use the
same dynamically selected Provider Runtime identity. Code mode calls the existing
workspace-safe proposal API; it does not parse, write, or execute code in the UI.

Each successful request appends an assistant proposal card to the current visual
conversation. The card contains the target path, provider/model, summary, warnings,
unified diff, complete content, and pending/applied/discarded state. A pending card
can be discarded without writing. Apply requires the operator to type `APPLY CODE`,
confirm the target, and pass the existing backend confirmation and stale-base gates.

Cloud Code requests retain the separate consent checkbox. Changing mode or model
clears that consent so a previous choice cannot silently authorize another model.
Protected targets, workspace escape, credential-like output, syntax validation,
size limits, and atomic write behavior remain owned by CodeGenerationService and
Workspace Runtime.

