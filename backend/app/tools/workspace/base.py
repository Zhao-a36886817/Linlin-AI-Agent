from __future__ import annotations

from abc import ABC
from pathlib import Path

from app.workspace import WorkspaceError, WorkspaceRuntime

__all__ = ["WorkspaceBase", "WorkspaceError"]


class WorkspaceBase(ABC):
    """Base class for workspace tools."""

    def __init__(
        self,
        workspace: str | Path,
    ) -> None:

        self.runtime = WorkspaceRuntime(workspace)
        self.workspace = self.runtime.root

    def resolve(
        self,
        relative_path: str,
    ) -> Path:

        return self.runtime.resolve(relative_path)
