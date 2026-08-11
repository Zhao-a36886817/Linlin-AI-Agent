#!/usr/bin/env python3
"""LAES phase supervisor. Workers never own phase transitions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required (python -m pip install PyYAML).") from exc


ROOT = Path(__file__).resolve().parents[1]
LAES = ROOT / ".laes"
CURRENT = LAES / "CURRENT_PHASE.yaml"
STATE = LAES / "REVIEW_STATE.yaml"
POLICY = LAES / "SUPERVISOR_POLICY.yaml"
BASELINE = LAES / "SUPERVISOR_BASELINE.json"
RESULTS = LAES / "SUPERVISOR_RESULTS.json"
# 每一個 phase 擁有獨立的治理產物資料夾。未來 validate 會直接把審查包寫入
# 對應 P 編號，不再把新報告散落到專案根目錄。
PHASE_ARTIFACTS = ROOT / "docs" / "governance" / "phase-artifacts"
SELF_ARTIFACTS = {
    ".laes/REVIEW_STATE.yaml",
    ".laes/SUPERVISOR_BASELINE.json",
    ".laes/SUPERVISOR_RESULTS.json",
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Expected a YAML mapping: {path}")
    return data


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def ignored(path: Path) -> bool:
    parts = set(path.parts)
    name = rel(path)
    return (bool(parts & {".git", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", "dist", "target"})
            or name in SELF_ARTIFACTS or name.endswith("_SUPERVISOR_REVIEW_PACKAGE.md"))


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def snapshot() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in ROOT.rglob("*"):
        if path.is_file() and not ignored(path):
            result[rel(path)] = digest(path)
    return result


def changes(base: dict[str, str], current: dict[str, str]) -> list[str]:
    return sorted(key for key in base.keys() | current.keys() if base.get(key) != current.get(key))


def phase() -> dict[str, Any]:
    return load_yaml(CURRENT)


def state() -> dict[str, Any]:
    return load_yaml(STATE)


def phase_policy(name: str) -> dict[str, Any]:
    configured = load_yaml(POLICY).get("phases", {}).get(name)
    if not isinstance(configured, dict):
        raise SystemExit(f"No machine policy configured for {name}; refusing to guess.")
    return configured


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "-C", str(ROOT), *args],
        text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
    )


def cmd_begin(_: argparse.Namespace) -> int:
    p = phase()
    s = state()
    if s.get("gate") == "APPROVED":
        raise SystemExit("Approved review exists; transition or reject it before beginning again.")
    snap = snapshot()
    BASELINE.write_text(json.dumps(snap, indent=2, sort_keys=True), encoding="utf-8")
    write_yaml(STATE, {
        "laes_version": p.get("laes_version"), "phase": p["current_phase"],
        "gate": "IN_PROGRESS", "checks": "NOT_RUN", "began_at": now(),
        "reviewer": None, "reviewer_approved": False, "owner_approved": False,
        "approval_note": None, "validated_snapshot": None,
    })
    print(f"{p['current_phase']}: IN_PROGRESS; baseline contains {len(snap)} files")
    return 0


def cmd_reopen(args: argparse.Namespace) -> int:
    """Reopen an approved terminal gate after an owner-authorized roadmap extension."""

    p = phase()
    s = state()
    if not args.owner_approved:
        raise SystemExit("Reopen denied: explicit owner approval is required.")
    if not (
        s.get("gate") == "APPROVED"
        and s.get("checks") == "PASS"
        and s.get("reviewer_approved")
        and s.get("owner_approved")
    ):
        raise SystemExit("Reopen denied: the existing gate must be fully approved.")
    if s.get("phase") != p.get("current_phase"):
        raise SystemExit("Reopen denied: review state and current phase differ.")
    snap = snapshot()
    BASELINE.write_text(json.dumps(snap, indent=2, sort_keys=True), encoding="utf-8")
    write_yaml(STATE, {
        "laes_version": p.get("laes_version"), "phase": p["current_phase"],
        "gate": "IN_PROGRESS", "checks": "NOT_RUN", "began_at": now(),
        "reviewer": None, "reviewer_approved": False, "owner_approved": False,
        "approval_note": None, "validated_snapshot": None,
        "reopened_from_approved": True, "reopen_note": args.note,
    })
    print(f"{p['current_phase']}: IN_PROGRESS; owner-authorized reopen; baseline contains {len(snap)} files")
    return 0


def cmd_reprioritize(args: argparse.Namespace) -> int:
    """Activate an owner-authorized roadmap phase without forging a PASS gate."""

    current_phase = phase()
    current_state = state()
    if not args.owner_approved:
        raise SystemExit("Reprioritize denied: explicit owner approval is required.")
    allowed_source = current_state.get("gate") in {"REJECTED", "WAITING_REVIEW"}
    allowed_source = allowed_source or (
        current_state.get("gate") == "IN_PROGRESS"
        and current_state.get("checks") == "NOT_RUN"
    )
    if not allowed_source:
        raise SystemExit("Reprioritize denied: close or reject active work first.")
    if current_state.get("gate") == "WAITING_REVIEW" and current_state.get("checks") != "FAIL":
        raise SystemExit("Reprioritize denied: a reviewable PASS gate must use transition.")
    template = LAES / "phases" / f"{args.phase}.yaml"
    if not template.is_file():
        raise SystemExit(f"Reprioritize denied: no phase template for {args.phase}.")
    phase_policy(args.phase)
    CURRENT.write_bytes(template.read_bytes())
    write_yaml(STATE, {
        "laes_version": current_phase.get("laes_version"),
        "phase": args.phase,
        "gate": "NOT_STARTED",
        "checks": "NOT_RUN",
        "reprioritized_at": now(),
        "reprioritized_from": current_phase["current_phase"],
        "owner_approved": True,
        "approval_note": args.note,
    })
    print(f"Reprioritized {current_phase['current_phase']} -> {args.phase}; run begin before implementation.")
    return 0


def run_validation(item: dict[str, Any]) -> dict[str, Any]:
    cwd = ROOT / item.get("cwd", ".")
    command = [str(x) for x in item["command"]]
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True,
                          encoding="utf-8", errors="replace", check=False)
    return {"name": item["name"], "command": command, "cwd": rel(cwd),
            "exit_code": proc.returncode, "pass": proc.returncode == 0,
            "stdout": proc.stdout[-12000:], "stderr": proc.stderr[-12000:]}


def policy_checks(base: dict[str, str], current: dict[str, str], p: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    changed = changes(base, current)
    checks: list[dict[str, Any]] = []
    current_name = p["current_phase"]
    future = [x for x in changed if re.fullmatch(r"(?:\.laes/phases|docs/development)/P\d+\.(?:yaml|md)", x)
              and f"/{current_name}." not in f"/{x}"]
    checks.append({"name": "future_phase_isolation", "pass": not future, "findings": future})
    protected = [x for x in changed if any(x == y or x.startswith(y.rstrip("/") + "/") for y in cfg.get("protected_paths", []))]
    checks.append({"name": "protected_architecture", "pass": not protected, "findings": protected})
    phase_tamper = digest(CURRENT) != digest(LAES / "phases" / f"{current_name}.yaml")
    checks.append({"name": "current_phase_unchanged", "pass": not phase_tamper,
                   "findings": ["CURRENT_PHASE differs from its approved template"] if phase_tamper else []})
    allowed = cfg.get("allowed_paths", [])
    scope = [x for x in changed if not any(x == y or x.startswith(y.rstrip("/") + "/") for y in allowed)]
    checks.append({"name": "scope", "pass": not scope, "findings": scope})
    secret_re = re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")
    path_re = re.compile(r"(?:[A-Za-z]:\\Users\\[^\\\s]+|/home/[^/\s]+)")
    secrets: list[str] = []
    hardcoded: list[str] = []
    for name in changed:
        path = ROOT / name
        if not path.is_file() or path.stat().st_size > 2_000_000 or path.suffix.lower() in {".lock", ".png", ".jpg", ".docx"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if secret_re.search(text): secrets.append(name)
        if path.suffix.lower() in {".py", ".js", ".ts", ".tsx", ".ps1", ".sh"} and path_re.search(text): hardcoded.append(name)
    checks.append({"name": "sensitive_information", "pass": not secrets, "findings": secrets})
    checks.append({"name": "cross_platform_paths", "pass": not hardcoded, "findings": hardcoded})
    nested = ROOT / "Linlin-Agent" / ".git"
    checks.append({"name": "nested_repository_guard", "pass": True,
                   "findings": ["Nested repository detected and left untouched"] if nested.exists() else []})
    return checks


def report(results: dict[str, Any]) -> Path:
    name = f"{results['phase']}_SUPERVISOR_REVIEW_PACKAGE.md"
    path = PHASE_ARTIFACTS / results["phase"] / name
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {results['phase']} Supervisor Review Package", "", f"Generated: {results['generated_at']}", "",
             f"Overall checks: **{'PASS' if results['all_pass'] else 'FAIL'}**", "", "## Changed files since begin", ""]
    lines += [f"- `{x}`" for x in results["changed_files"]] or ["- None"]
    lines += ["", "## Policy checks", ""]
    for item in results["policy_checks"]:
        lines.append(f"- **{item['name']}**: {'PASS' if item['pass'] else 'FAIL'}")
        lines += [f"  - {x}" for x in item["findings"]]
    lines += ["", "## Required validation", ""]
    for item in results["validations"]:
        lines += [f"### {item['name']}: {'PASS' if item['pass'] else 'FAIL'}", "", f"Exit code: `{item['exit_code']}`", "", "```text", (item["stdout"] + item["stderr"]).strip(), "```", ""]
    lines += ["## Gate", "", "The Supervisor has set `WAITING_REVIEW`. Transition remains forbidden until reviewer and owner approval are recorded.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def cmd_validate(_: argparse.Namespace) -> int:
    p, s = phase(), state()
    if s.get("gate") != "IN_PROGRESS" or s.get("phase") != p.get("current_phase") or not BASELINE.exists():
        raise SystemExit("Run begin for the current phase before validate.")
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    before_report = snapshot()
    cfg = phase_policy(p["current_phase"])
    policies = policy_checks(base, before_report, p, cfg)
    validations = [run_validation(x) for x in cfg.get("validations", [])]
    all_pass = all(x["pass"] for x in policies + validations)
    result = {"phase": p["current_phase"], "generated_at": now(), "all_pass": all_pass,
              "changed_files": changes(base, before_report), "policy_checks": policies, "validations": validations,
              "snapshot_hash": hashlib.sha256(json.dumps(before_report, sort_keys=True).encode()).hexdigest()}
    RESULTS.write_text(json.dumps(result, indent=2), encoding="utf-8")
    package = report(result)
    s.update({"gate": "WAITING_REVIEW", "checks": "PASS" if all_pass else "FAIL",
              "validated_at": now(), "validated_snapshot": result["snapshot_hash"], "review_package": rel(package)})
    write_yaml(STATE, s)
    print(f"{p['current_phase']}: WAITING_REVIEW; checks={'PASS' if all_pass else 'FAIL'}; {package.name}")
    return 0 if all_pass else 1


def cmd_review(args: argparse.Namespace) -> int:
    s = state()
    if s.get("gate") != "WAITING_REVIEW": raise SystemExit("Gate must be WAITING_REVIEW.")
    if args.decision == "approve" and s.get("checks") != "PASS": raise SystemExit("Cannot approve failed checks.")
    s.update({"gate": "APPROVED" if args.decision == "approve" else "REJECTED",
              "reviewer": args.reviewer, "reviewer_approved": args.decision == "approve",
              "owner_approved": bool(args.owner_approved and args.decision == "approve"),
              "approval_note": args.note, "reviewed_at": now()})
    write_yaml(STATE, s)
    print(f"Gate: {s['gate']}; owner_approved={s['owner_approved']}")
    return 0


def cmd_transition(_: argparse.Namespace) -> int:
    p, s = phase(), state()
    if not (s.get("gate") == "APPROVED" and s.get("checks") == "PASS" and s.get("reviewer_approved") and s.get("owner_approved")):
        raise SystemExit("Transition denied: approved reviewer + owner gate and PASS checks are required.")
    current = snapshot()
    current_hash = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
    if current_hash != s.get("validated_snapshot"):
        raise SystemExit("Transition denied: repository changed after validation; run begin/validate/review again.")
    next_name = p.get("next_phase")
    template = LAES / "phases" / f"{next_name}.yaml"
    if not next_name or not template.exists(): raise SystemExit("No configured next phase template.")
    CURRENT.write_bytes(template.read_bytes())
    write_yaml(STATE, {"laes_version": p.get("laes_version"), "phase": next_name, "gate": "IN_PROGRESS",
                       "checks": "NOT_RUN", "transitioned_at": now(), "transitioned_from": p["current_phase"]})
    print(f"Transitioned {p['current_phase']} -> {next_name}. No worker was started.")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    print(yaml.safe_dump({"phase": phase(), "review_state": state()}, sort_keys=False, allow_unicode=True))
    return 0


def cmd_worker_info(_: argparse.Namespace) -> int:
    exe = shutil.which("codex")
    print(json.dumps({"codex_path": exe, "callable": False,
                      "reason": "Packaged Codex executable is access-denied from non-interactive child processes; use an external runner to invoke `begin`, a worker, then `validate`."}, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    for name, func in (("begin", cmd_begin), ("validate", cmd_validate), ("transition", cmd_transition), ("status", cmd_status), ("worker-info", cmd_worker_info)):
        sub.add_parser(name).set_defaults(func=func)
    reopen = sub.add_parser("reopen")
    reopen.add_argument("--owner-approved", action="store_true")
    reopen.add_argument("--note", required=True)
    reopen.set_defaults(func=cmd_reopen)
    reprioritize = sub.add_parser("reprioritize")
    reprioritize.add_argument("phase")
    reprioritize.add_argument("--owner-approved", action="store_true")
    reprioritize.add_argument("--note", required=True)
    reprioritize.set_defaults(func=cmd_reprioritize)
    review = sub.add_parser("review")
    review.add_argument("decision", choices=("approve", "reject")); review.add_argument("--reviewer", required=True)
    review.add_argument("--owner-approved", action="store_true"); review.add_argument("--note")
    review.set_defaults(func=cmd_review)
    return ap


if __name__ == "__main__":
    args = parser().parse_args()
    raise SystemExit(args.func(args))
