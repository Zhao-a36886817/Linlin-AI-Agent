from __future__ import annotations

"""以保存的 task transcript 回溯建立 P24 缺少的歷史治理證據。

此工具不從記憶推測核准，也不宣稱找回原始 REVIEW_STATE。每一筆 ledger 都同時
綁定 canonical Supervisor PASS package、最小化證據摘錄及完整 transcript
SHA-256，並記錄實際 Gate decision/owner authorization 原始行號；來源內容或
行號不一致時一律 fail closed。完整 task export 僅留在 F 槽，不納入 release。
"""

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = Path("Codex-Task-Export/CODEX_TASK_TRANSCRIPT.md")
EVIDENCE_EXCERPT = Path("docs/governance/evidence/P0_P23_APPROVAL_EXCERPTS.md")
PASS_MARKER = "Overall checks: **PASS**"
RECOVERY_DATE = "2026-08-11"


@dataclass(frozen=True, slots=True)
class PhaseEvidence:
    """經人工逐階段交叉比對的 transcript mapping 與範圍摘要。"""

    review_line: int
    owner_line: int
    summary: str


# P0-P9 共用原始任務的持續 owner 授權（line 22）；P10-P21 共用後續明確的
# P10-P24 持續授權（line 579）；P22/P23 另綁定較接近該 Gate 的再次授權。
PHASE_EVIDENCE: dict[str, PhaseEvidence] = {
    "P0": PhaseEvidence(35, 22, "穩定建置與測試入口，確認基線可重現。"),
    "P1": PhaseEvidence(85, 22, "統一 Provider runtime 路徑並消除重複實作。"),
    "P2": PhaseEvidence(106, 22, "強化 Ollama reasoning、tool calling 與輸出邊界。"),
    "P3": PhaseEvidence(128, 22, "以明確 profile 限制工具曝光與上下文成本。"),
    "P4": PhaseEvidence(169, 22, "建立 Workspace、archive、Git、terminal 安全邊界。"),
    "P5": PhaseEvidence(199, 22, "建立 credential identifier 與安全儲存／遮罩規則。"),
    "P6": PhaseEvidence(237, 22, "以 fail-closed 分類 Provider 成本與可用性。"),
    "P7": PhaseEvidence(263, 22, "移除機器 prefix 並正規化跨平台依賴設定。"),
    "P8": PhaseEvidence(308, 22, "收斂 React frontend 與 Tauri 的唯一建置路徑。"),
    "P9": PhaseEvidence(334, 22, "稽核進階 runtime 並記錄 keep/defer 與 RFC 邊界。"),
    "P10": PhaseEvidence(623, 579, "完成預設關閉且具隔離／刪除能力的 Memory runtime。"),
    "P11": PhaseEvidence(656, 579, "完成受 Workspace/Provider 邊界保護的 RAG runtime。"),
    "P12": PhaseEvidence(676, 579, "完成 deny-by-default MCP runtime 與 capability gate。"),
    "P13": PhaseEvidence(701, 579, "完成版本化 plugin manifest 與受限生命週期。"),
    "P14": PhaseEvidence(739, 579, "完成可重現且不重送已完成工作的 scheduler。"),
    "P15": PhaseEvidence(777, 579, "完成權限、預算與取消傳播的 multi-agent runtime。"),
    "P16": PhaseEvidence(812, 579, "完成受 Workspace 保護的 multimodal artifact runtime。"),
    "P17": PhaseEvidence(844, 579, "完成先遮罩再保留且無隱藏遙測的 diagnostics。"),
    "P18": PhaseEvidence(875, 579, "完成資源預留、過載、取消與 soak 證據。"),
    "P19": PhaseEvidence(900, 579, "完成 deterministic、tenant-isolated policy gate。"),
    "P20": PhaseEvidence(1395, 579, "完成桌面封裝、簽章驗證與啟動 smoke。"),
    "P21": PhaseEvidence(3124, 579, "完成供應鏈、SBOM、依賴稽核與三平台 CI 基線。"),
    "P22": PhaseEvidence(4709, 4697, "完成 API 版本契約、相容性與 plugin 邊界審查。"),
    "P23": PhaseEvidence(5051, 4840, "完成 recovery transaction 與惡意 archive 防護。"),
}


def sha256_file(path: Path) -> str:
    """串流計算小寫 SHA-256，不把來源內容複製到 log。"""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def transcript_line(lines: list[str], number: int) -> str:
    """依一基底行號取證；mapping 過期時拒絕產生任何正式 ledger。"""

    if not 1 <= number <= len(lines):
        raise ValueError(f"Transcript line {number} is outside the durable source.")
    return lines[number - 1]


