from pathlib import Path

import pytest
from pydantic import ValidationError

from app.artifacts import ArtifactError, ArtifactProvenance, ArtifactRuntime
from app.workspace import WorkspaceError, WorkspaceRuntime


@pytest.fixture
def runtime(tmp_path: Path) -> ArtifactRuntime:
    root = tmp_path / "workspace"
    root.mkdir()
    return ArtifactRuntime(WorkspaceRuntime(root), max_bytes=32)


def test_import_preserves_type_size_and_provenance(runtime: ArtifactRuntime) -> None:
    artifact = runtime.import_bytes(
        b"\x89PNG\r\n\x1a\ncontent",
        kind="image",
        content_type="image/png",
        provenance=ArtifactProvenance(source="user-upload"),
    )
    assert artifact.kind == "image"
    assert artifact.size_bytes == 15
    assert artifact.provenance.source == "user-upload"
    assert runtime.read(artifact.id).startswith(b"\x89PNG")


@pytest.mark.parametrize(
    ("data", "kind", "content_type"),
    [
        (b"", "document", "text/plain"),
        (b"x" * 33, "document", "text/plain"),
        (b"not png", "image", "image/png"),
        (b"text", "audio", "text/plain"),
        (b"text", "document", "application/octet-stream"),
    ],
)
def test_unsafe_size_type_and_signature_are_rejected(
    runtime: ArtifactRuntime, data: bytes, kind: str, content_type: str
) -> None:
    with pytest.raises(ArtifactError):
        runtime.import_bytes(
            data,
            kind=kind,  # type: ignore[arg-type]
            content_type=content_type,
            provenance=ArtifactProvenance(source="test"),
        )


def test_workspace_import_and_export_reject_path_escape(
    runtime: ArtifactRuntime,
) -> None:
    with pytest.raises(WorkspaceError):
        runtime.import_file("../secret.txt", kind="document", content_type="text/plain")
    artifact = runtime.import_bytes(
        b"safe text",
        kind="document",
        content_type="text/plain",
        provenance=ArtifactProvenance(source="test"),
    )
    with pytest.raises(WorkspaceError):
        runtime.export(artifact.id, "../export.txt")


def test_temporary_cleanup_does_not_delete_persistent_artifacts(
    runtime: ArtifactRuntime,
) -> None:
    temporary = runtime.import_bytes(
        b"temporary",
        kind="document",
        content_type="text/plain",
        provenance=ArtifactProvenance(source="test"),
    )
    persistent = runtime.import_bytes(
        b"persistent",
        kind="document",
        content_type="text/plain",
        provenance=ArtifactProvenance(source="test"),
        temporary=False,
    )
    assert runtime.cleanup(temporary.id) is True
    with pytest.raises(ArtifactError):
        runtime.get(temporary.id)
    assert runtime.cleanup(persistent.id) is False
    assert runtime.read(persistent.id) == b"persistent"


def test_local_and_consented_cloud_contracts_are_distinct(
    runtime: ArtifactRuntime,
) -> None:
    artifact = runtime.import_bytes(
        b"local",
        kind="document",
        content_type="text/plain",
        provenance=ArtifactProvenance(source="test"),
    )
    local = runtime.prepare_request("describe", [artifact.id])
    assert local.handling == "local"
    with pytest.raises(ValidationError):
        runtime.prepare_request("describe", [artifact.id], handling="cloud")
    cloud = runtime.prepare_request(
        "describe", [artifact.id], handling="cloud", cloud_consent=True
    )
    assert cloud.handling == "cloud"
    assert cloud.cloud_consent is True


def test_storage_tampering_is_detected(runtime: ArtifactRuntime) -> None:
    artifact = runtime.import_bytes(
        b"original",
        kind="document",
        content_type="text/plain",
        provenance=ArtifactProvenance(source="test"),
    )
    stored = runtime._workspace.resolve(artifact.path)
    stored.write_bytes(b"tampered")
    with pytest.raises(ArtifactError):
        runtime.read(artifact.id)
