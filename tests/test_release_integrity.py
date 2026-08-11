from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.release_integrity import (
    ReleaseIntegrityError,
    build_manifest,
    canonical_manifest,
    verify_signed_package,
)


def package(tmp_path: Path) -> Path:
    root = tmp_path / "package"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "linlin").write_bytes(b"desktop-binary")
    (root / "NOTICE.txt").write_text("notice", encoding="utf-8")
    return root


def signed(root: Path) -> tuple[dict[str, object], bytes, bytes]:
    manifest = build_manifest(
        root, version="1.2.3", platform="windows-x86_64", rollback_version="1.2.2"
    )
    private = Ed25519PrivateKey.generate()
    signature = private.sign(canonical_manifest(manifest))
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return manifest, signature, public


def test_manifest_is_reproducible_and_sorted(tmp_path: Path) -> None:
    root = package(tmp_path)
    first = build_manifest(root, version="1.2.3", platform="windows-x86_64")
    second = build_manifest(root, version="1.2.3", platform="windows-x86_64")
    assert canonical_manifest(first) == canonical_manifest(second)
    assert [item["path"] for item in first["files"]] == ["NOTICE.txt", "bin/linlin"]


def test_valid_signed_package_and_rollback_metadata_verify(tmp_path: Path) -> None:
    root = package(tmp_path)
    manifest, signature, public = signed(root)
    verify_signed_package(root, manifest, signature=signature, public_key=public)
    assert manifest["rollback_version"] == "1.2.2"


def test_tampered_signature_is_rejected(tmp_path: Path) -> None:
    root = package(tmp_path)
    manifest, signature, public = signed(root)
    with pytest.raises(ReleaseIntegrityError, match="signature"):
        verify_signed_package(root, manifest, signature=signature[:-1] + b"x", public_key=public)


def test_tampered_or_extra_package_content_is_rejected(tmp_path: Path) -> None:
    root = package(tmp_path)
    manifest, signature, public = signed(root)
    (root / "bin" / "linlin").write_bytes(b"tampered-binary")
    with pytest.raises(ReleaseIntegrityError, match="content"):
        verify_signed_package(root, manifest, signature=signature, public_key=public)


def test_symlink_package_entry_is_rejected(tmp_path: Path) -> None:
    root = package(tmp_path)
    link = root / "linked"
    try:
        link.symlink_to(root / "NOTICE.txt")
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform/account.")
    with pytest.raises(ReleaseIntegrityError, match="symbolic"):
        build_manifest(root, version="1.2.3", platform="test")