def sha256_text(content: str) -> str:
    """依實際寫檔的 UTF-8 bytes 計算可重現摘要。"""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def evidence_excerpt(
    transcript_lines: list[str],
    transcript_hash: str,
) -> tuple[str, dict[str, tuple[int, int]]]:
    """只保存 Gate/owner 必要行，避免把整份私人 task 對話帶入 release。"""

    output = [
        "# P0–P23 回溯核准最小證據摘錄",
        "",
        "> 本檔由 `scripts/p24_evidence_recovery.py` 從 F 槽既有 task transcript",
        "> 確定性產生；只保存 Gate 與 owner 授權必要行，不代表 P24 RC 發布核准。",
        f"> 原始完整 transcript SHA-256：`{transcript_hash}`",
        "",
    ]
    line_map: dict[str, tuple[int, int]] = {}
    for phase, evidence in PHASE_EVIDENCE.items():
        output.extend([f"## {phase}", ""])
        review_line = len(output) + 1
        output.append(
            f"- 原 transcript line {evidence.review_line} / reviewer："
            f"{transcript_line(transcript_lines, evidence.review_line).rstrip()}"
        )
        owner_line = len(output) + 1
        output.append(
            f"- 原 transcript line {evidence.owner_line} / owner："
            f"{transcript_line(transcript_lines, evidence.owner_line).rstrip()}"
        )
        output.append("")
        line_map[phase] = (review_line, owner_line)
    return "\n".join(output).rstrip() + "\n", line_map


def phase_title(specification: Path, phase: str) -> str:
    """從 canonical phase spec 取得標題，避免維護第二份名稱清單。"""

    for line in specification.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    raise ValueError(f"{phase} specification has no level-one title.")


def validation_names(package_text: str, phase: str) -> list[str]:
    """只列出保存 package 中明確標示 PASS 的 validation。"""

    names = re.findall(r"^### (.+): PASS$", package_text, flags=re.MULTILINE)
    if not names:
        raise ValueError(f"{phase} package has no explicit PASS validations.")
    return names


def approval_record(
    phase: str,
    evidence: PhaseEvidence,
    package_relative: Path,
    package_hash: str,
    excerpt_hash: str,
    origin_transcript_hash: str,
    excerpt_lines: tuple[int, int],
) -> dict[str, object]:
    """建立一筆 schema 嚴格、可由 enterprise gate 重算的 ledger。"""

    return {
        "schema_version": 1,
        "record_type": "retrospective-approval-ledger",
        "phase": phase,
        "decision": "APPROVED",
        "reviewer": "ChatGPT",
        "reviewer_approved": True,
        "owner": "project-owner",
        "owner_approved": True,
        "review_package": package_relative.as_posix(),
        "review_package_sha256": package_hash,
        "source_transcript": EVIDENCE_EXCERPT.as_posix(),
        "source_transcript_sha256": excerpt_hash,
        "origin_transcript_sha256": origin_transcript_hash,
        "review_evidence_line": excerpt_lines[0],
        "owner_authorization_line": excerpt_lines[1],
        "original_review_evidence_line": evidence.review_line,
        "original_owner_authorization_line": evidence.owner_line,
        "ledger_created_on": RECOVERY_DATE,
        "limitations": (
            "由 Supervisor PASS package 與 task transcript 最小摘錄回溯建立；"
            "原 transcript 僅以 SHA-256 綁定且不隨 release 發布。不是遺失的"
            "原始 REVIEW_STATE，也不宣稱未知的原始核准時間。"
        ),
    }


