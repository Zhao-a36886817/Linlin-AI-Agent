from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class ReleaseIntegrityError(RuntimeError):
    pass


def build_manifest(
    package_root: Path,
    *,
    version: str,
    platform: str,
    rollback_version: str | None = None,
) -> dict[str, Any]:
    root = package_root.resolve()
    if not root.is_dir():
        raise ReleaseIntegrityError("Package root does not exist.")
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ReleaseIntegrityError("Package manifests do not accept symbolic links.")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        files.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    if not files:
        raise ReleaseIntegrityError("Package must contain at least one file.")
    return {
        "schema": 1,
        "version": version,
        "platform": platform,
        "rollback_version": rollback_version,
        "files": files,
    }


def canonical_manifest(manifest: dict[str, Any]) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_signed_package(
    package_root: Path,
    manifest: dict[str, Any],
    *,
    signature: bytes,
    public_key: bytes,
) -> None:
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, canonical_manifest(manifest)
        )
    except (ValueError, InvalidSignature) as exc:
        raise ReleaseIntegrityError("Release metadata signature is invalid.") from exc

    rebuilt = build_manifest(
        package_root,
        version=str(manifest.get("version", "")),
        platform=str(manifest.get("platform", "")),
        rollback_version=manifest.get("rollback_version"),
    )
    if rebuilt != manifest:
        raise ReleaseIntegrityError("Package content does not match signed metadata.")
