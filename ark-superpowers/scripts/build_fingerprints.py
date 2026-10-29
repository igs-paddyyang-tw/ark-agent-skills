#!/usr/bin/env python3
"""build_fingerprints.py — 掃 templates/** 產 fingerprints.json（ADR-001 SP-001）。

模板指紋 = 每個模板的每一行（含表格 cell）正規化後的 sha1。
doc_lint 的 SP-001 用它偵測「產物某一行還是模板原文」（模板殘留）。

正規化：去前後空白、摺疊內部空白、去大小寫、去尾標點。
兩個粒度：整行 + 表格 cell（`|` 分隔），因為使用者常只改一格 cell。

輸出：{"version": 1, "generated": "<date>", "lines": [sha1...], "cells": [sha1...]}
CI 與 self_check.sh 執行；doc_lint 啟動時比對模板 mtime，指紋落後即要求重建（不靜默用舊指紋）。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
TEMPLATES_DIR = SKILL_ROOT / "references" / "templates"
FINGERPRINTS = SKILL_ROOT / "references" / "fingerprints.json"

# 這些行不進指紋（結構性、非模板獨有內容）
_SKIP_RE = re.compile(r"^\s*(---|#{1,6}\s|\||```|<!--|>|\d+\.|\-|\*)?\s*$")
# 太短的行不進指紋（避免誤判通用短語）
_MIN_LEN = 8


def normalize(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".,;:。，；：")
    return s


def _sha(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def collect(templates_dir: Path) -> tuple[set[str], set[str]]:
    lines: set[str] = set()
    cells: set[str] = set()
    for md in sorted(templates_dir.rglob("*.md")):
        for raw in md.read_text(encoding="utf-8").splitlines():
            # cell 粒度：表格列
            if "|" in raw:
                for cell in raw.split("|"):
                    n = normalize(cell)
                    if len(n) >= _MIN_LEN and "{" not in n:  # 含 placeholder 的不當指紋（本就要填）
                        cells.add(_sha(n))
            # line 粒度：實質內容行
            n = normalize(raw)
            if len(n) >= _MIN_LEN and not _SKIP_RE.match(raw) and "{" not in n:
                lines.add(_sha(n))
    return lines, cells


def build() -> dict:
    lines, cells = collect(TEMPLATES_DIR)
    return {"version": 1, "generated": str(date.today()),
            "lines": sorted(lines), "cells": sorted(cells)}


def _without_date(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "generated"}


def main() -> int:
    """重產 fingerprints.json；內容（不含 generated 日期）沒變就不寫檔。

    🔴 2026-10-29：原本不解析參數，連 `--help` 都會重寫這個被追蹤的檔（只差日期）→
       每跑一次 CLI 契約測試就弄髒工作樹，manifest 也會記到被改過的 tree_hash。
    """
    import argparse
    ap = argparse.ArgumentParser(description="掃 templates/** 產 references/fingerprints.json（內容沒變不寫檔）")
    ap.add_argument("--check", action="store_true", help="只檢查是否過期：過期 exit 1，不寫檔")
    args = ap.parse_args()
    data = build()
    if FINGERPRINTS.exists():
        try:
            old = json.loads(FINGERPRINTS.read_text(encoding="utf-8"))
        except ValueError:
            old = {}
        if _without_date(old) == _without_date(data):
            print(f"✅ fingerprints.json 已是最新（{len(data['lines'])} 行指紋 + {len(data['cells'])} cell 指紋），未寫檔")
            return 0
    if args.check:
        print("❌ fingerprints.json 過期：請執行 python scripts/build_fingerprints.py")
        return 1
    FINGERPRINTS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ fingerprints.json：{len(data['lines'])} 行指紋 + {len(data['cells'])} cell 指紋")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
