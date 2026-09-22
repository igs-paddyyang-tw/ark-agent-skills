#!/usr/bin/env python3
"""memory_optimize.py — memory/ 的量測與搬運（判斷交給 LLM，這裡只做確定性的事）

Usage:
    python memory_optimize.py <workspace> daily "<≤150 字紀錄>"      # 追加 memory/daily/YYYY-MM-DD.md
    python memory_optimize.py <workspace> check [--limit 2000]       # 估 memory.md tokens；超限 exit 2
    python memory_optimize.py <workspace> archive <段落檔>           # 段落原文 → memory/archive/memory-archive-YYYY-MM-DD.md

規則（對齊 BRAIN.md）：
    - daily 一筆 ≤150 字（CJK 字元 + 英文單字合計），超長拒收 exit 1
    - memory.md 上限約 2000 tokens（估算：CJK 每字 1、ASCII 每單字 1.3）
    - archive 只追加不覆寫；memory.md 末尾留指針行；daily/ 與 archive/ 永不刪
"""
import sys

if __name__ == "__main__" and ({"-h", "--help"} & set(sys.argv[1:]) or len(sys.argv) < 3):
    print(__doc__ or "")
    raise SystemExit(0)

import re
from datetime import date
from pathlib import Path

DAILY_LIMIT = 150
CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]")


def count_units(text: str) -> int:
    cjk = len(CJK.findall(text))
    ascii_words = len(re.findall(r"[A-Za-z0-9_./-]+", text))
    return cjk + ascii_words


def estimate_tokens(text: str) -> int:
    cjk = len(CJK.findall(text))
    ascii_words = len(re.findall(r"[A-Za-z0-9_./-]+", text))
    return int(cjk + ascii_words * 1.3)


def cmd_daily(ws: Path, text: str) -> int:
    n = count_units(text)
    if n > DAILY_LIMIT:
        print(f"❌ daily 紀錄 {n} 字，超過 {DAILY_LIMIT}；請精簡（明細寫 docs/ 或 wiki，這裡只留結論）")
        return 1
    today = date.today().isoformat()
    d = ws / "memory" / "daily"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{today}.md"
    header = f"# {today}\n\n" if not f.exists() else ""
    with f.open("a", encoding="utf-8") as fh:
        fh.write(f"{header}- {text.strip()}\n")
    print(f"✅ 追加 {f.relative_to(ws)}（{n} 字）")
    return 0


def cmd_check(ws: Path, limit: int) -> int:
    f = ws / "memory" / "memory.md"
    if not f.exists():
        print("⚠️  memory/memory.md 不存在（尚未建立長期記憶）")
        return 0
    text = f.read_text(encoding="utf-8", errors="ignore")
    tokens = estimate_tokens(text)
    lines = text.count("\n")
    over = tokens > limit
    mark = "❌" if over else "✅"
    print(f"{mark} memory.md ≈ {tokens} tokens（{lines} 行，上限 {limit}）")
    if over:
        print(f"   → 超出 {tokens - limit}，請將歷史/明細段落歸檔：memory_optimize.py archive <段落檔>")
        return 2
    return 0


def cmd_archive(ws: Path, chunk_file: Path) -> int:
    if not chunk_file.exists():
        print(f"❌ 段落檔不存在：{chunk_file}")
        return 1
    chunk = chunk_file.read_text(encoding="utf-8").strip()
    if not chunk:
        print("❌ 段落檔為空")
        return 1
    today = date.today().isoformat()
    arch_dir = ws / "memory" / "archive"
    arch_dir.mkdir(parents=True, exist_ok=True)
    arch = arch_dir / f"memory-archive-{today}.md"
    header = f"# memory archive {today}\n\n" if not arch.exists() else "\n\n---\n\n"
    with arch.open("a", encoding="utf-8") as fh:
        fh.write(header + chunk + "\n")

    mem = ws / "memory" / "memory.md"
    if mem.exists():
        text = mem.read_text(encoding="utf-8")
        if chunk in text:
            text = text.replace(chunk, "").rstrip() + "\n"
        pointer = f"- 歷史明細見 `memory/archive/memory-archive-{today}.md`"
        if pointer not in text:
            text += f"\n{pointer}\n"
        mem.write_text(text, encoding="utf-8")
        print(f"✅ 已歸檔 → {arch.relative_to(ws)}；memory.md 移除原段落並留指針")
    else:
        print(f"✅ 已歸檔 → {arch.relative_to(ws)}（memory.md 不存在，未改）")
    return 0


def main() -> int:
    ws = Path(sys.argv[1]).resolve()
    cmd = sys.argv[2]
    rest = sys.argv[3:]
    if cmd == "daily":
        if not rest:
            print("❌ 缺紀錄文字"); return 1
        return cmd_daily(ws, " ".join(rest))
    if cmd == "check":
        limit = 2000
        if "--limit" in rest:
            limit = int(rest[rest.index("--limit") + 1])
        return cmd_check(ws, limit)
    if cmd == "archive":
        if not rest:
            print("❌ 缺段落檔路徑"); return 1
        return cmd_archive(ws, Path(rest[0]))
    print(f"❌ 未知子命令：{cmd}（daily | check | archive）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
