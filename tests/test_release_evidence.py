from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.release_evidence import (
    PLATFORMS,
    ReleaseEvidenceError,
    create_aggregate,
    create_checksum_manifest,
    create_platform_record,
    stage_native_bundle,
    validate_release_evidence,
)

ROOT = Path(__file__).parents[1]
COMMIT = "a" * 40
VERSION = "1.0.0-rc.1"


def fake_sigstore_bundle(path: Path) -> None:
    """測試只驗 schema 綁定；真實密碼學驗證由官方 Sigstore action 執行。"""

    path.write_text(
        json.dumps(
            {
                "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
                "verificationMaterial": {"certificate": {"rawBytes": "test"}},
                "messageSignature": {
                    "messageDigest": {"algorithm": "SHA2_256", "digest": "test"},
                    "signature": "test",
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
        signed_subject = tmp_path / f"source-{platform}.subjects.sha256"
        create_checksum_manifest(bundle, signed_subject)
        create_platform_record(
            root=ROOT,
            bundle=bundle,
            output=evidence / f"{platform}.json",
            attestation_bundle=attestation,
            signed_subject=signed_subject,
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
    signed_subject = tmp_path / "subjects.sha256"
    create_checksum_manifest(bundle, signed_subject)

    with pytest.raises(ReleaseEvidenceError, match="signed material"):
        create_platform_record(
            root=ROOT,
            bundle=bundle,
            output=tmp_path / "windows.json",
            attestation_bundle=attestation,
            signed_subject=signed_subject,
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
        )


def test_platform_record_rejects_checksum_subject_for_other_bundle(
    tmp_path: Path,
) -> None:
    """即使 Sigstore bundle 看似有效，也不能接受簽到另一批檔案的雜湊清單。"""

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "candidate.bin").write_bytes(b"candidate")
    signed_subject = tmp_path / "subjects.sha256"
    signed_subject.write_text(f"{'0' * 64}  candidate.bin\n", encoding="utf-8")
    attestation = tmp_path / "attestation.json"
    fake_sigstore_bundle(attestation)

    with pytest.raises(ReleaseEvidenceError, match="does not match native bundle"):
        create_platform_record(
            root=ROOT,
            bundle=bundle,
            output=tmp_path / "windows.json",
            attestation_bundle=attestation,
            signed_subject=signed_subject,
            platform="windows",
            version=VERSION,
            source_commit=COMMIT,
            repository="owner/repository",
            workflow_ref="owner/repository/.github/workflows/release.yml@refs/heads/main",
            run_id="1",
            run_attempt=1,
            artifact_name="candidate",
            artifact_id="2",
            artifact_url="https://github.com/owner/repository/actions/artifacts/2",
        )


def test_native_staging_copies_only_final_installers_and_sbom(tmp_path: Path) -> None:
    """Linux 暫存樹可含 symlink，但可簽署候選目錄必須完全沒有連結。"""

    source = tmp_path / "tauri-bundle"
    (source / "deb").mkdir(parents=True)
    (source / "appimage").mkdir()
    (source / "appimage" / "candidate.AppImage").write_bytes(b"appimage")
    (source / "deb" / "candidate.deb").write_bytes(b"deb")
    (source / "sbom.cdx.json").write_text("{}", encoding="utf-8")
    (source / "appimage" / "temporary.txt").write_text("skip", encoding="utf-8")
    temporary_link = source / "appimage" / "AppRun"
    try:
        temporary_link.symlink_to(source / "appimage" / "temporary.txt")
    except OSError:
        # 一般 Windows 測試帳號可能沒有建立 symlink 的權限；函式本身仍由
        # bundle_files 的 fail-closed 測試與 Linux CI 路徑共同覆蓋。
        temporary_link = None

    staged = tmp_path / "release-staging" / "linux"
    files = stage_native_bundle(source, staged, "linux")

    assert {item["path"] for item in files} == {
        "appimage/candidate.AppImage",
        "deb/candidate.deb",
        "sbom.cdx.json",
    }
    assert not (staged / "appimage" / "temporary.txt").exists()
    if temporary_link is not None:
        assert not (staged / "appimage" / "AppRun").exists()


def test_native_staging_requires_every_platform_format(tmp_path: Path) -> None:
    """Linux matrix 宣告 DEB + AppImage 時，缺任一格式都必須停止蒐證。"""

    source = tmp_path / "tauri-bundle"
    source.mkdir()
    (source / "candidate.deb").write_bytes(b"deb")
    (source / "sbom.cdx.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match=".appimage"):
        stage_native_bundle(source, tmp_path / "release-staging", "linux")
