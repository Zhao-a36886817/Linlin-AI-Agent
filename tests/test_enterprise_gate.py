from __future__ import annotations

import subprocess
from hashlib import sha256
from pathlib import Path

from scripts.enterprise_gate import (
    PASS_MARKER,
    PHASES,
    approval_ledger,
    audit_repository,
    evidence_index,
    manifest_integrity,
    owner_decision,
    phase_artifact_path,
)

ROOT = Path(__file__).parents[1]


def _git(repository: Path, *arguments: str) -> None:
    """在不支援 ownership 的 F: 測試目錄中，只信任這一個臨時 repository。"""

    subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repository.resolve().as_posix()}",
            *arguments,
        ],
        cwd=repository,
        check=True,
    )


def test_all_p0_p23_supervisor_packages_publish_pass_evidence() -> None:
    for phase in PHASES:
        package = phase_artifact_path(
            ROOT,
            phase,
            f"{phase}_SUPERVISOR_REVIEW_PACKAGE.md",
        )
        assert package.is_file(), phase
        assert PASS_MARKER in package.read_text(encoding="utf-8", errors="replace")


def test_phase_artifacts_do_not_regress_into_repository_root() -> None:
    """Future iterations must keep generated phase evidence out of the root."""

    root_artifacts = [
        path.name
        for path in ROOT.iterdir()
        if path.is_file()
        and (
            path.name.endswith("_COMPLETION_REPORT.md")
            or path.name.startswith("P")
            and path.name.endswith("_SUPERVISOR_REVIEW_PACKAGE.md")
            or path.name in {"P24_EVIDENCE_INDEX.json", "P24_RC_DECISION.yaml"}
        )
    ]
    assert root_artifacts == []


def test_evidence_index_is_deterministic_and_covers_every_phase() -> None:
    first = evidence_index(ROOT)
    second = evidence_index(ROOT)

    assert first == second
    assert {item["phase"] for item in first} == set(PHASES)
    assert len(first) == len(PHASES) * 4


def test_current_source_matches_explicit_owner_decision_and_fails_closed() -> None:
    """目前倉庫可由 NO_GO 進入 GO，但必須維持決策與證據一致。

    舊測試把一次性的 P24 初始狀態永久寫死為 NO_GO，導致真正補齊三平台證據並
    取得 owner GO 後，正確的 Gate 結果反而會讓測試失敗。這裡改驗證不變條件：
    只有零阻擋、有效且一致的 owner GO 才能授權；任何其他狀態都必須 fail closed。
    """

    result = audit_repository(ROOT)
    decision = owner_decision(ROOT)

    assert decision["valid"] is True
    assert result["recommendation"] in {"GO", "NO_GO"}
    if result["recommendation"] == "GO":
        assert result["blockers"] == []
        assert decision["decision"] == "GO"
        assert result["decision_consistent"] is True
        assert result["release_authorized"] is True
    else:
        # Dirty source、證據缺漏、owner NO_GO 或任何不一致狀態都不能取得授權。
        assert result["release_authorized"] is False


def test_approval_ledger_binds_all_phases_to_durable_sources() -> None:
    """24 個 YAML 檔本身不夠；每一筆 package/transcript 驗證都必須通過。"""

    ledger = approval_ledger(ROOT)

    assert ledger["expected"] == len(PHASES)
    assert ledger["valid"] == len(PHASES)
    assert ledger["valid_phases"] == list(PHASES)
    assert ledger["invalid"] == []


def test_manifest_integrity_reports_changed_content_without_values(tmp_path: Path) -> None:
    # 建立最小 Git repository，讓測試同時驗證 manifest 不只檢查已列項目，
    # 也會從 Git 發現被刻意漏列的新來源檔案。
    _git(tmp_path, "init", "-q")
    target = tmp_path / "document.txt"
    target.write_text("approved", encoding="utf-8")
    _git(tmp_path, "add", "document.txt")
    digest = sha256(target.read_bytes()).hexdigest()
    (tmp_path / "MANIFEST.sha256").write_text(
        f"{digest}  document.txt\n",
        encoding="utf-8",
    )

    assert manifest_integrity(tmp_path)["mismatched"] == []
    target.write_text("changed", encoding="utf-8")
    result = manifest_integrity(tmp_path)
    assert result["mismatched"] == ["document.txt"]
    assert "changed" not in str(result)


def test_manifest_integrity_reports_unlisted_git_source(tmp_path: Path) -> None:
    """只替少數檔案寫雜湊不能冒充完整來源 manifest。"""

    _git(tmp_path, "init", "-q")
    listed = tmp_path / "listed.txt"
    omitted = tmp_path / "omitted.txt"
    listed.write_text("listed", encoding="utf-8")
    omitted.write_text("must also be covered", encoding="utf-8")
    _git(tmp_path, "add", "listed.txt", "omitted.txt")
    digest = sha256(listed.read_bytes()).hexdigest()
    (tmp_path / "MANIFEST.sha256").write_text(
        f"{digest}  listed.txt\n",
        encoding="utf-8",
    )

    result = manifest_integrity(tmp_path)
    assert result["unlisted"] == ["omitted.txt"]
    assert result["discovery_error"] is None


def test_owner_decision_must_be_explicit_and_well_formed(tmp_path: Path) -> None:
    assert owner_decision(tmp_path)["decision"] == "PENDING"
    decision_path = phase_artifact_path(tmp_path, "P24", "P24_RC_DECISION.yaml")
    decision_path.parent.mkdir(parents=True)
    decision_path.write_text(
        """schema_version: 1
decision: NO_GO
owner: project-owner
recorded_at: \"2026-08-09T00:00:00+08:00\"
rationale: \"Release blockers remain open.\"
""",
        encoding="utf-8",
    )

    result = owner_decision(tmp_path)
    assert result["valid"] is True
    assert result["decision"] == "NO_GO"
