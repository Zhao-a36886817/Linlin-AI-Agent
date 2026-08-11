# Cross-platform development

The supported source environments are Windows, Linux, and macOS. Create the
Conda environment by name rather than by a machine-specific prefix:

```text
conda env create -f environment.yml
conda activate Linlin_agent
```

Backend validation is identical in PowerShell and POSIX shells when the
environment is active:

```text
cd backend
python -m compileall app tests
python -m ruff check app tests
python -m pytest tests -q
```

Frontend validation uses the checked-in npm lockfile:

```text
cd frontend
npm ci
npm run build
npm run lint
```

Runtime data paths are derived from the repository and settings. Do not add
usernames, drive letters, shell-specific assumptions, or absolute environment
prefixes to active configuration.
