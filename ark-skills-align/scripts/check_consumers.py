#!/usr/bin/env python3
"""轉呼檔（ark-skills-align 已於 2026-11-13 併入 ark-skills-sync）—— argv 原封轉給 ark-skills-sync/scripts/check_consumers.py。"""
import runpy
import sys
from pathlib import Path

_REAL = Path(__file__).resolve().parent.parent.parent / "ark-skills-sync" / "scripts" / "check_consumers.py"
if __name__ == "__main__":
    if not _REAL.exists():
        sys.exit(f"找不到 {_REAL}：請先安裝 ark-skills-sync（ark-skills-align 已併入）")
    sys.path.insert(0, str(_REAL.parent))
    sys.argv[0] = str(_REAL)
    runpy.run_path(str(_REAL), run_name="__main__")
