from __future__ import annotations

"""建立及驗證 Linlin Agent 的完整發布來源 SHA-256 manifest。

manifest 的範圍以 Git 真正會納入版本控制的工作樹檔案為準，因此會自動排除
`.gitignore` 中的本機模型、建置快取與參考 ZIP。P24 自身的動態審查輸出另行
排除，避免「先產生 manifest、再寫入稽核結果」形成無法收斂的循環。
"""

import argparse
import hashlib
import subprocess
from pathlib import Path, PurePosixPath

MANIFEST_NAME = "MANIFEST.sha256"
# P24 的 evidence index、review package 與 owner decision 是針對已凍結來源所
# 產生的外部審查結果，不是被審查的產品來源。它們仍保留在專案內供人工稽核。
EXCLUDED_PREFIXES = ("docs/governance/phase-artifacts/P24/",)


class ManifestError(RuntimeError):
    """表示 Git 來源盤點或 manifest 格式無法安全完成。"""


def sha256_file(path: Path) -> str:
    """以串流方式計算檔案雜湊，避免未來大型來源檔一次載入記憶體。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def release_source_paths(root: Path) -> list[PurePosixPath]:
    """回傳應完整列入 manifest 的現存 Git 發布來源，相對路徑固定為 POSIX。"""

    root = root.resolve()
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ManifestError(f"Git source inventory failed: {message}")

    paths: set[PurePosixPath] = set()
    for raw_item in result.stdout.split(b"\0"):
        if not raw_item:
            continue
        relative_text = raw_item.decode("utf-8", errors="strict").replace("\\", "/")
        relative = PurePosixPath(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ManifestError(f"Unsafe Git path: {relative_text}")
        if relative_text == MANIFEST_NAME or relative_text.startswith(EXCLUDED_PREFIXES):
            continue
        target = root.joinpath(*relative.parts)
        # `git ls-files --cached` 可能暫時列出 staged-then-deleted 路徑；manifest
        # 描述的是目前將凍結的工作樹，所以只納入實際存在的普通檔案。
        if not target.is_file():
            continue
        if target.is_symlink():
            raise ManifestError(f"Symlink is not allowed in release source: {relative_text}")
        if "\n" in relative_text or "\r" in relative_text:
            raise ManifestError(f"Manifest cannot encode path: {relative_text!r}")
        paths.add(relative)
    return sorted(paths, key=lambda item: item.as_posix())


def render_manifest(root: Path) -> str:
    """依穩定排序輸出 `<sha256><兩空白><相對路徑>`，確保可重現。"""

    root = root.resolve()
    lines = []
    for relative in release_source_paths(root):
        target = root.joinpath(*relative.parts)
        lines.append(f"{sha256_file(target)}  {relative.as_posix()}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="建立或檢查完整治理來源 manifest")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--check",
        action="store_true",
        help="只驗證 MANIFEST.sha256 是否與重新計算結果完全一致",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = root / MANIFEST_NAME
    expected = render_manifest(root)
    if args.check:
        if not manifest.is_file() or manifest.read_text(encoding="utf-8") != expected:
            print("Governance manifest drift detected.")
            return 1
        print(f"Governance manifest verified: {len(expected.splitlines())} files")
        return 0
    manifest.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Governance manifest written: {len(expected.splitlines())} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
