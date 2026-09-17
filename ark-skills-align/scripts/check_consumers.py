#!/usr/bin/env python3
"""check_consumers.py — thin wrapper（skills-align v2 C 項:腳本歸位）。

實體在 repo 根 `scripts/check_consumers.py`（那裡的 `Path(__file__).parent.parent`
才指得到 skill 庫根;搬進本目錄會多一層而指錯，已反證）。

保留根檔案的理由:
- 消費端 8 個 wrapper（各專案 doctor.sh / check_skills_residue.sh）寫死
  `$HOME/kiro-cli/.kiro/skills/scripts/check_consumers.py`，在別的 repo 不能一起改
- 本 wrapper 讓 SKILL.md 的 `ark-skills-align/scripts/check_consumers.py` 指向成立

用法與根檔案完全一致（argv 原封轉發）。
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_REAL = Path(__file__).resolve().parent.parent.parent / "scripts" / "check_consumers.py"

if __name__ == "__main__":
    if not _REAL.exists():
        sys.exit(f"找不到實體腳本:{_REAL}（repo 根 scripts/ 下）")
    sys.argv[0] = str(_REAL)
    runpy.run_path(str(_REAL), run_name="__main__")
