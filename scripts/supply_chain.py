from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

import tomllib


class SupplyChainError(RuntimeError):
    pass


_SECRET_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "openai-key": re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "assigned-secret": re.compile(
        r"(?i)\b(?:password|api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]{16,}['\"]"
    ),
}
_EXCLUDED_PARTS = {".git", "node_modules", "target", "dist", "__pycache__"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def generate_sbom(root: Path) -> dict[str, Any]:
    components: dict[str, dict[str, str]] = {}
    backend = tomllib.loads((root / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    for dependency in backend["project"]["dependencies"]:
        name, version = _split_requirement(dependency)
        components[f"pypi:{name}"] = _component("library", name, version, f"pkg:pypi/{name}@{version}")

    package_lock = json.loads((root / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    for key, package in package_lock.get("packages", {}).items():
        if not key.startswith("node_modules/") or not package.get("version"):
            continue
        name = key.removeprefix("node_modules/")
        version = str(package["version"])
        components[f"npm:{name}"] = _component("library", name, version, f"pkg:npm/{name}@{version}")

    cargo = tomllib.loads((root / "desktop" / "src-tauri" / "Cargo.lock").read_text(encoding="utf-8"))
    for package in cargo.get("package", []):
        name = str(package["name"])
        version = str(package["version"])
        components[f"cargo:{name}"] = _component("library", name, version, f"pkg:cargo/{name}@{version}")

    ordered = [components[key] for key in sorted(components)]
    fingerprint = hashlib.sha256(
        json.dumps(ordered, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.UUID(fingerprint[:32])}",
        "version": 1,
        "metadata": {"component": _component("application", "linlin-agent", "0.1.0", "pkg:generic/linlin-agent@0.1.0")},
        "components": ordered,
    }


def backend_requirements(root: Path) -> list[str]:
    backend = tomllib.loads((root / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = list(backend["project"]["dependencies"])
    for requirement in requirements:
        _split_requirement(requirement)
    return sorted(requirements, key=str.casefold)


def generate_provenance(
    artifacts: list[Path], *, source_commit: str, builder: str, workflow_ref: str
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise SupplyChainError("Source commit must be a full lowercase Git SHA.")
    subjects = []
    for artifact in sorted(artifacts, key=lambda item: item.as_posix()):
        if not artifact.is_file() or artifact.is_symlink():
            raise SupplyChainError("Provenance subjects must be regular files.")
        subjects.append(
            {
                "name": artifact.name,
                "size": artifact.stat().st_size,
                "digest": {"sha256": sha256_file(artifact)},
            }
        )
    if not subjects:
        raise SupplyChainError("At least one provenance subject is required.")
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://github.com/linlin-agent/release/v1",
                "externalParameters": {"sourceCommit": source_commit, "workflowRef": workflow_ref},
            },
            "runDetails": {"builder": {"id": builder}},
        },
    }


def scan_secrets(root: Path, paths: list[Path] | None = None) -> list[str]:
    candidates = paths or _tracked_files(root)
    findings: list[str] = []
    for path in candidates:
        absolute = path if path.is_absolute() else root / path
        try:
            relative = absolute.resolve().relative_to(root.resolve())
        except ValueError:
            findings.append(f"outside-root:{path}")
            continue
        if (
            any(part in _EXCLUDED_PARTS for part in relative.parts)
            or (relative.parts and relative.parts[0] == "Linlin-Agent")
            or not absolute.is_file()
        ):
            continue
        try:
            content = absolute.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for name, pattern in _SECRET_PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{relative.as_posix()}:{line_number}:{name}")
    return findings


def canonical_json(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _tracked_files(root: Path) -> list[Path]:
    # F: 可能是 exFAT 等不記錄 Windows 擁有者資訊的可攜式磁碟。Git 2.35.2+
    # 會因此把合法的專案誤判為 dubious ownership。只針對本次命令信任已解析的
    # 專案根目錄，避免寫入使用者的全域 Git 設定，也不會放寬其他 repository。
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.resolve().as_posix()}",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [Path(item.decode()) for item in result.stdout.split(b"\0") if item]


def _split_requirement(requirement: str) -> tuple[str, str]:
    match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^;\s]+)", requirement)
    if not match:
        raise SupplyChainError(f"Dependency must be exactly pinned: {requirement}")
    return match.group(1).lower(), match.group(2)


def _component(kind: str, name: str, version: str, purl: str) -> dict[str, str]:
    return {"type": kind, "name": name, "version": version, "purl": purl}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("requirements", "sbom", "scan"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "scan":
        findings = scan_secrets(args.root)
        if findings:
            print("\n".join(findings))
            return 1
        print("Secret scan passed.")
        return 0
    if args.command == "requirements":
        if args.output is None:
            parser.error("--output is required for requirements")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(backend_requirements(args.root)) + "\n", encoding="utf-8")
        print(args.output)
        return 0
    if args.output is None:
        parser.error("--output is required for sbom")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical_json(generate_sbom(args.root)), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
