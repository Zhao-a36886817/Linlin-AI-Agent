# Linlin Agent Testing Standard

## Principles

- Tests verify behavior; they are not obstacles to be removed.
- A failing required check is a blocker until explained or fixed.
- Do not hide failures by broad ignores or weakened assertions.

## Baseline Checks

Backend, when applicable:

```bash
python -m compileall app tests
python -m ruff check app tests
python -m pytest tests -q
```

Frontend, when applicable:

```bash
npm run build
npm run lint
```

Desktop/Tauri, when applicable:

```bash
cargo check
```

The active P-stage file may narrow or extend these commands.