def completion_report(
    phase: str,
    title: str,
    evidence: PhaseEvidence,
    validations: list[str],
    package_relative: Path,
    package_hash: str,
    excerpt_hash: str,
    origin_transcript_hash: str,
) -> str:
    """產生有醒目限制說明的 P0-P9 回溯完成報告。"""

    validation_lines = "\n".join(f"- `{name}`：PASS" for name in validations)
    return f"""# {phase} 回溯完成報告 — {title}

> 證據恢復聲明：原始 `{phase}_COMPLETION_REPORT.md` 未隨專案轉移保留。本檔於
> {RECOVERY_DATE} 依 P24 要求進行回溯重審後建立，不冒充原始報告，也不補寫
> 無法證明的原始時間或 validated snapshot。

## 階段範圍與結論

{evidence.summary}目前保存的 canonical Supervisor package 明確標示
`Overall checks: **PASS**`；task transcript 也在指定行記錄 {phase} Gate
PASS/APPROVED，並可追溯至專案擁有者授權。本報告只確認保存證據支持當時 Gate
已通過，不代表目前 P24 RC 已取得 GO。

## 可驗證來源

- 規格：`docs/development/{phase}.md`
- Supervisor package：`{package_relative.as_posix()}`
- Supervisor package SHA-256：`{package_hash}`
- 最小化 transcript 證據：`{EVIDENCE_EXCERPT.as_posix()}`
- 最小化證據 SHA-256：`{excerpt_hash}`
- 原始完整 transcript SHA-256：`{origin_transcript_hash}`（原件只保留於 F 槽）
- Gate review 證據行：`{evidence.review_line}`
- Owner authorization 證據行：`{evidence.owner_line}`

兩個 SHA-256 也寫入 `.laes/reviews/{phase}_APPROVAL.yaml`。P24 enterprise gate
會重算雜湊並檢查 phase、reviewer、owner、決策及證據行；任一來源改變即失敗。

## 保存的驗證結果

{validation_lines}

這些結果來自當時 Supervisor package，不宣稱於 {RECOVERY_DATE} 重跑舊 snapshot。
P24 對目前來源執行的完整 regression 是另一份證據，兩者不可混用。

## 安全、隱私與跨平台覆核

回溯作業只讀取 F 槽既有規格、package 與 transcript；未讀取 workspace、
credential、簽章金鑰或雲端秘密。報告只保存雜湊與行號，並使用 repository-relative
POSIX 路徑，避免再次綁定舊 Windows 帳號。

## 偏差、限制與回復

- 這是回溯重審報告，不是遺失原件；原件日後尋回時必須先比對 provenance。
- 現在來源已歷經後續階段，不能由本報告推論 {phase} 當時完整 Git tree。
- 回復方式是移除本報告與 ledger，使 P24 重新出現缺證 blocker；不得以空白檔、
  口頭記憶或手工 Gate 狀態取代。
- P24 manifest、dirty source 與三平台簽章證據仍須獨立解決。
"""


def render_all(root: Path) -> dict[Path, str]:
    """驗證所有 durable input，並在記憶體產生確定性的 35 份文件。"""

    transcript_path = root / TRANSCRIPT
    transcript_lines = transcript_path.read_text(encoding="utf-8").splitlines()
    transcript_hash = sha256_file(transcript_path)
    excerpt, excerpt_line_map = evidence_excerpt(transcript_lines, transcript_hash)
    excerpt_hash = sha256_text(excerpt)
    rendered: dict[Path, str] = {root / EVIDENCE_EXCERPT: excerpt}
    for phase, evidence in PHASE_EVIDENCE.items():
        specification = root / f"docs/development/{phase}.md"
        package_relative = Path(
            f"docs/governance/phase-artifacts/{phase}/"
            f"{phase}_SUPERVISOR_REVIEW_PACKAGE.md"
        )
        package = root / package_relative
        package_text = package.read_text(encoding="utf-8", errors="replace")
        if PASS_MARKER not in package_text:
            raise ValueError(f"{phase} package is not PASS; recovery is forbidden.")

        review_text = transcript_line(transcript_lines, evidence.review_line)
        owner_text = transcript_line(transcript_lines, evidence.owner_line)
        if phase not in review_text or not any(
            marker in review_text for marker in ("PASS", "APPROVED")
        ):
            raise ValueError(f"{phase} review transcript mapping is stale.")
        if "owner" not in owner_text.lower():
            raise ValueError(f"{phase} owner authorization mapping is stale.")

        package_hash = sha256_file(package)
        approval_path = root / f".laes/reviews/{phase}_APPROVAL.yaml"
        rendered[approval_path] = yaml.safe_dump(
            approval_record(
                phase,
                evidence,
                package_relative,
                package_hash,
                excerpt_hash,
                transcript_hash,
                excerpt_line_map[phase],
            ),
            allow_unicode=True,
            sort_keys=False,
        )
        if phase in {f"P{number}" for number in range(10)}:
            report_path = root / (
                f"docs/governance/phase-artifacts/{phase}/"
                f"{phase}_COMPLETION_REPORT.md"
            )
            rendered[report_path] = completion_report(
                phase,
                phase_title(specification, phase),
                evidence,
                validation_names(package_text, phase),
                package_relative,
                package_hash,
                excerpt_hash,
                transcript_hash,
            )
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover hash-bound P0-P23 LAES evidence.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    rendered = render_all(root)
    drift: list[str] = []
    for path, expected in rendered.items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != expected:
                drift.append(path.relative_to(root).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8", newline="\n")
    if drift:
        print("Recovery evidence drift: " + ", ".join(drift))
        return 1
    action = "verified" if args.check else "written"
    print(f"P24 retrospective evidence {action}: {len(rendered)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
