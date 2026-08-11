# Linlin Agent — Mandatory AI Instructions

This file is the primary repository instruction entry point for AI coding agents.

## Authoritative Reading Order

Before modifying ANY code, read and obey in this order:

1. `AI_COLLABORATION_CHARTER.md`
2. `.laes/CURRENT_PHASE.yaml`
3. every file listed under `required_reading` in `.laes/CURRENT_PHASE.yaml`
4. only the accepted ADR/RFC documents directly relevant to the current phase

`CURRENT_PHASE.yaml` is the phase gate and the source of truth for what may be implemented now.

### Future-phase isolation

- Do **NOT** preload, summarize, implement, or optimize future `P*.md` phase specifications.
- Future phase files may be opened only when the project owner has advanced `.laes/CURRENT_PHASE.yaml` to that phase, or when explicitly requested for planning/review without code modification.
- Knowledge that a future phase exists does not grant permission to implement it.

## Non-Negotiable Rules

- Implement ONLY the current P stage.
- Use Minimum Change Policy.
- Do not redesign accepted architecture.
- Do not replace frameworks unless explicitly approved through the LAES governance process.
- Do not perform unrelated refactoring or feature work.
- Do not bypass Provider Runtime, Tool Runtime, Workspace Runtime, or Credential Store boundaries.
- Preserve Windows/Linux/macOS compatibility.
- Never expose secrets.
- Never hide, disable, weaken, or delete failing tests merely to obtain PASS.
- Do not advance `.laes/CURRENT_PHASE.yaml` by yourself.

## Before Coding

State:

- current P stage;
- authoritative rules/documents loaded;
- expected files to change;
- validation commands to run;
- explicit out-of-scope items you will not touch.

Then implement only the assigned stage.

## End-of-Stage Rule

After completing the current P stage:

1. run all required validation;
2. report root cause and changes;
3. list modified files;
4. report exact test/build results;
5. report remaining risks/blockers;
6. show any deviations from the phase specification;
7. STOP.

**DO NOT begin the next P stage.**

The next P stage may begin only after ChatGPT architecture review returns **PASS** and the project owner explicitly approves continuation.
