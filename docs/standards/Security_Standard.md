# Linlin Agent Security Standard

## Secrets

Secrets MUST NOT appear in:

- Git history;
- normal logs;
- frontend local storage;
- provider configuration returned to UI;
- model-visible debug output;
- test fixtures containing real credentials.

## Workspace

Agent-visible filesystem access MUST remain inside the configured workspace unless an explicitly approved capability says otherwise.

Validate traversal, symlink, archive extraction, and shell working-directory boundaries.

## Tools

High-risk tools such as terminal, process execution, Git mutation, network calls, and destructive filesystem actions SHOULD require explicit registration and policy checks.

## Cloud Data Handling

The application MUST NOT silently send user prompts, files, credentials, or workspace contents to a cloud provider.
