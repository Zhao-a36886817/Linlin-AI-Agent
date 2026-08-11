import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_ci_represents_all_supported_platforms_and_required_checks() -> None:
    text = workflow("ci.yml")
    for runner in ("ubuntu-latest", "windows-latest", "macos-latest"):
        assert runner in text
    for check in ("pytest", "ruff", "npm audit", "pip-audit", "supply_chain.py scan", "cargo check"):
        assert check in text


def test_every_external_action_is_pinned_to_full_sha() -> None:
    for path in WORKFLOWS.glob("*.yml"):
        for action in re.findall(r"uses:\s*([^\s#]+)", path.read_text(encoding="utf-8")):
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", action), f"unpinned action: {action}"


def test_workflows_are_least_privilege_and_avoid_untrusted_target_trigger() -> None:
    for name in ("ci.yml", "release.yml"):
        text = workflow(name)
        assert "pull_request_target" not in text
        assert "contents: read" in text
        assert "persist-credentials: false" in text


def test_release_is_manual_gated_and_never_logs_signing_secrets() -> None:
    text = workflow("release.yml")
    assert "workflow_dispatch:" in text
    assert "environment: production" in text
    assert "inputs.promotion == 'PROMOTE'" in text
    assert "TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}" in text
    assert "TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY_PASSWORD }}" in text
    assert not re.search(r"(?:echo|Write-Output).*TAURI_SIGNING", text, re.IGNORECASE)
    assert "attestations: write" in text
    assert "id-token: write" in text
