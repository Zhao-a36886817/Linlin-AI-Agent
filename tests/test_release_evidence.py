from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.release_evidence import (
    PLATFORMS,
    ReleaseEvidenceError,
    create_aggregate,
    create_platform_record,
    validate_release_evidence,
)

ROOT = Path(__file__).parents[1]
COMMIT = "a" * 40
VERSION = "1.0.0-rc.1"


def fake_sigstore_bundle(path: Path) -> None:
    """測試只驗 schema 綁定；真實密碼學驗證由 CI 的 GitHub CLI 執行。"""

    path.write_text(
        json.dumps(
            {
                "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
                "verificationMaterial": {"certificate": {"rawBytes": "test"}},
                "dsseEnvelope": {
                    "payload": "test",
                    "payloadType": "application/vnd.in-toto+json",
                    "signatures": [{"sig": "test"}],
                },
            }
        ),
        encoding="utf-8",
    )


def build_evidence(tmp_path: Path) -> Path:
    evidence = tmp_path / "release-evidence"
    for index, platform in enumerate(PLATFORMS, start=1):
        bundle = tmp_path / f"bundle-{platform}"
        bundle.mkdir()
        (bundle / f"linlin-agent-{platform}.bin").write_bytes(
            f"native-{platform}".encode()
        )
        (bundle / "sbom.cdx.json").write_text("{}", encoding="utf-8")
        attestation = tmp_path / f"source-{platform}.attestation.json"
        fake_sigstore_bundle(attestation)
        create_platform_record(
            root=ROOT,
            bundle=bundle,
            output=evidence / f"{platform}.json",
            attestation_bundle=attestation,
            platform=platform,
            version=VERSION,
            source_commit=COMMIT,
            repository="owner/repository",
            workflow_ref=(
                "owner/repository/.github/workflows/release.yml@refs/heads/main"
            ),
            run_id="12345",
            run_attempt=1,
            artifact_name=f"linlin-agent-{VERSION}-{platform}",
            artifact_id=str(1000 + index),
            artifact_url=f"https://github.com/owner/repository/actions/artifacts/{index}",
            attestation_id=str(2000 + index),
            attestation_url=f"https://github.com/owner/repository/attestations/{index}",
        )
    create_aggregate(evidence, source_commit=COMMIT, version=VERSION)
    return evidence


def test_three_platform_evidence_is_commit_bound_and_complete(tmp_path: Path) -> None:
    evidence = build_evidence(tmp_path)

    result = validate_release_evidence(
        evidence,
        source_commit=COMMIT,
        version=VERSION,
    )

    assert result == {"valid": True, "errors": [], "platforms": list(PLATFORMS)}


def test_wrong_source_commit_fails_closed(tmp_path: Path) -> None:
    evidence = build_evidence(tmp_path)

    result = validate_release_evidence(
        evidence,
        source_commit="b" * 40,
        version=VERSION,
    )

    assert result["valid"] is False
    assert any("identity mismatch" in error for error in result["errors"])


def test_platform_record_rejects_non_sigstore_json(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "candidate.bin").write_bytes(b"candidate")
    attestation = tmp_path / "attestation.json"
    attestation.write_text("{}", encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="signed DSSE"):
        create_platform_record(
            root=ROOT,
            bundle=bundle,
            output=tmp_path / "windows.json",
            attestation_bundle=attestation,
            platform="windows",
            version=VERSION,
            source_commit=COMMIT,
            repository="owner/repository",
            workflow_ref=(
                "owner/repository/.github/workflows/release.yml@refs/heads/main"
            ),
            run_id="1",
            run_attempt=1,
            artifact_name="candidate",
            artifact_id="2",
            artifact_url="https://github.com/owner/repository/actions/artifacts/2",
            attestation_id="3",
            attestation_url="https://github.com/owner/repository/attestations/3",
        )
