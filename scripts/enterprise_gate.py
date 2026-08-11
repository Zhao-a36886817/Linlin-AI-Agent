from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import tomllib
import yaml

if __package__:
    from scripts.governance_manifest import ManifestError, release_source_paths
    from scripts.supply_chain import scan_secrets
else:
    from governance_manifest import ManifestError, release_source_paths
    from supply_chain import scan_secrets

PHASES = tuple(f"P{number}" for number in range(24))
PASS_MARKER = "Overall checks: **PASS**"
RC_VERSION = re.compile(r"^1\.0\.0-rc\.\d+$")
APPROVAL_RECORD_FIELDS = {
    "schema_version",
    "record_type",
    "phase",
    "decision",
    "reviewer",
    "reviewer_approved",
    "owner",
    "owner_approved",
    "review_package",
    "review_package_sha256",
    "source_transcript",
    "source_transcript_sha256",
    "origin_transcript_sha256",
    "review_evidence_line",
    "owner_authorization_line",
    "original_review_evidence_line",
    "original_owner_authorization_line",
    "ledger_created_on",
    "limitations",
}
# 階段完成報告、審查包與決策證據統一依 P 編號分層，避免專案根目錄在每次
# 迭代後持續累積數十個檔案。所有 Gate 稽核都透過下方 helper 解析相同結構。
PHASE_ARTIFACTS_DIR = Path("docs/governance/phase-artifacts")


@dataclass(frozen=True, slots=True)
class Finding:
    id: str
    severity: str
    title: str
    evidence: str
    owner: str
    resolution: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def phase_artifact_relative(phase: str, filename: str) -> str:
    """Return one phase artifact path in repository-relative POSIX form."""

    return (PHASE_ARTIFACTS_DIR / phase / filename).as_posix()


def phase_artifact_path(root: Path, phase: str, filename: str) -> Path:
    """Resolve one phase artifact without depending on the process working directory."""

    return root / phase_artifact_relative(phase, filename)


def evidence_index(root: Path) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for phase in PHASES:
        for kind, relative in (
            ("phase-template", f".laes/phases/{phase}.yaml"),
            ("phase-spec", f"docs/development/{phase}.md"),
            (
                "supervisor-package",
                phase_artifact_relative(
                    phase,
                    f"{phase}_SUPERVISOR_REVIEW_PACKAGE.md",
                ),
            ),
            (
                "completion-report",
                phase_artifact_relative(phase, f"{phase}_COMPLETION_REPORT.md"),
            ),
        ):
            path = root / relative
            evidence.append(
                {
                    "phase": phase,
                    "kind": kind,
                    "path": relative,
                    "present": path.is_file(),
                    "sha256": sha256_file(path) if path.is_file() else None,
                }
            )
    return evidence


def manifest_integrity(root: Path) -> dict[str, Any]:
    manifest = root / "MANIFEST.sha256"
    matched: list[str] = []
    missing: list[str] = []
    mismatched: list[str] = []
    invalid: list[str] = []
    unlisted: list[str] = []
    discovery_error: str | None = None
    if not manifest.is_file():
        return {
            "present": False,
            "matched": matched,
            "missing": missing,
            "mismatched": mismatched,
            "invalid": invalid,
            "unlisted": unlisted,
            "discovery_error": discovery_error,
        }
    listed: set[str] = set()
    for line_number, line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        try:
            expected, relative = line.split("  ", 1)
        except ValueError:
            invalid.append(str(line_number))
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            invalid.append(str(line_number))
            continue
        if relative in listed or Path(relative).is_absolute() or ".." in Path(relative).parts:
            invalid.append(str(line_number))
            continue
        listed.add(relative)
        target = root / relative
        if not target.is_file():
            missing.append(relative)
        elif sha256_file(target) != expected:
            mismatched.append(relative)
        else:
            matched.append(relative)
    try:
        expected_paths = {
            path.as_posix() for path in release_source_paths(root)
        }
        unlisted = sorted(expected_paths - listed)
    except ManifestError as error:
        # Git 盤點失敗時 fail closed；只記錄錯誤類型文字，不輸出檔案內容或秘密。
        discovery_error = str(error)
    return {
        "present": True,
        "matched": matched,
        "missing": missing,
        "mismatched": mismatched,
        "invalid": invalid,
        "unlisted": unlisted,
        "discovery_error": discovery_error,
    }


