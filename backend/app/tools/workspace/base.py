from __future__ import annotations

from abc import ABC
from pathlib import Path


class WorkspaceError(RuntimeError):
    """Raised when a workspace operation is invalid."""


class WorkspaceBase(ABC):
    """Base class for workspace tools."""

    def __init__(
        self,
        workspace: str | Path,
    ) -> None:

        self.workspace = Path(workspace).resolve()

        if not self.workspace.exists():
            raise WorkspaceError(
                f"Workspace does not exist: {self.workspace}",
            )

    def resolve(
        self,
        relative_path: str,
    ) -> Path:

        target = (self.workspace / relative_path).resolve()

        try:
            target.relative_to(self.workspace)

        except ValueError as exc:
            raise WorkspaceError(
                "Access outside workspace is not allowed.",
            ) from exc

        return target
