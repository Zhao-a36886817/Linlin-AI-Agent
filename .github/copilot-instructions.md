# Linlin Agent Repository Instructions

Before modifying code, follow:

- `AI_COLLABORATION_CHARTER.md`
- `AGENTS.md`
- `docs/standards/Engineering_Standard.md`
- `docs/architecture/System_Architecture.md`
- `.laes/CURRENT_PHASE.yaml`
- the active P-stage document

Mandatory rules:

- Minimum Change Policy.
- Only the current P stage may be implemented.
- Do not redesign accepted architecture.
- Do not replace frameworks without approval.
- Do not bypass Provider Runtime, Tool Runtime, Workspace Runtime, or Credential Store.
- Preserve Windows/Linux/macOS compatibility.
- Never expose credentials or secrets.
- Run required validation.
- Never suppress, disable, or weaken failing tests merely to obtain PASS.
- Stop after completing one P stage.
- Do not start the next P stage without ChatGPT PASS review and explicit project-owner approval.
