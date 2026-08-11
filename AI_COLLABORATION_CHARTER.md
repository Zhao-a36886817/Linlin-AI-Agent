# Linlin Agent AI Collaboration Charter

**LAES Version:** 1.1  
**Status:** Accepted  
**Authority:** Project Owner  

## 1. Purpose

This Charter defines the highest-level rules for every AI system that contributes to Linlin Agent, including Codex, ChatGPT, Claude, Gemini, Qwen, Copilot, Cursor, Cline, and future AI systems.

Its goals are to preserve architecture, security, cross-platform compatibility, testability, maintainability, and predictable collaboration.

## 2. Authority Order

When instructions conflict, follow this order:

1. Project Owner instructions
2. This `AI_COLLABORATION_CHARTER.md`
3. Accepted Architecture Decision Records (ADR)
4. Approved Requests for Change (RFC)
5. LAES engineering standards
6. Current P-stage specification
7. AI-generated implementation choices

Implementation MUST NOT override higher-level governance.

## 3. Core Engineering Principles

- **Architecture First** — Do not sacrifice architecture for speed.
- **Stability First** — Stabilize existing behavior before adding features.
- **Security First** — Never bypass security boundaries for convenience.
- **Local First** — Prefer local execution when practical; cloud usage must be explicit.
- **Privacy First** — No hidden upload, telemetry, or secret exposure.
- **Cross-Platform First** — Windows, Linux, and macOS are first-class targets.
- **Minimum Change** — Make the smallest correct change that solves the assigned problem.
- **Evidence-Based Decisions** — Architecture or performance changes require evidence, not preference.
- **Documentation Required** — Relevant documentation must stay consistent with implementation.
- **Testing Required** — Required validation may not be skipped, hidden, or disabled.

## 4. AI Roles

### Project Owner

The human project owner has final authority over phase transitions, architecture approval, merges, and releases.

### ChatGPT

Primary responsibilities:

- architecture planning and review
- change-scope review
- quality review
- security review
- cross-platform review
- ADR/RFC review
- P-stage PASS/FAIL review

### Codex

Primary responsibilities:

- implementation of the currently assigned P stage
- targeted bug fixes
- targeted refactoring approved by the current stage
- tests required by the current stage

Codex MUST NOT independently redesign accepted architecture or continue to another P stage.

### Other AI Systems

Other AI systems may analyze or implement only within the same LAES rules and current P-stage scope.

## 5. Mandatory Reading Before Code Changes

Before modifying code, an AI contributor MUST read:

1. `AI_COLLABORATION_CHARTER.md`
2. `AGENTS.md` or the model-specific entry file
3. `docs/standards/Engineering_Standard.md`
4. `docs/architecture/System_Architecture.md`
5. `.laes/CURRENT_PHASE.yaml`
6. the current `docs/development/P*.md`
7. relevant accepted ADR/RFC documents when present

The AI MUST NOT modify code before understanding the current scope.

## 6. One P-Stage Policy

Exactly one P stage may be implemented at a time.

Required workflow:

`Current P -> Implement -> Validate -> Report -> STOP -> ChatGPT Review -> Owner Approval -> Next P`

After finishing the current P stage, every AI MUST STOP.

The next P stage MUST NOT begin until:

1. ChatGPT has reviewed the completed stage and returned PASS; and
2. the project owner explicitly approves continuation.

An AI MUST NOT advance `.laes/CURRENT_PHASE.yaml` by itself unless explicitly instructed by the project owner after review.

## 7. Minimum Change Policy

For every task:

- modify only files necessary for the current stage;
- preserve existing public behavior unless change is explicitly required;
- do not perform unrelated cleanup;
- do not rename modules without necessity;
- do not replace frameworks;
- do not rewrite working subsystems;
- prefer root-cause fixes over broad redesign;
- keep diffs reviewable and reversible.

## 8. Architecture Protection

Accepted architecture MUST NOT be redesigned by an implementation AI.

Architecture changes require:

`RFC Proposal -> Architecture Review -> Owner Approval -> ADR/RFC Update -> Implementation`

No AI may mark its own architecture proposal as approved.

## 9. Layer Boundaries

The intended high-level flow is:

`Frontend -> API Layer -> Agent Runtime -> Provider Runtime -> Tool Runtime -> Workspace Runtime`

Important constraints:

- Providers MUST NOT directly execute tools.
- Tool execution MUST pass through Tool Runtime / Tool Registry.
- File-system operations exposed to agents MUST pass through Workspace Runtime.
- UI MUST NOT contain backend runtime logic.
- Secrets MUST NOT be returned to frontend code or model-visible logs.

## 10. Security Rules

AI contributors MUST NOT:

- expose API keys, tokens, passwords, or credentials;
- commit secrets;
- log secrets;
- bypass Credential Store;
- bypass Workspace sandboxing;
- disable security checks just to make tests pass;
- add unrestricted shell execution without explicit approved scope;
- trust archive paths without traversal validation;
- silently send user files or prompts to cloud services.

## 11. Cross-Platform Rules

Core code MUST support Windows, Linux, and macOS.

Do not hard-code paths such as:

- `C:\...`
- `D:\...`
- `/home/<user>/...`

Use platform-neutral APIs such as `pathlib`, configuration, environment variables, and isolated platform adapters.

OS-specific behavior must be isolated behind explicit platform boundaries.

## 12. Provider Policy

Providers MUST follow the official provider contract and shared runtime architecture.

Provider classifications use:

- `LOCAL_FREE`
- `FREE_TIER`
- `PAID`
- `UNKNOWN`

`FREE_TIER` MUST NOT be presented as permanently free.

Local Ollama / local OpenAI-compatible runtimes are the preferred baseline for zero API-usage-cost operation.

## 13. Tool and Workspace Policy

Tool execution flow:

`LLM -> Tool Parser -> Tool Registry -> Tool Runtime -> Workspace/Service -> Tool Result -> LLM`

Workspace Runtime is the authorized boundary for agent-visible file operations.

Path traversal, workspace escape, unsafe archive extraction, and unauthorized absolute-path access are prohibited.

## 14. Required Completion Report

At the end of every P stage, the implementing AI MUST report:

- current P stage;
- root cause(s);
- modified files;
- concise diff summary;
- validation commands executed;
- test/build results;
- security impact;
- cross-platform impact;
- remaining risks or blockers.

Then STOP.

## 15. Test Integrity

Required checks MUST NOT be bypassed by:

- deleting tests;
- disabling tests;
- weakening assertions solely to obtain PASS;
- suppressing errors without root-cause analysis;
- adding broad ignore rules without explicit justification.

If a required check cannot run, report it as a blocker.

## 16. Violation Handling

If an AI discovers that it has violated this Charter, it MUST:

1. stop further implementation;
2. clearly report the deviation;
3. identify affected files;
4. propose the smallest corrective action;
5. wait for review if the correction changes scope.

## 17. Amendment Process

This Charter may only be changed through explicit project-owner approval.

AI systems MUST NOT autonomously weaken, remove, or bypass this Charter.
