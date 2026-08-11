from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import zipfile
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest

from app.portability import (
    BACKUP_FORMAT,
    BACKUP_SCHEMA_VERSION,
    PortabilityError,
    PortabilityRuntime,
)
from app.security.credential_store import CredentialStore, SessionCredentialBackend
from app.workspace import WorkspaceRuntime


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    return root


@pytest.fixture
def runtime(workspace_root: Path) -> PortabilityRuntime:
    return PortabilityRuntime(WorkspaceRuntime(workspace_root))


def test_round_trip_restore_is_deterministic(
    runtime: PortabilityRuntime,
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    (workspace_root / "empty").mkdir()
    (workspace_root / "folder").mkdir()
    (workspace_root / "folder" / "資料.txt").write_text("original\n", encoding="utf-8")
    first = tmp_path / "backups" / "first.linlin-backup"
    second = tmp_path / "backups" / "second.linlin-backup"

    summary = runtime.create_backup(first)
    (workspace_root / "folder" / "資料.txt").write_text("changed", encoding="utf-8")
    (workspace_root / "new.txt").write_text("not in backup", encoding="utf-8")

    report = runtime.restore_backup(first)
    runtime.create_backup(second)

    assert (workspace_root / "folder" / "資料.txt").read_text(encoding="utf-8") == "original\n"
    assert (workspace_root / "empty").is_dir()
    assert not (workspace_root / "new.txt").exists()
    assert first.read_bytes() == second.read_bytes()
    assert summary.files == report.files == 1
    assert report.rpo_bytes == 0
    assert report.rehearsal is False


def test_manifest_is_versioned_and_preserves_logical_security_metadata(
    runtime: PortabilityRuntime,
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    target = workspace_root / "private.txt"
    target.write_text("private", encoding="utf-8")
    os.chmod(target, 0o600)
    backup = tmp_path / "metadata.linlin-backup"

    runtime.create_backup(backup)
    manifest = runtime.verify_backup(backup)
    entry = next(item for item in manifest.entries if item.path == "private.txt")

    assert manifest.format == BACKUP_FORMAT
    assert manifest.schema_version == BACKUP_SCHEMA_VERSION == 1
    assert manifest.logical_root == "workspace"
    assert entry.logical_owner == "workspace"
    assert entry.mode == stat.S_IMODE(target.stat().st_mode) & 0o777


def test_restore_rehearsal_reports_rpo_rto_without_changing_workspace(
    runtime: PortabilityRuntime,
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    source = workspace_root / "state.txt"
    source.write_text("backup state", encoding="utf-8")
    backup = tmp_path / "rehearsal.linlin-backup"
    runtime.create_backup(backup)
    source.write_text("live state", encoding="utf-8")

    report = runtime.rehearse_restore(backup)

    assert source.read_text(encoding="utf-8") == "live state"
    assert report.rehearsal is True
    assert report.rpo_bytes == 0
    assert report.rto_seconds >= 0


def test_interrupted_restore_rolls_back_to_pre_restore_state(
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    source = workspace_root / "state.txt"
    source.write_text("backup state", encoding="utf-8")
    healthy = PortabilityRuntime(WorkspaceRuntime(workspace_root))
    backup = tmp_path / "rollback.linlin-backup"
    healthy.create_backup(backup)
    source.write_text("live state", encoding="utf-8")

    class InterruptedRuntime(PortabilityRuntime):
        def _activate_stage(self, stage: Path, root: Path) -> None:
            raise OSError("simulated interruption")

    interrupted = InterruptedRuntime(WorkspaceRuntime(workspace_root))
    with pytest.raises(PortabilityError, match="rolled back safely"):
        interrupted.restore_backup(backup)

    assert source.read_text(encoding="utf-8") == "live state"
    assert not interrupted._journal_path.exists()
    assert not list(tmp_path.glob(".workspace.linlin-stage-*"))
    assert not list(tmp_path.glob(".workspace.linlin-rollback-*"))


def test_fresh_process_bootstrap_recovers_missing_workspace(
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    (workspace_root / "state.txt").write_text("original", encoding="utf-8")
    runtime = PortabilityRuntime(WorkspaceRuntime(workspace_root))
    transaction_id = uuid4().hex
    stage, rollback = runtime._transaction_paths(transaction_id)
    stage.mkdir()
    (stage / "state.txt").write_text("replacement", encoding="utf-8")
    runtime._write_journal(transaction_id, "prepared")
    workspace_root.replace(rollback)
    runtime._write_journal(transaction_id, "old_moved")
    del runtime
    environment = os.environ.copy()
    environment["WORKSPACE_ROOT"] = str(workspace_root)

    assert not workspace_root.exists()
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from app.main import app; "
                "from app.core.config import get_settings; "
                "root = get_settings().workspace_root; "
                "print(app.title); print((root / 'state.txt').read_text())"
            ),
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert "Linlin Agent\noriginal" in process.stdout
    fresh_runtime = PortabilityRuntime(WorkspaceRuntime(workspace_root))
    assert (workspace_root / "state.txt").read_text(encoding="utf-8") == "original"
    assert not stage.exists()
    assert not rollback.exists()
    assert not fresh_runtime._journal_path.exists()
    assert tmp_path.is_dir()


def test_non_file_recovery_journal_fails_closed(
    runtime: PortabilityRuntime,
) -> None:
    runtime._journal_path.mkdir()

    with pytest.raises(PortabilityError, match="journal is unsafe"):
        runtime.recover_interrupted()


def test_archive_device_members_are_rejected(
    runtime: PortabilityRuntime,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "device.linlin-backup"
    device = zipfile.ZipInfo("payload/device")
    device.create_system = 3
    device.external_attr = (stat.S_IFCHR | 0o600) << 16
    payload = b"device"
    manifest = {
        "format": BACKUP_FORMAT,
        "schema_version": 1,
        "logical_root": "workspace",
        "root_mode": 0o700,
        "entries": [
            {
                "path": "device",
                "kind": "file",
                "logical_owner": "workspace",
                "mode": 0o600,
                "size_bytes": len(payload),
                "sha256": sha256(payload).hexdigest(),
            }
        ],
    }
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(device, payload)

    with pytest.raises(PortabilityError, match="unsafe member"):
        runtime.verify_backup(backup)


def test_corrupt_payload_is_rejected_before_restore(
    runtime: PortabilityRuntime,
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    (workspace_root / "state.txt").write_text("trusted", encoding="utf-8")
    valid = tmp_path / "valid.linlin-backup"
    corrupt = tmp_path / "corrupt.linlin-backup"
    runtime.create_backup(valid)
    _rewrite_archive(valid, corrupt, {"payload/state.txt": b"tampered"})

    with pytest.raises(PortabilityError, match="size|integrity"):
        runtime.verify_backup(corrupt)
    assert (workspace_root / "state.txt").read_text(encoding="utf-8") == "trusted"


@pytest.mark.parametrize(
    "member",
    ["payload/../escape.txt", "payload\\escape.txt", "payload/C:/escape.txt"],
)
def test_malicious_archive_paths_are_rejected(
    runtime: PortabilityRuntime,
    tmp_path: Path,
    member: str,
) -> None:
    backup = tmp_path / f"malicious-{uuid4().hex}.linlin-backup"
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("manifest.json", _empty_manifest())
        archive.writestr(member, "escape")

    with pytest.raises(PortabilityError, match="unsafe path|do not match"):
        runtime.verify_backup(backup)


def test_archive_symbolic_links_are_rejected(
    runtime: PortabilityRuntime,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "symlink.linlin-backup"
    link = zipfile.ZipInfo("payload/link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    manifest = {
        "format": BACKUP_FORMAT,
        "schema_version": 1,
        "logical_root": "workspace",
        "root_mode": 0o700,
        "entries": [
            {
                "path": "link",
                "kind": "file",
                "logical_owner": "workspace",
                "mode": 0o600,
                "size_bytes": 6,
                "sha256": "0" * 64,
            }
        ],
    }
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(link, "target")

    with pytest.raises(PortabilityError, match="unsafe member"):
        runtime.verify_backup(backup)


def test_unknown_backup_schema_requires_explicit_migration(
    runtime: PortabilityRuntime,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "future.linlin-backup"
    payload = json.loads(_empty_manifest())
    payload["schema_version"] = 2
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("manifest.json", json.dumps(payload))

    with pytest.raises(PortabilityError, match="invalid or unreadable"):
        runtime.verify_backup(backup)


def test_archive_inside_workspace_and_source_symlinks_are_rejected(
    runtime: PortabilityRuntime,
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    with pytest.raises(PortabilityError, match="outside the workspace"):
        runtime.create_backup(workspace_root / "backup.linlin-backup")

    link = workspace_root / "link"
    try:
        link.symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform/account.")
    with pytest.raises(PortabilityError, match="symbolic links"):
        runtime.create_backup(tmp_path / "symlink-source.linlin-backup")


def test_credential_store_is_outside_plaintext_export_boundary(
    runtime: PortabilityRuntime,
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    credentials = CredentialStore(SessionCredentialBackend(), environment={})
    credentials.set("PROVIDER_API_KEY", "credential-must-not-be-exported")
    (workspace_root / "user.txt").write_text("portable user data", encoding="utf-8")
    backup = tmp_path / "no-credentials.linlin-backup"

    runtime.create_backup(backup)

    with zipfile.ZipFile(backup) as archive:
        exported = b"\n".join(archive.read(name) for name in archive.namelist())
    assert b"credential-must-not-be-exported" not in exported
    assert credentials.get("PROVIDER_API_KEY") == "credential-must-not-be-exported"


def _empty_manifest() -> str:
    return json.dumps(
        {
            "format": BACKUP_FORMAT,
            "schema_version": 1,
            "logical_root": "workspace",
            "root_mode": 0o700,
            "entries": [],
        }
    )


def _rewrite_archive(
    source_path: Path,
    target_path: Path,
    replacements: dict[str, bytes],
) -> None:
    with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(target_path, "w") as target:
        for member in source.infolist():
            target.writestr(member, replacements.get(member.filename, source.read(member)))
