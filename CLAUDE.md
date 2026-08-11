# Linlin Agent — Claude Code Instructions

@AI_COLLABORATION_CHARTER.md
@AGENTS.md
@docs/standards/Engineering_Standard.md
@docs/architecture/System_Architecture.md
@.laes/CURRENT_PHASE.yaml

Claude MUST implement only the current P stage and MUST obey Minimum Change Policy.

Do not redesign accepted architecture, replace frameworks, bypass runtime boundaries, or perform unrelated refactoring.

After the current P stage is completed:

- run required validation;
- report root cause and modified files;
- report test/build results;
- report security/cross-platform impact and remaining risks;
- STOP.

Do not begin the next P stage until ChatGPT review returns PASS and the project owner explicitly approves continuation.
