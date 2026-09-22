#!/usr/bin/env python3
"""wrapup_check.py — 收尾前盤點（唯讀，只列不改）

Usage:
    python wrapup_check.py <workspace> --todos     # 列計畫檔中的未勾項目 `- [ ]`
    python wrapup_check.py <workspace> --drift     # 頂層目錄/scripts 未出現在 AGENTS.md / index.md / README 的清單
    python wrapup_check.py <workspace> --all       # 兩者 + memory.md 大小

exit：0 無發現；1 有發現（advisory，交 LLM 判斷）。--todos 掃描：task_plan.md、plan.md、TODO.md、docs/**/*.md
"""
import sys

if __name__ == "__main__" and ({"-h", "--help"} & set(sys.argv[1:]) or len(sys.argv) < 3):
    print(__doc__ or "")
    raise SystemExit(0)

import re
from pathlib import Path

PLAN_FILES = ["task_plan.md", "plan.md", "TODO.md", "todo.md"]
DOC_FILES = ["AGENTS.md", "index.md", "README.md", "readme.md", "knowledge/shared/index.md", ".kiro/steering/AGENTS.md"]
IGNORE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".kiro", ".pytest_cache", "dist", "build", ".mypy_cache"}


def find_todos(ws: Path) -> list[str]:
    hits = []
    files = [ws / f for f in PLAN_FILES if (ws / f).exists()]
    files += list((ws / "docs").rglob("*.md")) if (ws / "docs").exists() else []
    for f in files:
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if re.match(r"\s*[-*]\s+\[ \]", line):
                hits.append(f"{f.relative_to(ws)}:{i}  {line.strip()[:90]}")
    return hits


def find_drift(ws: Path) -> list[str]:
    docs = "\n".join((ws / f).read_text(encoding="utf-8", errors="ignore") for f in DOC_FILES if (ws / f).exists())
    if not docs.strip():
        return ["（找不到 AGENTS.md / index.md / README —— 無索引可比對）"]
    hits = []
    for d in sorted(p for p in ws.iterdir() if p.is_dir() and p.name not in IGNORE_DIRS and not p.name.startswith(".")):
        if d.name not in docs:
            hits.append(f"目錄 {d.name}/ 未出現在任何索引/規範檔")
    scripts = ws / "scripts"
    if scripts.exists():
        for s in sorted(scripts.glob("*.py")):
            if s.name not in docs and s.stem not in docs:
                hits.append(f"scripts/{s.name} 未出現在任何索引/規範檔")
    return hits


def main() -> int:
    ws = Path(sys.argv[1]).resolve()
    flags = set(sys.argv[2:])
    do_todos = "--todos" in flags or "--all" in flags
    do_drift = "--drift" in flags or "--all" in flags
    found = 0
    if do_todos:
        t = find_todos(ws)
        print(f"── 未勾 todo：{len(t)}")
        for h in t: print("   " + h)
        found += len(t)
    if do_drift:
        d = find_drift(ws)
        print(f"── 索引漂移：{len(d)}")
        for h in d: print("   " + h)
        found += len(d)
    if "--all" in flags:
        mem = ws / "memory" / "memory.md"
        if mem.exists():
            from memory_optimize import estimate_tokens  # 同目錄
            print(f"── memory.md ≈ {estimate_tokens(mem.read_text(encoding='utf-8', errors='ignore'))} tokens")
    return 1 if found else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
