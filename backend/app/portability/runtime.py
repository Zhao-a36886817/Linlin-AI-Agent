from __future__ import annotations

import json
import os
import shutil
import stat
import unicodedata
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath, PureWindowsPath
from time import monotonic
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.workspace import WorkspaceRuntime

BACKUP_FORMAT = "linlin-workspace-backup"
BACKUP_SCHEMA_VERSION = 1
_MANIFEST_NAME = "manifest.json"
_PAYLOAD_PREFIX = "payload/"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_INVALID_PORTABLE_CHARS = frozenset('<>:"|?*')
_WINDOWS_RESERVED_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{number}" for number in range(1, 10)}
    | {f"lpt{number}" for number in range(1, 10)}
)


class PortabilityError(RuntimeError):
    """Raised when a backup or recovery operation is unsafe or invalid."""


class BackupEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    kind: Literal["file", "directory"]
    logical_owner: Literal["workspace"] = "workspace"
    mode: int = Field(ge=0, le=0o777)
    size_bytes: int = Field(default=0, ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_kind_metadata(self) -> Self:
        _validate_portable_relative_path(self.path)
        if self.kind == "directory" and (self.size_bytes or self.sha256 is not None):
            raise ValueError("Directory entries cannot contain file metadata.")
        if self.kind == "file" and self.sha256 is None:
            raise ValueError("File entries require a SHA-256 digest.")
        return self


class BackupManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal[BACKUP_FORMAT] = BACKUP_FORMAT
    schema_version: int = Field(
        default=BACKUP_SCHEMA_VERSION,
        ge=BACKUP_SCHEMA_VERSION,
        le=BACKUP_SCHEMA_VERSION,
    )
    logical_root: Literal["workspace"] = "workspace"
    root_mode: int = Field(ge=0, le=0o777)
    entries: tuple[BackupEntry, ...]

    @model_validator(mode="after")
    def validate_entries(self) -> Self:
        paths = [entry.path for entry in self.entries]
        if paths != sorted(paths):
            raise ValueError("Backup entries must use deterministic path ordering.")
        if len(paths) != len(set(paths)):
            raise ValueError("Backup entries must use unique paths.")
        portable = [_portable_key(path) for path in paths]
        if len(portable) != len(set(portable)):
            raise ValueError("Backup paths collide on a supported platform.")
        entries_by_path = {entry.path: entry for entry in self.entries}
        for entry in self.entries:
            parts = PurePosixPath(entry.path).parts
            for depth in range(1, len(parts)):
                parent = "/".join(parts[:depth])
                parent_entry = entries_by_path.get(parent)
                if parent_entry is None or parent_entry.kind != "directory":
                    raise ValueError("Backup entries must declare their directories.")
        return self


@dataclass(frozen=True, slots=True)
class BackupSummary:
    archive: Path
    files: int
    directories: int
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    files: int
    directories: int
    size_bytes: int
    rpo_bytes: int
    rto_seconds: float
    rehearsal: bool
    recovered_interrupted_transaction: bool = False


class PortabilityRuntime:
    """Versioned, deterministic backup and transactional workspace recovery."""

    def __init__(
        self,
        workspace: WorkspaceRuntime,
        *,
        max_entries: int = 10_000,
        max_total_bytes: int = 512 * 1024 * 1024,
    ) -> None:
        if max_entries < 1 or max_total_bytes < 1:
            raise ValueError("Backup limits must be positive.")
        self._workspace = workspace
        self._max_entries = max_entries
        self._max_total_bytes = max_total_bytes

    def create_backup(self, archive_path: str | Path) -> BackupSummary:
        archive = self._external_archive_path(archive_path)
        if archive.exists():
            raise PortabilityError("Backup target already exists.")
        archive.parent.mkdir(parents=True, exist_ok=True)

        manifest = self._snapshot_workspace()
        temporary = archive.with_name(f".{archive.name}.{uuid4().hex}.tmp")
        try:
            with zipfile.ZipFile(
                temporary,
                mode="x",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as target:
                self._write_archive_member(
                    target,
                    _MANIFEST_NAME,
                    _manifest_bytes(manifest),
                    0o600,
                )
                for entry in manifest.entries:
                    if entry.kind == "file":
                        self._write_workspace_file(
                            target,
                            f"{_PAYLOAD_PREFIX}{entry.path}",
                            entry,
                        )
            temporary.replace(archive)
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise PortabilityError("Unable to create the backup archive.") from exc
        finally:
            temporary.unlink(missing_ok=True)

        data = archive.read_bytes()
        return BackupSummary(
            archive=archive,
            files=sum(entry.kind == "file" for entry in manifest.entries),
            directories=sum(entry.kind == "directory" for entry in manifest.entries),
            size_bytes=sum(entry.size_bytes for entry in manifest.entries),
            sha256=sha256(data).hexdigest(),
        )

    def verify_backup(self, archive_path: str | Path) -> BackupManifest:
        archive_path = self._external_archive_path(archive_path)
        try:
            with zipfile.ZipFile(archive_path) as archive:
                return self._verify_open_archive(archive)
        except PortabilityError:
            raise
        except (
            OSError,
            RuntimeError,
            ValueError,
            zipfile.BadZipFile,
            ValidationError,
        ) as exc:
            raise PortabilityError("Backup archive is invalid or unreadable.") from exc

    def rehearse_restore(self, archive_path: str | Path) -> RecoveryReport:
        started = monotonic()
        manifest = self.verify_backup(archive_path)
        transaction_id = uuid4().hex
        stage, _ = self._transaction_paths(transaction_id)
        try:
            self._stage_archive(archive_path, manifest, stage)
        finally:
            self._remove_transaction_path(stage)
        return self._report(manifest, started, rehearsal=True)

    def restore_backup(self, archive_path: str | Path) -> RecoveryReport:
        started = monotonic()
        recovered = self.recover_interrupted()
        manifest = self.verify_backup(archive_path)
        transaction_id = uuid4().hex
        stage, rollback = self._transaction_paths(transaction_id)
        self._stage_archive(archive_path, manifest, stage)
        self._write_journal(transaction_id, "prepared")

        try:
            self._workspace.root.replace(rollback)
            self._write_journal(transaction_id, "old_moved")
            self._activate_stage(stage, self._workspace.root)
            self._write_journal(transaction_id, "committed")
        except (OSError, RuntimeError) as exc:
            try:
                self.recover_interrupted()
            except PortabilityError as recovery_exc:
                raise PortabilityError(
                    "Restore failed and automatic rollback also failed."
                ) from recovery_exc
            raise PortabilityError("Restore failed and was rolled back safely.") from exc

        self._remove_transaction_path(rollback)
        self._journal_path.unlink(missing_ok=True)
        return self._report(
            manifest,
            started,
            rehearsal=False,
            recovered=recovered,
        )

    def recover_interrupted(self) -> bool:
        return self.recover_workspace(self._workspace.root)

    @classmethod
    def recover_workspace(cls, workspace_root: str | Path) -> bool:
        """Recover a pending transaction before WorkspaceRuntime can be created."""

        root = Path(workspace_root).expanduser().resolve()
        journal = cls._journal_for_root(root)
        if journal.is_symlink():
            raise PortabilityError("Restore recovery journal is unsafe.")
        if journal.exists() and not journal.is_file():
            raise PortabilityError("Restore recovery journal is unsafe.")
        if not journal.exists():
            return False
        transaction_id, state = cls._read_journal(journal)
        stage, rollback = cls._transaction_paths_for_root(root, transaction_id)
        if root.exists() and not root.is_dir():
            raise PortabilityError("Configured workspace recovery path is unsafe.")
        for transaction_path in (stage, rollback):
            if transaction_path.is_symlink() or (
                transaction_path.exists() and not transaction_path.is_dir()
            ):
                raise PortabilityError("Restore transaction path is unsafe.")

        if state == "committed":
            if not root.is_dir():
                if not rollback.is_dir():
                    raise PortabilityError("Committed restore has no recoverable workspace.")
                rollback.replace(root)
            cls._remove_transaction_path(stage)
            cls._remove_transaction_path(rollback)
            journal.unlink(missing_ok=True)
            return True

        if rollback.is_dir():
            if root.exists():
                if stage.exists():
                    raise PortabilityError("Restore recovery paths are inconsistent.")
                root.replace(stage)
            rollback.replace(root)
        elif not root.is_dir():
            raise PortabilityError("Interrupted restore has no rollback workspace.")

        cls._remove_transaction_path(stage)
        journal.unlink(missing_ok=True)
        return True

    @property
    def _journal_path(self) -> Path:
        return self._journal_for_root(self._workspace.root)

    def _snapshot_workspace(self) -> BackupManifest:
        entries: list[BackupEntry] = []
        root = self._workspace.root

        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
            if path.is_symlink():
                raise PortabilityError("Workspace symbolic links cannot be exported.")
            relative = path.relative_to(root).as_posix()
            try:
                _validate_portable_relative_path(relative)
            except ValueError as exc:
                raise PortabilityError(
                    "Workspace contains a non-portable path."
                ) from exc
            mode = stat.S_IMODE(path.stat().st_mode) & 0o777
            if path.is_dir():
                entries.append(BackupEntry(path=relative, kind="directory", mode=mode))
                continue
            if not path.is_file():
                raise PortabilityError("Workspace special files cannot be exported.")
            digest = sha256()
            size = 0
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    size += len(block)
                    digest.update(block)
            entries.append(
                BackupEntry(
                    path=relative,
                    kind="file",
                    mode=mode,
                    size_bytes=size,
                    sha256=digest.hexdigest(),
                )
            )

        total_bytes = sum(entry.size_bytes for entry in entries)
        self._check_limits(len(entries), total_bytes)
        return BackupManifest(
            root_mode=stat.S_IMODE(root.stat().st_mode) & 0o777,
            entries=tuple(entries),
        )

    def _verify_open_archive(self, archive: zipfile.ZipFile) -> BackupManifest:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)) or len(names) != len({_portable_key(x) for x in names}):
            raise PortabilityError("Backup archive contains colliding members.")
        if len(members) > self._max_entries + 1:
            raise PortabilityError("Backup archive contains too many entries.")
        for member in members:
            try:
                _validate_portable_relative_path(member.filename)
            except ValueError as exc:
                raise PortabilityError("Backup archive contains an unsafe path.") from exc
            member_type = stat.S_IFMT(member.external_attr >> 16)
            if member.is_dir() or member_type not in {0, stat.S_IFREG}:
                raise PortabilityError("Backup archive contains an unsafe member.")

        try:
            manifest_member = archive.getinfo(_MANIFEST_NAME)
        except KeyError as exc:
            raise PortabilityError("Backup manifest is missing.") from exc
        if manifest_member.file_size > 2_000_000:
            raise PortabilityError("Backup manifest exceeds the size limit.")
        manifest = BackupManifest.model_validate_json(archive.read(manifest_member))
        self._check_limits(
            len(manifest.entries),
            sum(entry.size_bytes for entry in manifest.entries),
        )

        files = [entry for entry in manifest.entries if entry.kind == "file"]
        expected = {_MANIFEST_NAME} | {
            f"{_PAYLOAD_PREFIX}{entry.path}" for entry in files
        }
        if set(names) != expected:
            raise PortabilityError("Backup members do not match the manifest.")

        for entry in files:
            member = archive.getinfo(f"{_PAYLOAD_PREFIX}{entry.path}")
            if member.file_size != entry.size_bytes:
                raise PortabilityError("Backup member size does not match the manifest.")
            digest = sha256()
            with archive.open(member) as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != entry.sha256:
                raise PortabilityError("Backup member integrity check failed.")
        return manifest

    def _stage_archive(
        self,
        archive_path: str | Path,
        manifest: BackupManifest,
        stage: Path,
    ) -> None:
        if stage.exists():
            raise PortabilityError("Restore staging path already exists.")
        stage.mkdir(mode=0o700)
        try:
            directories = [entry for entry in manifest.entries if entry.kind == "directory"]
            for entry in directories:
                self._stage_target(stage, entry.path).mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(self._external_archive_path(archive_path)) as archive:
                for entry in manifest.entries:
                    if entry.kind != "file":
                        continue
                    target = self._stage_target(stage, entry.path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    digest = sha256()
                    size = 0
                    with (
                        archive.open(f"{_PAYLOAD_PREFIX}{entry.path}") as source,
                        target.open("xb") as destination,
                    ):
                        for block in iter(lambda: source.read(1024 * 1024), b""):
                            size += len(block)
                            digest.update(block)
                            destination.write(block)
                    if size != entry.size_bytes or digest.hexdigest() != entry.sha256:
                        raise PortabilityError("Backup changed during restore staging.")
                    os.chmod(target, entry.mode)
            for entry in sorted(
                directories,
                key=lambda item: len(PurePosixPath(item.path).parts),
                reverse=True,
            ):
                os.chmod(self._stage_target(stage, entry.path), entry.mode)
            os.chmod(stage, manifest.root_mode)
        except (OSError, RuntimeError, zipfile.BadZipFile):
            self._remove_transaction_path(stage)
            raise

    def _write_journal(self, transaction_id: str, state: str) -> None:
        payload = {
            "schema_version": 1,
            "transaction_id": transaction_id,
            "state": state,
        }
        temporary = self._journal_path.with_name(f"{self._journal_path.name}.tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(payload, sort_keys=True, separators=(",", ":"))
                    + "\n"
                )
            os.chmod(temporary, 0o600)
            temporary.replace(self._journal_path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _read_journal(journal: Path) -> tuple[str, str]:
        try:
            payload = json.loads(journal.read_text(encoding="utf-8"))
            if set(payload) != {"schema_version", "transaction_id", "state"}:
                raise ValueError
            if payload["schema_version"] != 1:
                raise ValueError
            transaction_id = UUID(hex=payload["transaction_id"]).hex
            state = payload["state"]
            if state not in {"prepared", "old_moved", "committed"}:
                raise ValueError
            return transaction_id, state
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PortabilityError("Restore recovery journal is invalid.") from exc

    def _external_archive_path(self, archive_path: str | Path) -> Path:
        archive = Path(archive_path).expanduser().resolve()
        try:
            archive.relative_to(self._workspace.root)
        except ValueError:
            return archive
        raise PortabilityError("Backup archives must be stored outside the workspace.")

    def _transaction_paths(self, transaction_id: str) -> tuple[Path, Path]:
        return self._transaction_paths_for_root(self._workspace.root, transaction_id)

    @staticmethod
    def _transaction_paths_for_root(
        root: Path,
        transaction_id: str,
    ) -> tuple[Path, Path]:
        normalized = UUID(hex=transaction_id).hex
        stage = root.parent / f".{root.name}.linlin-stage-{normalized}"
        rollback = root.parent / f".{root.name}.linlin-rollback-{normalized}"
        return stage, rollback

    @staticmethod
    def _journal_for_root(root: Path) -> Path:
        return root.parent / f".{root.name}.linlin-restore.json"

    @staticmethod
    def _activate_stage(stage: Path, root: Path) -> None:
        stage.replace(root)

    @staticmethod
    def _stage_target(stage: Path, relative: str) -> Path:
        _validate_portable_relative_path(relative)
        target = (stage / Path(*PurePosixPath(relative).parts)).resolve()
        try:
            target.relative_to(stage.resolve())
        except ValueError as exc:
            raise PortabilityError("Restore member escapes the staging boundary.") from exc
        return target

    @staticmethod
    def _write_archive_member(
        archive: zipfile.ZipFile,
        name: str,
        data: bytes,
        mode: int,
    ) -> None:
        info = zipfile.ZipInfo(name, _FIXED_ZIP_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | mode) << 16
        archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    def _write_workspace_file(
        self,
        archive: zipfile.ZipFile,
        member_name: str,
        entry: BackupEntry,
    ) -> None:
        source_path = self._workspace.resolve(entry.path)
        if source_path.is_symlink() or not source_path.is_file():
            raise PortabilityError("Workspace changed during backup creation.")
        info = zipfile.ZipInfo(member_name, _FIXED_ZIP_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | entry.mode) << 16
        digest = sha256()
        size = 0
        with source_path.open("rb") as source, archive.open(info, "w") as destination:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                size += len(block)
                digest.update(block)
                destination.write(block)
        if size != entry.size_bytes or digest.hexdigest() != entry.sha256:
            raise PortabilityError("Workspace changed during backup creation.")

    @staticmethod
    def _remove_transaction_path(path: Path) -> None:
        if not path.exists() and not path.is_symlink():
            return
        if path.is_symlink() or not path.is_dir():
            raise PortabilityError("Restore transaction path is unsafe.")
        shutil.rmtree(path, onexc=_make_writable_and_retry)

    def _check_limits(self, entries: int, size_bytes: int) -> None:
        if entries > self._max_entries:
            raise PortabilityError("Backup entry limit exceeded.")
        if size_bytes > self._max_total_bytes:
            raise PortabilityError("Backup size limit exceeded.")

    @staticmethod
    def _report(
        manifest: BackupManifest,
        started: float,
        *,
        rehearsal: bool,
        recovered: bool = False,
    ) -> RecoveryReport:
        return RecoveryReport(
            files=sum(entry.kind == "file" for entry in manifest.entries),
            directories=sum(entry.kind == "directory" for entry in manifest.entries),
            size_bytes=sum(entry.size_bytes for entry in manifest.entries),
            rpo_bytes=0,
            rto_seconds=max(0.0, monotonic() - started),
            rehearsal=rehearsal,
            recovered_interrupted_transaction=recovered,
        )


def _manifest_bytes(manifest: BackupManifest) -> bytes:
    payload = manifest.model_dump(mode="json")
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{serialized}\n".encode()


def _validate_portable_relative_path(raw: str) -> None:
    if not raw or "\\" in raw or unicodedata.normalize("NFC", raw) != raw:
        raise ValueError("Backup paths must use normalized portable names.")
    path = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    if (
        path.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or path.as_posix() != raw
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("Backup paths must be safe relative paths.")
    for part in path.parts:
        if (
            part.endswith((" ", "."))
            or any(character in _INVALID_PORTABLE_CHARS for character in part)
            or any(ord(character) < 32 for character in part)
            or part.split(".", 1)[0].casefold() in _WINDOWS_RESERVED_NAMES
        ):
            raise ValueError("Backup path is not portable across supported platforms.")


def _portable_key(raw: str) -> str:
    return unicodedata.normalize("NFC", raw).casefold()


def _make_writable_and_retry(
    function: Callable[[str], object],
    path: str,
    _: object,
) -> None:
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
    function(path)
