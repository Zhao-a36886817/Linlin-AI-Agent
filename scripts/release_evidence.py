from __future__ import annotations

"""產生及驗證 P24 三平台原生成品證據。

平台紀錄必須由同一個 GitHub Actions run 建立，並綁定完整 source commit、版本、
artifact ID、逐檔 SHA-256，以及 Sigstore 公益服務產生的簽章 bundle。為了讓私人
個人倉庫也能免費蒐證，CI 會簽署「逐檔雜湊清單」，再由官方 Sigstore action 依
GitHub OIDC workflow 身分立即驗證；本模組則負責確認清單、成品與證據彼此一致。
"""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

import tomllib

PLATFORMS = ("windows", "linux", "macos")
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
RC_VERSION = re.compile(r"1\.0\.0-rc\.\d+")
SIGSTORE_OIDC_ISSUER = "https://token.actions.githubusercontent.com"


class ReleaseEvidenceError(RuntimeError):
    """代表證據缺漏、不一致或無法安全驗證。"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def source_version(root: Path) -> str:
    """讀取五個正式版本來源；任一分歧都禁止產生成品證據。"""

    root = root.resolve()
    values = {
        str(
            tomllib.loads(
                (root / "backend/pyproject.toml").read_text(encoding="utf-8")
            )["project"]["version"]
        ),
        str(
            json.loads((root / "frontend/package.json").read_text(encoding="utf-8"))[
                "version"
            ]
        ),
        str(
            json.loads((root / "desktop/package.json").read_text(encoding="utf-8"))[
                "version"
            ]
        ),
        str(
            tomllib.loads(
                (root / "desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8")
            )["package"]["version"]
        ),
        str(
            json.loads(
                (root / "desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
            )["version"]
        ),
    }
    if len(values) != 1:
        raise ReleaseEvidenceError("Release version sources are inconsistent.")
    version = values.pop()
    if not RC_VERSION.fullmatch(version):
        raise ReleaseEvidenceError("Source version is not an approved RC format.")
    return version


def bundle_files(bundle: Path) -> list[dict[str, Any]]:
    """列出實際可下載 bundle 內所有普通檔案，拒絕 symlink 與空成品。"""

    bundle = bundle.resolve()
    if not bundle.is_dir():
        raise ReleaseEvidenceError("Native bundle directory is missing.")
    files: list[dict[str, Any]] = []
    for path in sorted(bundle.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ReleaseEvidenceError("Native bundle cannot contain symbolic links.")
        if path.is_file():
            files.append(
                {
                    "path": path.relative_to(bundle).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    if not files:
        raise ReleaseEvidenceError("Native bundle is empty.")
    return files


def checksum_manifest(files: list[dict[str, Any]]) -> str:
    """輸出可被 Sigstore 簽署、且跨三種 runner 都一致的 SHA-256 清單。"""

    return "".join(f"{item['sha256']}  {item['path']}\n" for item in files)


def create_checksum_manifest(bundle: Path, output: Path) -> None:
    """在簽章前由實際原生成品產生 subject；不接受人工提供的雜湊值。"""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        checksum_manifest(bundle_files(bundle)), encoding="utf-8", newline="\n"
    )


def _sigstore_bundle(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseEvidenceError("Sigstore bundle is unreadable.") from error
    required = {"mediaType", "verificationMaterial"}
    signed_content = {"dsseEnvelope", "messageSignature"}
    if (
        not isinstance(document, dict)
        or not required <= set(document)
        or not signed_content.intersection(document)
    ):
        raise ReleaseEvidenceError("Sigstore bundle has no signed material.")
    return document


def create_platform_record(
    *,
    root: Path,
    bundle: Path,
    output: Path,
    attestation_bundle: Path,
    signed_subject: Path,
    platform: str,
    version: str,
    source_commit: str,
    repository: str,
    workflow_ref: str,
    run_id: str,
    run_attempt: int,
    artifact_name: str,
    artifact_id: str,
    artifact_url: str,
) -> dict[str, Any]:
    """在官方 Sigstore action 驗證完成後，建立單一平台證據紀錄。"""

    if platform not in PLATFORMS or not COMMIT.fullmatch(source_commit):
        raise ReleaseEvidenceError("Invalid platform or source commit.")
    if version != source_version(root):
        raise ReleaseEvidenceError("Workflow input version does not match source.")
    if not re.fullmatch(r"[^/\s]+/[^/\s]+", repository):
        raise ReleaseEvidenceError("Invalid GitHub repository identity.")
    if ".github/workflows/release.yml@" not in workflow_ref:
        raise ReleaseEvidenceError("Evidence is not from the release workflow.")
    if not run_id.isdigit() or run_attempt < 1 or not artifact_id.isdigit():
        raise ReleaseEvidenceError("Invalid workflow or artifact identity.")
    _sigstore_bundle(attestation_bundle)

    files = bundle_files(bundle)
    try:
        subject_text = signed_subject.read_text(encoding="utf-8")
    except OSError as error:
        raise ReleaseEvidenceError("Signed checksum subject is unreadable.") from error
    if subject_text != checksum_manifest(files):
        raise ReleaseEvidenceError(
            "Signed checksum subject does not match native bundle."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    copied_subject = output.with_name(f"{platform}.subjects.sha256")
    if signed_subject.resolve() != copied_subject.resolve():
        shutil.copyfile(signed_subject, copied_subject)
    copied_attestation = output.with_name(f"{platform}.attestation.sigstore.json")
    shutil.copyfile(attestation_bundle, copied_attestation)
    cert_identity = f"https://github.com/{workflow_ref}"
    record = {
        "schema_version": 1,
        "evidence_type": "native-artifact",
        "platform": platform,
        "version": version,
        "source_commit": source_commit,
        "repository": repository,
        "workflow": {
            "ref": workflow_ref,
            "run_id": run_id,
            "run_attempt": run_attempt,
        },
        "artifact": {
            "name": artifact_name,
            "id": artifact_id,
            "url": artifact_url,
        },
        "bundle_files": files,
        "attestation": {
            "provider": "sigstore-public-good",
            "certificate_identity": cert_identity,
            "oidc_issuer": SIGSTORE_OIDC_ISSUER,
            "signed_subject_path": copied_subject.name,
            "signed_subject_sha256": sha256_file(copied_subject),
            "bundle_path": copied_attestation.name,
            "bundle_sha256": sha256_file(copied_attestation),
            "verification": "sigstore-action-identity-verify-passed",
            "transparency_log": "rekor-public-good",
        },
    }
    output.write_text(canonical_json(record), encoding="utf-8", newline="\n")
    return record


def validate_release_evidence(
    evidence_dir: Path,
    *,
    source_commit: str,
    version: str,
) -> dict[str, Any]:
    """驗證三平台紀錄、聚合 provenance 與 signing index 的相互綁定。"""

    errors: list[str] = []
    records: dict[str, dict[str, Any]] = {}
    for platform in PLATFORMS:
        path = evidence_dir / f"{platform}.json"
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            _validate_platform_record(
                evidence_dir, record, platform, source_commit, version
            )
            records[platform] = record
        except (OSError, json.JSONDecodeError, ReleaseEvidenceError) as error:
            errors.append(f"{platform}:{error}")
    for name in ("provenance.json", "signing-attestation.json"):
        if not (evidence_dir / name).is_file():
            errors.append(f"missing:{name}")
    if len(records) == len(PLATFORMS) and not errors:
        errors.extend(
            _validate_aggregate(evidence_dir, records, source_commit, version)
        )
    return {
        "valid": not errors,
        "errors": errors,
        "platforms": [platform for platform in PLATFORMS if platform in records],
    }


def _validate_platform_record(
    evidence_dir: Path,
    record: dict[str, Any],
    platform: str,
    commit: str,
    version: str,
) -> None:
    if not isinstance(record, dict):
        raise ReleaseEvidenceError("record is not an object")
    if (
        record.get("schema_version") != 1
        or record.get("evidence_type") != "native-artifact"
        or record.get("platform") != platform
        or record.get("source_commit") != commit
        or record.get("version") != version
    ):
        raise ReleaseEvidenceError("identity mismatch")
    workflow = record.get("workflow", {})
    artifact = record.get("artifact", {})
    repository = str(record.get("repository", ""))
    if not re.fullmatch(r"[^/\s]+/[^/\s]+", repository):
        raise ReleaseEvidenceError("repository identity missing")
    if ".github/workflows/release.yml@" not in str(workflow.get("ref", "")):
        raise ReleaseEvidenceError("release workflow identity missing")
    if (
        not str(workflow.get("run_id", "")).isdigit()
        or not isinstance(workflow.get("run_attempt"), int)
        or workflow["run_attempt"] < 1
        or not str(artifact.get("id", "")).isdigit()
    ):
        raise ReleaseEvidenceError("workflow/artifact identity missing")
    if not str(artifact.get("url", "")).startswith(
        f"https://github.com/{repository}/actions/"
    ):
        raise ReleaseEvidenceError("artifact URL identity mismatch")
    files = record.get("bundle_files")
    if not isinstance(files, list) or not files:
        raise ReleaseEvidenceError("bundle file list missing")
    seen: set[str] = set()
    for item in files:
        path = str(item.get("path", ""))
        if path in seen or not path or ".." in PurePosixPath(path).parts:
            raise ReleaseEvidenceError("unsafe/duplicate bundle path")
        if not isinstance(item.get("size"), int) or item["size"] < 0:
            raise ReleaseEvidenceError("invalid bundle size")
        if not SHA256.fullmatch(str(item.get("sha256", ""))):
            raise ReleaseEvidenceError("invalid bundle digest")
        seen.add(path)
    attestation = record.get("attestation", {})
    expected_identity = f"https://github.com/{workflow.get('ref', '')}"
    if (
        attestation.get("provider") != "sigstore-public-good"
        or attestation.get("verification") != "sigstore-action-identity-verify-passed"
        or attestation.get("certificate_identity") != expected_identity
        or attestation.get("oidc_issuer") != SIGSTORE_OIDC_ISSUER
        or attestation.get("transparency_log") != "rekor-public-good"
    ):
        raise ReleaseEvidenceError("attestation was not verified")
    subject_path = evidence_dir / str(attestation.get("signed_subject_path", ""))
    if not subject_path.is_file():
        raise ReleaseEvidenceError("signed checksum subject missing")
    if sha256_file(subject_path) != attestation.get("signed_subject_sha256"):
        raise ReleaseEvidenceError("signed checksum subject digest mismatch")
    if subject_path.read_text(encoding="utf-8") != checksum_manifest(files):
        raise ReleaseEvidenceError("signed checksum subject content mismatch")
    bundle_path = evidence_dir / str(attestation.get("bundle_path", ""))
    _sigstore_bundle(bundle_path)
    if sha256_file(bundle_path) != attestation.get("bundle_sha256"):
        raise ReleaseEvidenceError("attestation bundle digest mismatch")


def create_aggregate(
    evidence_dir: Path,
    *,
    source_commit: str,
    version: str,
) -> None:
    """三個 matrix job 完成後，建立 commit-bound provenance 與簽章索引。"""

    records = {
        platform: json.loads(
            (evidence_dir / f"{platform}.json").read_text(encoding="utf-8")
        )
        for platform in PLATFORMS
    }
    for platform, record in records.items():
        _validate_platform_record(
            evidence_dir, record, platform, source_commit, version
        )
    identities = {
        (
            record["repository"],
            record["workflow"]["ref"],
            record["workflow"]["run_id"],
            record["workflow"]["run_attempt"],
        )
        for record in records.values()
    }
    if len(identities) != 1:
        raise ReleaseEvidenceError("Platform records are not from one workflow run.")
    repository, workflow_ref, run_id, run_attempt = identities.pop()
    subjects = [
        {
            "name": f"{platform}/{item['path']}",
            "digest": {"sha256": item["sha256"]},
        }
        for platform, record in records.items()
        for item in record["bundle_files"]
    ]
    provenance = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": sorted(subjects, key=lambda item: item["name"]),
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://github.com/linlin-agent/release/v1",
                "externalParameters": {
                    "sourceCommit": source_commit,
                    "version": version,
                    "workflowRef": workflow_ref,
                },
            },
            "runDetails": {
                "builder": {"id": "https://github.com/actions/runner/github-hosted"},
                "metadata": {"runId": run_id, "runAttempt": run_attempt},
            },
        },
    }
    signing = {
        "schema_version": 1,
        "evidence_type": "sigstore-attestation-index",
        "source_commit": source_commit,
        "version": version,
        "repository": repository,
        "workflow_ref": workflow_ref,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "attestations": [
            {"platform": platform, **record["attestation"]}
            for platform, record in records.items()
        ],
    }
    (evidence_dir / "provenance.json").write_text(
        canonical_json(provenance), encoding="utf-8", newline="\n"
    )
    (evidence_dir / "signing-attestation.json").write_text(
        canonical_json(signing), encoding="utf-8", newline="\n"
    )


def _validate_aggregate(
    evidence_dir: Path,
    records: dict[str, dict[str, Any]],
    commit: str,
    version: str,
) -> list[str]:
    try:
        expected_dir = evidence_dir / "_expected"
        expected_dir.mkdir(exist_ok=True)
        # 使用同一產生器重建，再以 canonical JSON 比對；暫存目錄由 caller 放在
        # ignored release-evidence 內，不影響 immutable source 工作樹。
        for platform, record in records.items():
            (expected_dir / f"{platform}.json").write_text(
                canonical_json(record), encoding="utf-8"
            )
            signed_subject = evidence_dir / record["attestation"]["signed_subject_path"]
            shutil.copyfile(signed_subject, expected_dir / signed_subject.name)
            source = evidence_dir / record["attestation"]["bundle_path"]
            shutil.copyfile(source, expected_dir / source.name)
        create_aggregate(expected_dir, source_commit=commit, version=version)
        errors = []
        for name in ("provenance.json", "signing-attestation.json"):
            actual = json.loads((evidence_dir / name).read_text(encoding="utf-8"))
            expected = json.loads((expected_dir / name).read_text(encoding="utf-8"))
            if actual != expected:
                errors.append(f"aggregate-mismatch:{name}")
        shutil.rmtree(expected_dir)
        return errors
    except (OSError, json.JSONDecodeError, ReleaseEvidenceError) as error:
        return [f"aggregate:{error}"]


def main() -> int:
    parser = argparse.ArgumentParser(description="建立或驗證三平台 RC 證據")
    subparsers = parser.add_subparsers(dest="command", required=True)
    checksums = subparsers.add_parser("checksums")
    checksums.add_argument("--bundle", type=Path, required=True)
    checksums.add_argument("--output", type=Path, required=True)
    platform = subparsers.add_parser("platform")
    for command in (platform,):
        command.add_argument("--root", type=Path, default=Path.cwd())
        command.add_argument("--bundle", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--attestation-bundle", type=Path, required=True)
        command.add_argument("--signed-subject", type=Path, required=True)
        command.add_argument("--platform", choices=PLATFORMS, required=True)
        command.add_argument("--version", required=True)
        command.add_argument("--source-commit", required=True)
        command.add_argument("--repository", required=True)
        command.add_argument("--workflow-ref", required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--run-attempt", type=int, required=True)
        command.add_argument("--artifact-name", required=True)
        command.add_argument("--artifact-id", required=True)
        command.add_argument("--artifact-url", required=True)
    aggregate = subparsers.add_parser("aggregate")
    aggregate.add_argument("--evidence-dir", type=Path, required=True)
    aggregate.add_argument("--source-commit", required=True)
    aggregate.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        if args.command == "checksums":
            create_checksum_manifest(args.bundle, args.output)
        elif args.command == "platform":
            platform_arguments = vars(args).copy()
            platform_arguments.pop("command")
            create_platform_record(**platform_arguments)
        else:
            create_aggregate(
                args.evidence_dir,
                source_commit=args.source_commit,
                version=args.version,
            )
    except ReleaseEvidenceError as error:
        print(f"Release evidence failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
