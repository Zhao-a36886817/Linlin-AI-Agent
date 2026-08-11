# LAES Phase Transition Procedure

Only the project owner may advance the active phase, and only after ChatGPT review returns PASS.

## Promotion procedure

1. Coding AI completes the current phase and STOPS.
2. Review the diff and validation results with ChatGPT.
3. If ChatGPT returns FAIL, keep the current phase and repair only that phase.
4. If ChatGPT returns PASS, the project owner explicitly approves promotion.
5. Replace `.laes/CURRENT_PHASE.yaml` with the corresponding owner-approved template from `.laes/phases/`.
6. Commit the phase-gate change separately or clearly identify it in the promotion commit.
7. Start a new AI task/session. The coding AI reads the new `CURRENT_PHASE.yaml` and only that phase's required reading.

## Example

After P0 PASS + owner approval, copy `.laes/phases/P1.yaml` to `.laes/CURRENT_PHASE.yaml`.

The coding AI MUST NOT perform this promotion on its own.
