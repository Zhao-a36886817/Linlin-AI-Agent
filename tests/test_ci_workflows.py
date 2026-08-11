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
    for check in (
        "pytest",
        "ruff",
        "npm audit",
        "pip-audit",
        "supply_chain.py scan",
        "cargo check",
    ):
        assert check in text


def test_every_external_action_is_pinned_to_full_sha() -> None:
    for path in WORKFLOWS.glob("*.yml"):
        for action in re.findall(
            r"uses:\s*([^\s#]+)", path.read_text(encoding="utf-8")
        ):
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", action), (
                f"unpinned action: {action}"
            )


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
    assert "inputs.evidence_confirmation == 'GENERATE_EVIDENCE'" in text
    assert "does not approve or publish the RC" in text
    assert "inputs.promotion == 'PROMOTE'" not in text
    assert "TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}" in text
    assert (
        "TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY_PASSWORD }}"
        in text
    )
    assert not re.search(r"(?:echo|Write-Output).*TAURI_SIGNING", text, re.IGNORECASE)
    assert "attestations: write" not in text
    assert "artifact-metadata: write" not in text
    assert "id-token: write" in text


def test_release_preserves_commit_bound_three_platform_p24_evidence() -> None:
    """Workflow 必須產出可下載證據，不能只在 log 宣稱 build/attest 成功。"""

    text = workflow("release.yml")
    assert "scripts/release_evidence.py stage" in text
    assert "scripts/release_evidence.py checksums" in text
    assert "scripts/release_evidence.py platform" in text
    assert "scripts/release_evidence.py aggregate" in text
    assert "needs: signed-candidate" in text
    for platform in ("windows", "linux", "macos"):
        assert f"linlin-agent-evidence-{platform}" in text
    assert "${{ github.sha }}" in text
    assert "${{ github.run_id }}" in text
    assert (
        "sigstore/gh-action-sigstore-python@5b79a39c381910c090341a2c9b0bf022c8b387e1"
        in text
    )
    assert (
        'verify-cert-identity: "https://github.com/${{ github.workflow_ref }}"' in text
    )
    assert 'verify-oidc-issuer: "https://token.actions.githubusercontent.com"' in text
    assert "actions/attest@" not in text
    assert 'bundles: "nsis"' in text
    assert "tauri build --bundles ${{ matrix.bundles }}" in text
    assert '--bundle "release-staging/${{ matrix.artifact }}"' in text
    assert "p24-release-evidence" in text
