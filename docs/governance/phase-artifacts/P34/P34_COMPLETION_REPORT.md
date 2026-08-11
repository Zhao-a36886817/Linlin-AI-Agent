# P34 Completion Report — Visible Training Workspace and Local LoRA Runtime

## Root cause

The existing cloud fine-tuning control plane was functionally present but its
toolbar entry could be pushed out of view. It also reported local LoRA as
unavailable without a registered-model boundary, optional dependency installer,
background runner, cancellation, adapter output, or real local trainer metrics.

## Changes

- Moved **模型訓練** into the Chat page-title actions and made both title actions
  responsive; the crowded model toolbar now wraps instead of overflowing.
- Added discovery for registered Hugging Face model directories under `models/`.
- Added a real Transformers/PEFT LoRA runner with bounded steps, background jobs,
  cooperative cancellation, real loss callbacks, and adapter-only output.
- Kept local conversations in memory and limited output to
  `outputs/training/<job-id>/adapter` without overwriting source weights.
- Rejected missing consent, unregistered paths, traversal, symlink escape,
  incorrect local providers, and cross-conversation job access.
- Preserved the existing OpenAI-compatible cloud fine-tuning protocol and credentials.
- Added an optional, pinned local-training dependency set and a one-click launcher
  command/menu entry named `install-training`.

## Modified files

- `backend/app/training/local_lora.py`
- `backend/app/training/models.py`
- `backend/app/training/service.py`
- `backend/app/core/config.py`
- `backend/pyproject.toml`
- `backend/linlin_agent_backend.egg-info/PKG-INFO`
- `backend/linlin_agent_backend.egg-info/SOURCES.txt`
- `backend/linlin_agent_backend.egg-info/requires.txt`
- `backend/tests/test_training_api.py`
- `frontend/src/App.tsx`
- `frontend/src/App.css`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `scripts/windows_launcher.ps1`
- `tests/test_windows_launcher.py`
- `docs/development/LOCAL_LLM_TRAINING.md`

## Validation evidence

- The first Supervisor pass correctly rejected undeclared editable-install
  `egg-info` refreshes; those direct installation artifacts were explicitly added
  to the phase scope before this clean revalidation.
- Local/cloud training API and security tests: 7 passed.
- Launcher tests, including real hidden startup/cleanup smoke: 8 passed.
- Frontend TypeScript/Vite build and ESLint: PASS.
- Actual optional training dependencies installed successfully in the Linlin environment.
- Actual Transformers/PEFT one-step LoRA runner: PASS with a saved adapter and real loss.
- Actual `/api/training/jobs` end-to-end local job: `succeeded`, one real loss metric,
  and an adapter output path; the isolated test model/output were removed afterward.
- Browser inspection: Runtime online, **模型訓練** visible beside **新對話**, panel
  opens in the same conversation, two-second status contract and local capability shown.
- Complete Supervisor validation evidence is recorded in the generated review package.

## Security, rollback, and remaining risks

No client filesystem path is trusted, no cloud upload occurs for local jobs, source
weights are read-only, and secrets never enter jobs or UI responses. Rollback removes
the optional runner/discovery and visible control changes while leaving existing cloud
fine-tuning intact. Local jobs are in-memory and do not resume after process shutdown.
This machine has limited GPU memory, so large models can still fail cleanly from
insufficient resources; users should register a genuinely small trainable base model.
There are no data migrations or specification deviations.
