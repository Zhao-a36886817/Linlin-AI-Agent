from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.workspace import WorkspaceError, WorkspaceRuntime


@pytest.fixture
def runtime(tmp_path: Path) -> WorkspaceRuntime:
    root = tmp_path / "workspace"
    root.mkdir()
    return WorkspaceRuntime(root)


@pytest.mark.parametrize("path", ["../escape", "..\\escape"])
def test_rejects_parent_traversal(runtime: WorkspaceRuntime, path: str) -> None:
    with pytest.raises(WorkspaceError):
        runtime.resolve(path)


def test_rejects_absolute_path(runtime: WorkspaceRuntime, tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError):
        runtime.resolve(tmp_path.resolve())


@pytest.mark.parametrize("path", ["C:\\outside", "\\\\server\\share\\file"])
def test_rejects_windows_absolute_paths(runtime: WorkspaceRuntime, path: str) -> None:
    with pytest.raises(WorkspaceError):
        runtime.resolve(path)


def test_rejects_symlink_escape(runtime: WorkspaceRuntime, tmp_path: Path) -> None:
    link = runtime.root / "outside"
    try:
        link.symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform/account.")
    with pytest.raises(WorkspaceError):
        runtime.resolve("outside/secret.txt")


@pytest.mark.parametrize("member", ["../escape.txt", "..\\escape.txt", "/absolute.txt"])
def test_rejects_zip_slip(runtime: WorkspaceRuntime, member: str) -> None:
    archive = runtime.root / "bad.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr(member, "blocked")
    with pytest.raises(WorkspaceError):
        runtime.extract_zip("bad.zip", "output")


def test_extracts_valid_zip_and_rejects_overwrite(runtime: WorkspaceRuntime) -> None:
    archive = runtime.root / "safe.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("folder/file.txt", "safe")
    extracted = runtime.extract_zip("safe.zip", "output")
    assert extracted[0].read_text(encoding="utf-8") == "safe"
    with pytest.raises(WorkspaceError):
        runtime.extract_zip("safe.zip", "output")


def test_cwd_cannot_escape(runtime: WorkspaceRuntime) -> None:
    with pytest.raises(WorkspaceError):
        runtime.resolve_cwd("../outside")
