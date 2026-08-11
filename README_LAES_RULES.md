# Linlin Agent LAES Rules Pack v1.1

Copy this pack into the root of the Linlin Agent repository while preserving directory structure.

## Authority Order

1. `AI_COLLABORATION_CHARTER.md`
2. `AGENTS.md`
3. `.laes/CURRENT_PHASE.yaml`
4. files listed in `CURRENT_PHASE.yaml -> required_reading`
5. accepted relevant ADR/RFC documents

## Current Gate

The included `.laes/CURRENT_PHASE.yaml` is set to **P0 — Build and Test Stabilization**.

The repository also includes formal phase specifications for **P0 through P9**, but implementation agents are explicitly instructed **not to preload or implement future phases**.

## How phase switching works

After the active phase is completed:

`AI implementation → tests → STOP → ChatGPT review → owner approval → phase gate update`

Prebuilt owner-controlled phase templates are in:

`.laes/phases/P0.yaml` through `.laes/phases/P9.yaml`

See `.laes/PHASE_TRANSITION.md` for the promotion procedure.

## Formal phase specifications

See `docs/development/PHASE_INDEX.md` and `docs/development/P0.md` … `P9.md`.

## Important

Markdown instructions improve persistence but cannot technically guarantee model compliance by themselves. A future LAES Guard + CI policy should mechanically reject out-of-scope diffs and failed validation.
