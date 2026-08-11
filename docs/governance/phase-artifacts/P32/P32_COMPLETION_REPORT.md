# P32 Completion Report — Conversation-Bound LLM Training

## Root cause

Linlin could call inference models but had no truthful training capability, job
contract, conversation binding, metrics normalization, consent boundary, or UI.
The current machine also has no local LoRA stack and only a 2 GB GPU, so pretending
that its Ollama models were trainable would be incorrect.

## Changes

- Added a bounded Training Runtime and typed API contracts.
- Added real OpenAI-compatible file upload, fine-tuning job creation, status,
  checkpoint metrics, sanitised errors, and cancellation.
- Added backend-only Credential Store connection resolution; credentials never enter
  job objects or frontend responses.
- Added truthful candidate model discovery and local LoRA capability reporting.
- Bound jobs to random Chat conversation identities and excluded errors/Code cards
  from training data.
- Added a Chat training panel with model selection, explicit cloud/billing consent,
  two-second polling, job state, cancellation, and actual train/validation loss SVG.

## Modified files

- `backend/app/training/__init__.py`
- `backend/app/training/models.py`
- `backend/app/training/service.py`
- `backend/app/api/routes/training.py`
- `backend/app/api/router.py`
- `backend/app/services/cloud_provider_service.py`
- `backend/tests/test_training_api.py`
- `frontend/src/App.tsx`
- `frontend/src/App.css`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `docs/development/LLM_TRAINING.md`

## Validation evidence

- Training protocol/security tests: 4 passed.
- Backend Ruff: PASS.
- Frontend TypeScript/Vite build: PASS.
- Frontend ESLint: PASS.
- UI inspection: PASS; Chat shows truthful engine status and model controls.
- Runtime log inspection: PASS; the same conversation id was polled repeatedly at
  the specified two-second interval.
- Full results are recorded in the generated P32 Supervisor review package.

## Security, rollback, and remaining risks

There is no arbitrary command execution, synthetic training, automatic upload, or
credential exposure. Rollback removes the training route/runtime/UI composition and
leaves Chat/Code/providers intact. Provider model eligibility, cost, retention,
availability, and returned metrics remain external. Local LoRA stays unavailable
until a separately approved platform training pack and trainable weights exist.
There are no migrations or specification deviations.
