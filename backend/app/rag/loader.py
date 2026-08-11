from __future__ import annotations

from dataclasses import dataclass

from app.workspace import WorkspaceRuntime


class RagDocumentError(RuntimeError):
    pass


@dataclass(frozen=True)
class RagDocument:
    source: str
    text: str


class WorkspaceTextLoader:
    def __init__(self, workspace: WorkspaceRuntime, max_bytes: int = 1_000_000) -> None:
        self._workspace = workspace
        self._max_bytes = max_bytes

    def load(self, relative_path: str) -> RagDocument:
        path = self._workspace.resolve(relative_path)
        if not path.is_file():
            raise RagDocumentError("RAG source must be a workspace file.")
        data = path.read_bytes()
        if len(data) > self._max_bytes:
            raise RagDocumentError("RAG source exceeds the configured size limit.")
        if b"\x00" in data:
            raise RagDocumentError("Binary RAG sources are not supported.")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RagDocumentError("RAG source must be UTF-8 text.") from exc
        return RagDocument(source=path.relative_to(self._workspace.root).as_posix(), text=text)
