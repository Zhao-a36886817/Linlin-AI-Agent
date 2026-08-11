from __future__ import annotations

import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath


class WorkspaceError(RuntimeError):
    """Raised when an operation would violate the workspace boundary."""


class WorkspaceRuntime:
    """Canonical boundary for agent-visible filesystem paths."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise WorkspaceError(f"Workspace does not exist: {self.root}")

    def resolve(self, relative_path: str | Path) -> Path:
        raw = str(relative_path)
        if "\\" in raw:
            raw = raw.replace("\\", "/")
        candidate = Path(raw)
        if (
            candidate.is_absolute()
            or PurePosixPath(raw).is_absolute()
            or PureWindowsPath(raw).is_absolute()
        ):
            raise WorkspaceError("Absolute workspace paths are not allowed.")
        target = (self.root / candidate).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("Access outside workspace is not allowed.") from exc
        return target

    def resolve_cwd(self, relative_path: str | Path = ".") -> Path:
        target = self.resolve(relative_path)
        if not target.is_dir():
            raise WorkspaceError("Working directory must be inside the workspace.")
        return target

    def extract_zip(
        self,
        archive: str | Path,
        destination: str | Path = ".",
        *,
        overwrite: bool = False,
    ) -> list[Path]:
        archive_path = self.resolve(archive)
        destination_root = self.resolve(destination)
        destination_root.mkdir(parents=True, exist_ok=True)
        extracted: list[Path] = []
        with zipfile.ZipFile(archive_path) as source:
            for member in source.infolist():
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise WorkspaceError("Archive symbolic links are not allowed.")
                target = self._archive_target(destination_root, member.filename)
                if target.exists() and not overwrite:
                    raise WorkspaceError(f"Archive target already exists: {member.filename}")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as input_stream, target.open("wb") as output_stream:
                    shutil.copyfileobj(input_stream, output_stream)
                extracted.append(target)
        return extracted

    def _archive_target(self, destination: Path, member_name: str) -> Path:
        normalized = member_name.replace("\\", "/")
        member = PurePosixPath(normalized)
        if member.is_absolute() or ".." in member.parts:
            raise WorkspaceError("Archive member escapes the destination.")
        target = (destination / Path(*member.parts)).resolve()
        try:
            target.relative_to(destination.resolve())
        except ValueError as exc:
            raise WorkspaceError("Archive member escapes the destination.") from exc
        return target
