#!/usr/bin/env python3
"""memory_check.py — MEMORY.md 守門與里程碑輪替（ark-agent-init 2.9.0；規格 references/memory-architecture.md §2.1、§6）。

為什麼要腳本：舊規範只寫「里程碑加一行」，沒有「什麼時候移出去」，也沒有長度上限 ——
always-on 的 MEMORY.md 遷移後四週從 8 KB 長回 34 KB（fish-bot 2026-11-13，里程碑 101 行佔 76%）；
`build_kiro.py --validate` 原本只數 `## YYYY-MM-DD` 分節，抓不到 `- **日期**` 清單式里程碑。
原型：fish-bot `scripts/memory_check.py`（D-254），本檔一般化（佈局自動判斷、蒸餾新鮮度警告）。

用法（在 agent 工作目錄，`dir="."` 的 manager 就是專案根）：
    python3 memory_check.py                 # 檢查：超標 → rc=1（加里程碑前、收尾時跑）
    python3 memory_check.py --rotate        # 窗口外的里程碑依月份 append 到 memory/archive/YYYY-MM.md（冪等、位元組核對）
    python3 memory_check.py --selftest      # 反證：超標必紅、輪替不丟內容、重跑不重複
    python3 memory_check.py --root agents/x --json
上限（問題 → rc=1）：整檔 ≤ 20 KB、里程碑 ≤ 20 行、每行 ≤ 160 字、待辦 ≤ 15 項、`## YYYY-MM-DD` 分節 ≤ 5
警告（不影響 rc）：`memory/memory.md` 仍是骨架或超過 14 天沒更新 → 蒸餾沒在跑，持久事實會回流 MEMORY.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

MAX_BYTES = 20 * 1024        # 整檔（always-on 注入）
MAX_MILESTONES = 20          # 里程碑窗口：最近 20 行
MAX_LINE = 160               # 每行字元數（日期＋一句結論＋指路）
MAX_TODO = 15                # 待辦項數
MAX_DATED_SECTIONS = 5       # `## YYYY-MM-DD` 事件分節
DISTILL_STALE_DAYS = 14
MILESTONE_HEAD = re.compile(r"(?m)^## (?:📌 )?近期里程碑.*$")
TODO_HEAD = re.compile(r"(?m)^## (?:📋 )?待辦.*$")
MILESTONE = re.compile(r"^- \*\*(\d{4})-(\d{2})-(\d{2})\*\*")
SECTION = re.compile(r"(?m)^## ")
DATED_SECTION = re.compile(r"(?m)^## (?:✅ |🧭 )?\d{4}-\d{2}-\d{2}")
SKELETON_MARK = "（待蒸餾）"


def memory_md(root: Path) -> Path:
    """佈局判斷：有 `.ark/ark.yaml` → `.ark/brain/MEMORY.md`；否則 `.kiro/steering/MEMORY.md`。"""
    if (root / ".ark" / "ark.yaml").is_file():
        return root / ".ark" / "brain" / "MEMORY.md"
    return root / ".kiro" / "steering" / "MEMORY.md"


def split_section(text: str, head: re.Pattern) -> tuple[int, int] | None:
    """某個 `## ` 分節的內文 [start, end)（不含標題行）。"""
    m = head.search(text)
    if not m:
        return None
    start = m.end() + 1
    nxt = SECTION.search(text, start)
    return start, (nxt.start() if nxt else len(text))


def mdate(line: str) -> tuple[str, str, str]:
    m = MILESTONE.match(line)
    return (m.group(1), m.group(2), m.group(3)) if m else ("0000", "00", "00")


def milestones(text: str) -> list[str]:
    span = split_section(text, MILESTONE_HEAD)
    if not span:
        return []
    return [ln for ln in text[span[0]:span[1]].splitlines() if MILESTONE.match(ln)]


def problems(text: str) -> list[str]:
    """MEMORY.md 內容 → 違規清單（空＝通過）。每條都說要怎麼改。"""
    out = []
    size = len(text.encode("utf-8"))
    if size > MAX_BYTES:
        out.append(f"整檔 {size / 1024:.1f} KB > {MAX_BYTES // 1024} KB（always-on 注入）—— 跑 --rotate，長內容移到 archive／decision-log")
    if not MILESTONE_HEAD.search(text):
        if any(MILESTONE.match(ln) for ln in text.splitlines()):
            out.append("有 `- **YYYY-MM-DD**` 里程碑，但不在「## 📌 近期里程碑」分節 —— 守門讀不到，把它們移進該分節")
    ms = milestones(text)
    if len(ms) > MAX_MILESTONES:
        out.append(f"里程碑 {len(ms)} 行 > {MAX_MILESTONES} —— 跑 --rotate（舊的 append 到 memory/archive/）")
    for ln in ms:
        if len(ln) > MAX_LINE:
            out.append(f"里程碑一行 {len(ln)} 字 > {MAX_LINE}：{ln[:40]}… —— 只留一句結論＋指路，細節移到 daily／archive")
    todo = split_section(text, TODO_HEAD)
    if todo:
        n = sum(1 for ln in text[todo[0]:todo[1]].splitlines() if ln.strip().startswith("- ["))
        if n > MAX_TODO:
            out.append(f"待辦 {n} 項 > {MAX_TODO} —— 完成的刪掉，細節放計畫文件、這裡一行指路")
    dated = len(DATED_SECTION.findall(text))
    if dated > MAX_DATED_SECTIONS:
        out.append(f"{dated} 個日期事件分節（`## YYYY-MM-DD`）> {MAX_DATED_SECTIONS} —— 事件流水屬於 memory/daily、archive")
    return out


def distill_warning(root: Path, now: float | None = None) -> str | None:
    """持久事實層健康度：骨架未填或久未更新 → 一行警告；檔案不存在回 None（由骨架守門負責）。"""
    mm = root / "memory" / "memory.md"
    if not mm.is_file():
        return None
    age = ((now or time.time()) - mm.stat().st_mtime) / 86400
    skeleton = SKELETON_MARK in mm.read_text(encoding="utf-8", errors="replace")
    if age > DISTILL_STALE_DAYS or (skeleton and age > 1):
        why = "仍是骨架" if skeleton else f"{age:.0f} 天沒更新"
        return (f"memory/memory.md {why} —— 蒸餾（memory-distill）沒在跑，持久事實會回流 MEMORY.md；"
                "確認 daemon 與 scheduler.yaml，IDE-only workspace 把長期事實寫進 BRAIN 或「🔒 常駐定案」")
    return None


def rotate(mem: Path, archive: Path, keep: int = MAX_MILESTONES) -> int:
    """最舊的里程碑（窗口外）依月份 append 到 archive/YYYY-MM.md，再從 MEMORY.md 移除；回傳搬了幾行。"""
    text = mem.read_text(encoding="utf-8")
    ms = milestones(text)
    if len(ms) <= keep:
        return 0
    move = set(sorted(ms, key=mdate, reverse=True)[keep:])
    by_month: dict[str, list[str]] = defaultdict(list)
    for ln in ms:                                        # 保留原順序
        if ln in move:
            y, m, _ = mdate(ln)
            by_month[f"{y}-{m}"].append(ln)
    archive.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    for month, lines in sorted(by_month.items()):
        t = archive / f"{month}.md"
        before = t.read_bytes() if t.exists() else b""
        new = [ln for ln in lines if ln.encode("utf-8") not in before]    # 冪等
        if not new:
            continue
        head = b"" if before else f"# 記憶歸檔 {month}\n\n> append-only。\n".encode()
        add = (f"\n## 里程碑索引（自 MEMORY.md 輪替，{today}）\n\n" + "\n".join(new) + "\n").encode("utf-8")
        t.write_bytes(before + head + add)
        if t.stat().st_size != len(before) + len(head) + len(add):
            raise SystemExit(f"❌ {t} 位元組核對失敗 —— 停止，未改 MEMORY.md")
    kept = [ln for ln in text.splitlines(keepends=True) if ln.rstrip("\n") not in move]
    mem.write_text("".join(kept), encoding="utf-8")
    return len(move)


def selftest() -> int:
    """反證：超標必紅、輪替不丟內容、重跑不重複、里程碑跑出分節必紅、蒸餾久未更新必警告。"""
    ok = True
    good = "# x\n\n## 📌 近期里程碑\n\n" + "".join(f"- **2026-11-{d:02d}** 結論 {d}\n" for d in range(1, 11)) + "\n## 待辦\n\n- [ ] a\n"
    ok &= problems(good) == []
    bad_many = good.replace("## 待辦", "".join(f"- **2026-10-{d:02d}** 舊 {d}\n" for d in range(1, 21)) + "\n## 待辦")
    ok &= any("里程碑 30 行" in p for p in problems(bad_many))
    ok &= any("字 >" in p for p in problems(good.replace("結論 1\n", "結論" + "長" * 200 + "\n")))
    ok &= any("KB" in p for p in problems(good + "x" * MAX_BYTES))
    ok &= any("不在" in p for p in problems("# x\n- **2026-11-01** a\n"))
    ok &= any("待辦" in p for p in problems(good + "".join(f"- [ ] t{i}\n" for i in range(20))))
    with tempfile.TemporaryDirectory() as d:
        mem, arc = Path(d) / "MEMORY.md", Path(d) / "archive"
        mem.write_text(bad_many, encoding="utf-8")
        n = rotate(mem, arc)
        after = mem.read_text(encoding="utf-8")
        moved = (arc / "2026-10.md").read_text(encoding="utf-8")
        ok &= n == 10 and len(milestones(after)) == MAX_MILESTONES and problems(after) == []
        ok &= all(f"- **2026-10-{d:02d}** 舊 {d}" in moved for d in range(1, 11))
        mem.write_text(bad_many, encoding="utf-8")
        rotate(mem, arc)
        ok &= (arc / "2026-10.md").read_text(encoding="utf-8").count("- **2026-10-01**") == 1
        root = Path(d) / "ws"
        (root / "memory").mkdir(parents=True)
        (root / "memory" / "memory.md").write_text("## 環境慣例\n- x\n", encoding="utf-8")
        ok &= distill_warning(root) is None
        ok &= distill_warning(root, now=time.time() + 30 * 86400) is not None
    print("selftest", "✅" if ok else "❌")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MEMORY.md 守門與里程碑輪替")
    ap.add_argument("--root", type=Path, default=Path("."), help="agent 工作目錄（預設目前目錄）")
    ap.add_argument("--file", type=Path, help="MEMORY.md 路徑（預設依佈局）")
    ap.add_argument("--rotate", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    root = a.root.resolve()
    mem = a.file or memory_md(root)
    if not mem.is_file():
        print(f"❌ 找不到 {mem}", file=sys.stderr)
        return 2
    moved = rotate(mem, root / "memory" / "archive") if a.rotate else 0
    text = mem.read_text(encoding="utf-8")
    probs, warn = problems(text), distill_warning(root)
    if a.json:
        print(json.dumps({"file": str(mem), "bytes": len(text.encode()), "milestones": len(milestones(text)),
                          "rotated": moved, "problems": probs, "warnings": [warn] if warn else []}, ensure_ascii=False))
    else:
        if a.rotate:
            print(f"• 輪替 {moved} 行里程碑 → memory/archive/")
        print(f"{mem.name} {len(text.encode()) / 1024:.1f} KB｜里程碑 {len(milestones(text))} 行")
        for p in probs:
            print("❌", p)
        if warn:
            print("⚠️", warn)
        if not probs:
            print("✅ 通過")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
