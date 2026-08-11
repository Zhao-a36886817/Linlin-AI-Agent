from pathlib import Path


def test_supervisor_has_no_git_add_all() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "laes_supervisor.py").read_text(encoding="utf-8")
    assert "git add ." not in source


def test_transition_requires_both_approvals() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "laes_supervisor.py").read_text(encoding="utf-8")
    assert 's.get("reviewer_approved")' in source
    assert 's.get("owner_approved")' in source


def test_worker_info_does_not_launch_codex() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "laes_supervisor.py").read_text(encoding="utf-8")
    assert 'subprocess.run(["codex"' not in source


def test_reopen_requires_existing_and_explicit_owner_approval() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "laes_supervisor.py").read_text(encoding="utf-8")
    assert "if not args.owner_approved" in source
    assert 's.get("gate") == "APPROVED"' in source
    assert 's.get("reviewer_approved")' in source
    assert 's.get("owner_approved")' in source


def test_reprioritize_requires_owner_and_does_not_forge_pass() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "laes_supervisor.py").read_text(encoding="utf-8")
    assert "def cmd_reprioritize" in source
    assert "if not args.owner_approved" in source
    assert 'current_state.get("checks") != "FAIL"' in source
    assert 'current_state.get("gate") == "IN_PROGRESS"' in source
    assert 'current_state.get("checks") == "NOT_RUN"' in source
    assert '"gate": "NOT_STARTED"' in source
    assert '"checks": "NOT_RUN"' in source


def test_supervisor_writes_review_packages_to_phase_artifact_tree() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "laes_supervisor.py").read_text(
        encoding="utf-8"
    )
    assert 'PHASE_ARTIFACTS = ROOT / "docs" / "governance" / "phase-artifacts"' in source
    assert 'path = PHASE_ARTIFACTS / results["phase"] / name' in source