def version_inventory(root: Path) -> dict[str, str]:
    backend = tomllib.loads((root / "backend/pyproject.toml").read_text(encoding="utf-8"))
    cargo = tomllib.loads((root / "desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8"))
    frontend = json.loads((root / "frontend/package.json").read_text(encoding="utf-8"))
    desktop = json.loads((root / "desktop/package.json").read_text(encoding="utf-8"))
    tauri = json.loads((root / "desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    return {
        "backend": str(backend["project"]["version"]),
        "frontend": str(frontend["version"]),
        "desktop": str(desktop["version"]),
        "tauri": str(tauri["version"]),
        "cargo": str(cargo["package"]["version"]),
    }


def owner_decision(root: Path) -> dict[str, Any]:
    relative = phase_artifact_relative("P24", "P24_RC_DECISION.yaml")
    path = root / relative
    if not path.is_file():
        return {"decision": "PENDING", "valid": False, "path": relative}
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {"decision": "INVALID", "valid": False, "path": relative}
    required = {"schema_version", "decision", "owner", "recorded_at", "rationale"}
    if not isinstance(document, dict) or set(document) != required:
        return {"decision": "INVALID", "valid": False, "path": relative}
    decision = document.get("decision")
    valid = (
        document.get("schema_version") == 1
        and decision in {"GO", "NO_GO"}
        and document.get("owner") == "project-owner"
        and isinstance(document.get("recorded_at"), str)
        and bool(str(document.get("rationale", "")).strip())
    )
    return {
        **document,
        "decision": decision if valid else "INVALID",
        "valid": valid,
        "path": relative,
    }


def approval_ledger(root: Path) -> dict[str, Any]:
    """驗證所有回溯核准皆綁定真實 package 與 transcript，而非只計檔案數。"""

    records: list[dict[str, Any]] = []
    valid_phases: list[str] = []
    invalid: list[str] = []
    for phase in PHASES:
        relative = Path(f".laes/reviews/{phase}_APPROVAL.yaml")
        error = _approval_record_error(root, phase, root / relative)
        records.append(
            {
                "phase": phase,
                "path": relative.as_posix(),
                "valid": error is None,
                "error": error,
            }
        )
        if error is None:
            valid_phases.append(phase)
        else:
            invalid.append(f"{phase}:{error}")
    return {
        "expected": len(PHASES),
        "valid": len(valid_phases),
        "valid_phases": valid_phases,
        "invalid": invalid,
        "records": records,
    }


def _approval_record_error(root: Path, phase: str, path: Path) -> str | None:
    """回傳穩定錯誤代碼；schema、hash、決策或證據行任一錯誤即拒絕。"""

    if not path.is_file():
        return "missing"
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return "unreadable"
    if not isinstance(document, dict) or set(document) != APPROVAL_RECORD_FIELDS:
        return "schema"
    rules = (
        document.get("schema_version") == 1,
        document.get("record_type") == "retrospective-approval-ledger",
        document.get("phase") == phase,
        document.get("decision") == "APPROVED",
        document.get("reviewer") == "ChatGPT",
        document.get("reviewer_approved") is True,
        document.get("owner") == "project-owner",
        document.get("owner_approved") is True,
        bool(str(document.get("ledger_created_on", "")).strip()),
        bool(str(document.get("limitations", "")).strip()),
    )
    if not all(rules):
        return "decision"

    expected_package = phase_artifact_relative(
        phase,
        f"{phase}_SUPERVISOR_REVIEW_PACKAGE.md",
    )
    if document.get("review_package") != expected_package:
        return "package-path"
    package = root / expected_package
    transcript_relative = document.get("source_transcript")
    if not isinstance(transcript_relative, str):
        return "transcript-path"
    if Path(transcript_relative).is_absolute():
        return "transcript-path"
    transcript = root / transcript_relative
    if not package.is_file() or not transcript.is_file():
        return "source-missing"

    package_hash = document.get("review_package_sha256")
    transcript_hash = document.get("source_transcript_sha256")
    origin_hash = document.get("origin_transcript_sha256")
    hashes = (package_hash, transcript_hash, origin_hash)
    if not all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in hashes
    ):
        return "hash-format"
    if sha256_file(package) != package_hash:
        return "package-hash"
    if sha256_file(transcript) != transcript_hash:
        return "transcript-hash"

    lines = transcript.read_text(encoding="utf-8").splitlines()
    review_line = document.get("review_evidence_line")
    owner_line = document.get("owner_authorization_line")
    line_numbers = (review_line, owner_line)
    if not all(
        isinstance(number, int) and 1 <= number <= len(lines)
        for number in line_numbers
    ):
        return "line-range"
    review_text = lines[review_line - 1]
    owner_text = lines[owner_line - 1]
    original_review = document.get("original_review_evidence_line")
    original_owner = document.get("original_owner_authorization_line")
    if not all(isinstance(number, int) and number > 0 for number in (original_review, original_owner)):
        return "original-line-range"
    if f"原 transcript line {original_review}" not in review_text:
        return "original-review-line"
    if f"原 transcript line {original_owner}" not in owner_text:
        return "original-owner-line"
    if origin_hash not in lines[4]:
        return "origin-hash-binding"
    if phase not in review_text or not any(
        marker in review_text for marker in ("PASS", "APPROVED")
    ):
        return "review-evidence"
    if "owner" not in owner_text.lower():
        return "owner-evidence"
    if PASS_MARKER not in package.read_text(encoding="utf-8", errors="replace"):
        return "package-not-pass"
    return None


