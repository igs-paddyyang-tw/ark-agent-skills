#!/usr/bin/env python3
"""從 git log 規則式產出分類 changelog（零 LLM 依賴）。

規則式解析 Conventional Commits（feat/fix/refactor/docs/chore/test/perf/style/ci/build），
非規範 commit 落 other；標題含 `!` 或 body 含 `BREAKING CHANGE` 歸 breaking。
輸出分類 Markdown + 統計（commit 數 / 檔案數 / 行數 / 貢獻者）。

用法
----
    python changelog_gen.py --last 20                 # 最近 20 筆
    python changelog_gen.py --range v1.0.0..HEAD      # tag 範圍
    python changelog_gen.py --since 2026-09-01        # 日期起
    python changelog_gen.py --last 20 --output CHANGELOG.md   # 寫檔（預設印 stdout）

設計原則
--------
- 零 LLM：純規則解析，可離線、可 CI。
- --help 無副作用：不寫任何檔、不呼叫 git。
- LLM 只在 SKILL.md 工作流程的「highlight 摘要」那步介入，本腳本只產骨架。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict

# Conventional Commits type → 顯示標題
TYPE_TITLES: dict[str, str] = {
    "feat": "✨ Features",
    "fix": "🐛 Fixes",
    "perf": "⚡ Performance",
    "refactor": "♻️ Refactor",
    "docs": "📝 Docs",
    "test": "🧪 Tests",
    "build": "📦 Build",
    "ci": "🔧 CI",
    "style": "💄 Style",
    "chore": "🔨 Chore",
}
# 輸出順序（breaking 最前、other 最後）
SECTION_ORDER = ["breaking", "feat", "fix", "perf", "refactor",
                 "docs", "test", "build", "ci", "style", "chore", "other"]

# type(scope)!: subject —— scope 與 ! 皆選配
_HEADER_RE = re.compile(
    r"^(?P<type>\w+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s*(?P<subject>.+)$"
)


def _run_git(args: list[str]) -> str:
    """執行 git 並回傳 stdout（失敗則 raise）。"""
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    )
    return result.stdout


def _build_log_args(ns: argparse.Namespace) -> list[str]:
    """依參數組出 git log 範圍引數。"""
    # 用非可見的分隔符切欄位，避免 commit 訊息含 | 造成誤切
    fmt = "%H%x1f%an%x1f%s%x1f%b%x1e"
    args = ["log", f"--pretty=format:{fmt}"]
    if ns.range:
        args.append(ns.range)
    elif ns.since:
        args.append(f"--since={ns.since}")
    elif ns.last:
        args.append(f"-{ns.last}")
    return args


def _classify(subject: str, body: str) -> tuple[str, str, str]:
    """回傳 (section, scope, clean_subject)。"""
    m = _HEADER_RE.match(subject.strip())
    breaking = "BREAKING CHANGE" in body or "BREAKING-CHANGE" in body
    if not m:
        return ("breaking" if breaking else "other", "", subject.strip())
    ctype = m.group("type").lower()
    scope = m.group("scope") or ""
    subj = m.group("subject").strip()
    if m.group("bang") or breaking:
        return ("breaking", scope, subj)
    section = ctype if ctype in TYPE_TITLES else "other"
    return (section, scope, subj)


def parse_commits(raw: str) -> list[dict]:
    """解析 git log raw 輸出為 commit dict 清單。"""
    commits: list[dict] = []
    for record in raw.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split("\x1f")
        if len(parts) < 3:
            continue
        sha, author, subject = parts[0], parts[1], parts[2]
        body = parts[3] if len(parts) > 3 else ""
        section, scope, subj = _classify(subject, body)
        commits.append({
            "sha": sha[:7], "author": author,
            "section": section, "scope": scope, "subject": subj,
        })
    return commits


def _diff_stat(ns: argparse.Namespace) -> tuple[int, int]:
    """回傳 (檔案數, 變動行數)；取不到則 (0, 0)。"""
    try:
        if ns.range:
            spec = ns.range
        elif ns.last:
            spec = f"HEAD~{ns.last}..HEAD"
        else:
            return (0, 0)
        out = _run_git(["diff", "--shortstat", spec])
        files = re.search(r"(\d+) files? changed", out)
        ins = re.search(r"(\d+) insertions?", out)
        dels = re.search(r"(\d+) deletions?", out)
        n_files = int(files.group(1)) if files else 0
        n_lines = (int(ins.group(1)) if ins else 0) + (int(dels.group(1)) if dels else 0)
        return (n_files, n_lines)
    except (subprocess.CalledProcessError, ValueError):
        return (0, 0)


def render_markdown(commits: list[dict], n_files: int, n_lines: int) -> str:
    """組裝分類 changelog Markdown。"""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for c in commits:
        grouped[c["section"]].append(c)

    lines: list[str] = ["# Changelog", ""]
    lines.append("> 由 changelog_gen.py 規則式產出骨架；highlight 摘要待 LLM 補。")
    lines.append("")

    for section in SECTION_ORDER:
        items = grouped.get(section)
        if not items:
            continue
        title = "💥 Breaking Changes" if section == "breaking" else \
                TYPE_TITLES.get(section, "📌 Other")
        lines.append(f"## {title}")
        lines.append("")
        for c in items:
            scope = f"**{c['scope']}**: " if c["scope"] else ""
            lines.append(f"- {scope}{c['subject']} (`{c['sha']}`)")
        lines.append("")

    # 統計
    authors = sorted({c["author"] for c in commits})
    lines.append("## 📊 統計")
    lines.append("")
    lines.append(f"- Commits：{len(commits)}")
    lines.append(f"- 檔案變動：{n_files}")
    lines.append(f"- 行數變動：{n_lines}")
    lines.append(f"- 貢獻者（{len(authors)}）：{', '.join(authors)}")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="規則式 git log → 分類 changelog（零 LLM）"
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--last", type=int, metavar="N", help="最近 N 筆 commit")
    g.add_argument("--range", metavar="A..B", help="git 範圍，如 v1.0.0..HEAD")
    g.add_argument("--since", metavar="DATE", help="起始日期，如 2026-09-01")
    p.add_argument("--output", metavar="FILE", help="輸出檔（預設印 stdout）")
    return p


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    if not (ns.last or ns.range or ns.since):
        ns.last = 20  # 預設最近 20 筆

    try:
        raw = _run_git(_build_log_args(ns))
    except FileNotFoundError:
        print("🔴 找不到 git，請確認已安裝並在 PATH 中", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"🔴 git log 失敗：{e.stderr.strip()}", file=sys.stderr)
        return 1

    commits = parse_commits(raw)
    if not commits:
        print("⚠️ 指定範圍內沒有 commit", file=sys.stderr)
        return 1

    n_files, n_lines = _diff_stat(ns)
    md = render_markdown(commits, n_files, n_lines)

    if ns.output:
        from pathlib import Path
        Path(ns.output).write_text(md, encoding="utf-8")
        print(f"✅ 已寫入 {ns.output}（{len(commits)} commits）")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
