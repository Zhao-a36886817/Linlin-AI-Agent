# Linlin Agent — Codex Working Agreement

Codex MUST follow `AGENTS.md`, `AI_COLLABORATION_CHARTER.md`, and `.laes/CURRENT_PHASE.yaml` as authoritative repository instructions.

## Startup Rule

At the start of every coding task:

1. read `.laes/CURRENT_PHASE.yaml`;
2. read only its `required_reading` files plus directly relevant accepted ADR/RFC documents;
3. state the current phase and allowed scope before editing;
4. do not read future phase documents for implementation purposes.

## Codex Scope

Codex is an implementation agent. It may:

- repair bugs in the active P stage;
- implement explicitly assigned work in the active P stage;
- add or repair tests required by that stage;
- perform the smallest necessary refactor required to fix the root cause.

Codex MUST NOT:

- redesign accepted architecture;
- expand the task into later P stages;
- introduce unrelated features;
- replace frameworks;
- weaken tests or security controls;
- modify the phase gate on its own;
- implement a future phase merely because its specification exists in the repository.

## Mandatory Stop Gate

When the active P stage is complete, Codex MUST produce the completion report required by `AGENTS.md` and **STOP**.

Wait for ChatGPT review and explicit project-owner approval before any next phase.