def audit_repository(root: Path) -> dict[str, Any]:
    root = root.resolve()
    evidence = evidence_index(root)
    findings: list[Finding] = []
    missing_reports = [
        item["phase"]
        for item in evidence
        if item["kind"] == "completion-report" and not item["present"]
    ]
    failed_packages = []
    for phase in PHASES:
        package = phase_artifact_path(
            root,
            phase,
            f"{phase}_SUPERVISOR_REVIEW_PACKAGE.md",
        )
        if not package.is_file() or PASS_MARKER not in package.read_text(
            encoding="utf-8",
            errors="replace",
        ):
            failed_packages.append(phase)
    if failed_packages:
        findings.append(
            _finding(
                "EVIDENCE-001",
                "critical",
                "Phase Supervisor PASS evidence is incomplete",
                ", ".join(failed_packages),
                "Release Engineering",
                "Restore authentic PASS packages before any RC decision.",
            )
        )
    if missing_reports:
        findings.append(
            _finding(
                "EVIDENCE-002",
                "high",
                "Mandatory phase completion reports are missing",
                ", ".join(missing_reports),
                "Project Owner",
                "Recover original reports or re-audit the affected phases; do not reconstruct approvals from memory.",
            )
        )

    approvals = approval_ledger(root)
    if approvals["valid"] != len(PHASES):
        findings.append(
            _finding(
                "EVIDENCE-003",
                "high",
                "Durable reviewer and owner approval ledger is incomplete",
                (
                    f"valid={approvals['valid']}/{len(PHASES)}; "
                    f"invalid={','.join(approvals['invalid'])}"
                ),
                "Project Owner",
                "Provide authentic, hash-bound records tied to reviewed packages.",
            )
        )

    chain_errors = _phase_chain_errors(root)
    if chain_errors:
        findings.append(
            _finding(
                "EVIDENCE-004",
                "critical",
                "LAES phase chain is invalid",
                "; ".join(chain_errors),
                "Architecture Reviewer",
                "Correct governance templates through the approved LAES process.",
            )
        )

    manifest = manifest_integrity(root)
    if not manifest["present"] or any(
        manifest[key] for key in ("missing", "mismatched", "invalid", "unlisted")
    ) or manifest["discovery_error"]:
        findings.append(
            _finding(
                "INTEGRITY-001",
                "high",
                "Governance manifest does not match current source",
                (
                    f"missing={len(manifest['missing'])}, "
                    f"mismatched={len(manifest['mismatched'])}, "
                    f"invalid={len(manifest['invalid'])}"
                ),
                "Release Engineering",
                "Regenerate and independently review the manifest only after source is frozen.",
            )
        )

    versions = version_inventory(root)
    unique_versions = set(versions.values())
    if len(unique_versions) != 1 or not RC_VERSION.fullmatch(next(iter(unique_versions))):
        findings.append(
            _finding(
                "VERSION-001",
                "high",
                "Release versions are not aligned to a v1.0 release candidate",
                json.dumps(versions, sort_keys=True),
                "Release Engineering",
                "After product scope is frozen, align every package to one reviewed 1.0.0-rc.N version.",
            )
        )

    source = _git_source_state(root)
    if source["dirty_entries"]:
        findings.append(
            _finding(
                "SOURCE-001",
                "high",
                "Release source is not a clean immutable revision",
                f"commit={source['commit']}, dirty_entries={source['dirty_entries']}",
                "Project Owner",
                "Review and commit the approved source without deleting preserved user files.",
            )
        )

    secret_findings = scan_secrets(root)
    if secret_findings:
        findings.append(
            _finding(
                "SECURITY-001",
                "high",
                "Repository supply-chain secret scan is not clean",
                ", ".join(secret_findings),
                "Security Engineering",
                "Resolve each finding in an approved implementation phase and rerun the full secret scan.",
            )
        )

    native_evidence = root / "release-evidence"
    required_release_evidence = [
        native_evidence / "windows.json",
        native_evidence / "linux.json",
        native_evidence / "macos.json",
        native_evidence / "provenance.json",
        native_evidence / "signing-attestation.json",
    ]
    absent_release_evidence = [path.name for path in required_release_evidence if not path.is_file()]
    if absent_release_evidence:
        findings.append(
            _finding(
                "ARTIFACT-001",
                "high",
                "Commit-bound native artifacts and attestations are absent",
                ", ".join(absent_release_evidence),
                "Release Engineering",
                "Run the protected three-platform release workflow and retain signed commit-bound evidence.",
            )
        )

    decision = owner_decision(root)
    blockers = [asdict(item) for item in findings]
    recommendation = "NO_GO" if any(
        item.severity in {"critical", "high"} for item in findings
    ) else "GO"
    decision_consistent = decision["valid"] and decision["decision"] == recommendation
    return {
        "schema_version": 1,
        "audited_phases": list(PHASES),
        "source": source,
        "secret_scan": {"pass": not secret_findings, "findings": secret_findings},
        "versions": versions,
        "manifest": manifest,
        "phase_evidence": evidence,
        "approval_ledger": approvals,
        "blockers": blockers,
        "exceptions": [],
        "recommendation": recommendation,
        "owner_decision": decision,
        "decision_consistent": decision_consistent,
        "release_authorized": recommendation == "GO" and decision_consistent,
    }


