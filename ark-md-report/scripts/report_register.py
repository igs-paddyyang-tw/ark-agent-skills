"""report_register.py — 報告註冊器：索引 + 日報 log line + wiki source 建議。

報告通過 lint 後的最後一步。做三件事：
  1. 更新 docs/reports/_index.md（依 type 分組的總表）
  2. 對 docs/reports/log.md 追加一行 CollectorRunner 可解析的 pipe-delimited 記錄
  3. 若指定 --wiki，輸出該報告應加入哪些 wiki 頁面 sources 的建議（不自動改 wiki，
     遵循兩層信任模型：報告入 wiki 屬 LLM 蒸餾路徑，需人工/審核流程）

用法：
    python report_register.py docs/reports/review/2026-08-11-xxx.md
    python report_register.py report.md --wiki knowledge/myproj

log.md 行格式（日報 CollectorRunner 解析契約，勿改欄序）：
    date | type | subject | verdict | p0 | p1 | p2 | score | path
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from report_lint import parse_frontmatter  # noqa: E402


def reports_root(md_path: Path) -> Path:
    parts = md_path.parts
    if "reports" in parts:
        return Path(*parts[: parts.index("reports") + 1])
    return md_path.parent


def register(md_path: Path, wiki_dir: Path | None) -> int:
    fm = parse_frontmatter(md_path.read_text(encoding="utf-8"))
    if not fm:
        print("❌ 無 frontmatter，請先通過 report_lint")
        return 1

    root = reports_root(md_path)
    f = fm.get("findings") or {}
    row = " | ".join([
        str(fm.get("date", "")), str(fm.get("type", "")), str(fm.get("subject", "")),
        str(fm.get("verdict", "")),
        str(f.get("p0", 0)), str(f.get("p1", 0)), str(f.get("p2", 0)),
        str(fm.get("score", "-")),
        md_path.as_posix(),
    ])

    # 1. log.md append-only
    log = root / "log.md"
    header = "date | type | subject | verdict | p0 | p1 | p2 | score | path\n"
    if not log.exists():
        log.write_text("# Reports Log（append-only，CollectorRunner 解析用）\n\n" + header, encoding="utf-8")
    existing = log.read_text(encoding="utf-8")
    if md_path.as_posix() in existing:
        print(f"ℹ log.md 已含此報告，略過 append")
    else:
        log.write_text(existing + row + "\n", encoding="utf-8")
        print(f"✅ log.md 已追加：{row}")

    # 2. _index.md 重建（由 log 聚合，依 type 分組、日期倒序）
    index = root / "_index.md"
    entries: dict[str, list[str]] = {}
    for line in log.read_text(encoding="utf-8").splitlines():
        cols = [c.strip() for c in line.split("|")]
        if len(cols) != 9 or cols[0] == "date" or not re.match(r"\d{4}-\d{2}-\d{2}", cols[0]):
            continue
        entries.setdefault(cols[1], []).append(line.strip())
    lines = ["# Reports Index", ""]
    for rtype in sorted(entries):
        lines += [f"## {rtype}", "", "| 日期 | subject | verdict | P0/P1/P2 | 報告 |", "|---|---|---|---|---|"]
        for e in sorted(entries[rtype], reverse=True):
            c = [x.strip() for x in e.split("|")]
            lines.append(f"| {c[0]} | {c[2]} | {c[3]} | {c[4]}/{c[5]}/{c[6]} | [{Path(c[8]).name}]({c[8]}) |")
        lines.append("")
    index.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ _index.md 已重建（{sum(len(v) for v in entries.values())} 筆）")

    # 3. wiki source 建議（只建議不動手）
    if wiki_dir:
        subject = str(fm.get("subject", ""))
        tags = fm.get("tags") or []
        hits: list[Path] = []
        for page in (wiki_dir / "wiki").rglob("*.md"):
            text = page.read_text(encoding="utf-8", errors="ignore")
            if subject and subject in text or any(f"- {t}" in text or f"[{t}" in text for t in tags):
                hits.append(page)
        print("\n📎 wiki source 建議（人工確認後將報告路徑加入頁面 frontmatter 的 sources）：")
        if hits:
            for h in hits[:5]:
                print(f"   - {h.relative_to(wiki_dir)}")
        else:
            print(f"   - 無現有頁面命中 subject/tags；若主題重要，建議由 wiki-engine 以本報告為 source 開新 synthesis 頁")

    return 0


def main() -> int:
    args = sys.argv[1:]
    wiki_dir: Path | None = None
    if "--wiki" in args:
        idx = args.index("--wiki")
        wiki_dir = Path(args[idx + 1])
        args = args[:idx] + args[idx + 2:]
    if not args:
        print(__doc__)
        return 1
    return register(Path(args[0]), wiki_dir)


if __name__ == "__main__":
    sys.exit(main())
