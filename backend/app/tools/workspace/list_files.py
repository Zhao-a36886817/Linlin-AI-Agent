from __future__ import annotations

from pathlib import Path
from typing import Any

from app.tools.base import BaseTool
from app.tools.workspace.base import WorkspaceBase, WorkspaceError


class ListFilesTool(WorkspaceBase, BaseTool):
    """List files and directories inside the configured workspace."""

    name = "list_files"
    description = (
        "List files and directories inside the workspace. "
        "Access outside the workspace is not allowed."
    )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Relative directory path inside the workspace. "
                        "Use '.' for the workspace root."
                    ),
                    "default": ".",
                },
                "recursive": {
                    "type": "boolean",
                    "description": (
                        "Whether to recursively list nested files and directories."
                    ),
                    "default": False,
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Whether to include hidden files and directories.",
                    "default": False,
                },
                "max_entries": {
                    "type": "integer",
                    "description": "Maximum number of entries to return.",
                    "minimum": 1,
                    "maximum": 5000,
                    "default": 500,
                },
            },
            "additionalProperties": False,
        }

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise TypeError("Tool arguments must be an object.")

        relative_path = arguments.get("path", ".")
        recursive = arguments.get("recursive", False)
        include_hidden = arguments.get("include_hidden", False)
        max_entries = arguments.get("max_entries", 500)

        if not isinstance(relative_path, str):
            raise TypeError("path must be a string.")

        if not isinstance(recursive, bool):
            raise TypeError("recursive must be a boolean.")

        if not isinstance(include_hidden, bool):
            raise TypeError("include_hidden must be a boolean.")

        if isinstance(max_entries, bool) or not isinstance(max_entries, int):
            raise TypeError("max_entries must be an integer.")

        if not 1 <= max_entries <= 5000:
            raise ValueError("max_entries must be between 1 and 5000.")

        target = self.resolve(relative_path)

        if not target.exists():
            raise WorkspaceError(
                f"Path does not exist: {relative_path}",
            )

        if not target.is_dir():
            raise WorkspaceError(
                f"Path is not a directory: {relative_path}",
            )

        entries = target.rglob("*") if recursive else target.iterdir()

        results: list[dict[str, Any]] = []

        for entry in sorted(
            entries,
            key=lambda item: (
                not item.is_dir(),
                str(item.relative_to(self.workspace)).lower(),
            ),
        ):
            relative = entry.relative_to(self.workspace)

            if not include_hidden and self._is_hidden(relative):
                continue

            results.append(
                {
                    "path": relative.as_posix(),
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": (None if entry.is_dir() else self._safe_file_size(entry)),
                },
            )

            if len(results) >= max_entries:
                break

        return {
            "tool": self.name,
            "ok": True,
            "path": target.relative_to(self.workspace).as_posix() or ".",
            "recursive": recursive,
            "include_hidden": include_hidden,
            "count": len(results),
            "truncated": len(results) >= max_entries,
            "entries": results,
        }

    @staticmethod
    def _is_hidden(path: Path) -> bool:
        return any(
            part.startswith(".") for part in path.parts if part not in {".", ".."}
        )

    @staticmethod
    def _safe_file_size(path: Path) -> int | None:
        try:
            return path.stat().st_size
        except OSError:
            return None