def canonical_json(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _phase_chain_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for number in range(24):
        phase = f"P{number}"
        path = root / f".laes/phases/{phase}.yaml"
        if not path.is_file():
            errors.append(f"{phase}:missing")
            continue
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        expected_next = f"P{number + 1}"
        if document.get("current_phase") != phase or document.get("next_phase") != expected_next:
            errors.append(f"{phase}:chain")
    current = yaml.safe_load((root / ".laes/CURRENT_PHASE.yaml").read_text(encoding="utf-8"))
    if current.get("current_phase") != "P24" or current.get("next_phase") != "NONE":
        errors.append("CURRENT_PHASE:not-P24-terminal")
    return errors


def _git_source_state(root: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "status", "--porcelain=v1"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return {"commit": commit, "dirty_entries": len(status)}


def _finding(
    finding_id: str,
    severity: str,
    title: str,
    evidence: str,
    owner: str,
    resolution: str,
) -> Finding:
    return Finding(finding_id, severity, title, evidence, owner, resolution)


def main() -> int:
    parser = argparse.ArgumentParser(description="Linlin Agent enterprise RC evidence gate")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-go", action="store_true")
    args = parser.parse_args()
    result = audit_repository(args.root)
    serialized = canonical_json(result)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(
        f"P24 recommendation={result['recommendation']}; "
        f"blockers={len(result['blockers'])}; "
        f"owner_decision={result['owner_decision']['decision']}"
    )
    return 1 if args.require_go and not result["release_authorized"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
