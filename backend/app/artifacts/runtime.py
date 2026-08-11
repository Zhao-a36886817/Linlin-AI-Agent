from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from app.artifacts.models import (
    Artifact,
    ArtifactKind,
    ArtifactProvenance,
    MultimodalRequest,
)
from app.workspace import WorkspaceRuntime

_TYPES: dict[str, tuple[ArtifactKind, str]] = {
    "image/png": ("image", ".png"),
    "image/jpeg": ("image", ".jpg"),
    "audio/wav": ("audio", ".wav"),
    "audio/mpeg": ("audio", ".mp3"),
    "application/pdf": ("document", ".pdf"),
    "text/plain": ("document", ".txt"),
}


class ArtifactError(RuntimeError):
    pass


class ArtifactRuntime:
    """Stores bounded artifact bytes only through a Workspace Runtime root."""

    def __init__(self, workspace: WorkspaceRuntime, *, max_bytes: int = 10_000_000) -> None:
        if max_bytes < 1:
            raise ValueError("Artifact size limit must be positive.")
        self._workspace = workspace
        self._max_bytes = max_bytes
        self._artifacts: dict[UUID, Artifact] = {}

    def import_bytes(
        self,
        data: bytes,
        *,
        kind: ArtifactKind,
        content_type: str,
        provenance: ArtifactProvenance,
        temporary: bool = True,
    ) -> Artifact:
        suffix = self._validate(data, kind, content_type)
        artifact_id = uuid4()
        relative = f".linlin/artifacts/{artifact_id}{suffix}"
        target = self._workspace.resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
        artifact = Artifact(
            id=artifact_id,
            path=relative,
            kind=kind,
            content_type=content_type,
            size_bytes=len(data),
            sha256=sha256(data).hexdigest(),
            temporary=temporary,
            provenance=provenance,
        )
        self._artifacts[artifact.id] = artifact
        return artifact

    def import_file(
        self,
        source: str | Path,
        *,
        kind: ArtifactKind,
        content_type: str,
        temporary: bool = True,
    ) -> Artifact:
        source_path = self._workspace.resolve(source)
        if not source_path.is_file():
            raise ArtifactError("Artifact source must be a workspace file.")
        with source_path.open("rb") as stream:
            data = stream.read(self._max_bytes + 1)
        return self.import_bytes(
            data,
            kind=kind,
            content_type=content_type,
            provenance=ArtifactProvenance(source=str(source).replace("\\", "/")),
            temporary=temporary,
        )

    def get(self, artifact_id: UUID) -> Artifact:
        try:
            return self._artifacts[artifact_id]
        except KeyError as exc:
            raise ArtifactError("Unknown artifact.") from exc

    def read(self, artifact_id: UUID) -> bytes:
        artifact = self.get(artifact_id)
        target = self._workspace.resolve(artifact.path)
        if not target.is_file() or target.stat().st_size != artifact.size_bytes:
            raise ArtifactError("Artifact storage no longer matches its metadata.")
        data = target.read_bytes()
        if sha256(data).hexdigest() != artifact.sha256:
            raise ArtifactError("Artifact content integrity check failed.")
        return data

    def export(self, artifact_id: UUID, destination: str | Path) -> Path:
        data = self.read(artifact_id)
        target = self._workspace.resolve(destination)
        if target.exists():
            raise ArtifactError("Artifact export target already exists.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
        return target

    def cleanup(self, artifact_id: UUID) -> bool:
        artifact = self.get(artifact_id)
        if not artifact.temporary:
            return False
        target = self._workspace.resolve(artifact.path)
        if target.exists():
            target.unlink()
        del self._artifacts[artifact_id]
        return True

    def prepare_request(
        self,
        prompt: str,
        artifact_ids: list[UUID],
        *,
        handling: str = "local",
        cloud_consent: bool = False,
    ) -> MultimodalRequest:
        return MultimodalRequest(
            prompt=prompt,
            artifacts=tuple(self.get(item) for item in artifact_ids),
            handling=handling,
            cloud_consent=cloud_consent,
        )

    def _validate(
        self, data: bytes, kind: ArtifactKind, content_type: str
    ) -> str:
        if not data or len(data) > self._max_bytes:
            raise ArtifactError("Artifact is empty or exceeds the size limit.")
        declared = _TYPES.get(content_type)
        if declared is None or declared[0] != kind:
            raise ArtifactError("Artifact kind or content type is not approved.")
        if not self._matches_signature(data, content_type):
            raise ArtifactError("Artifact bytes do not match the declared content type.")
        return declared[1]

    @staticmethod
    def _matches_signature(data: bytes, content_type: str) -> bool:
        if content_type == "image/png":
            return data.startswith(b"\x89PNG\r\n\x1a\n")
        if content_type == "image/jpeg":
            return data.startswith(b"\xff\xd8\xff")
        if content_type == "audio/wav":
            return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE"
        if content_type == "audio/mpeg":
            return data.startswith(b"ID3") or data[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}
        if content_type == "application/pdf":
            return data.startswith(b"%PDF-")
        if content_type == "text/plain":
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                return False
            return True
        return False
