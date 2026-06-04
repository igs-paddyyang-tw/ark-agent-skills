#!/usr/bin/env python3
"""validate_wiki.py — Wiki 知識庫引擎產出驗證腳本。

快捷驗證入口，等同 `python build_wiki.py --validate <dir>`。

Usage:
    python validate_wiki.py <project_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

# Import from sibling
sys.path.insert(0, str(Path(__file__).parent))
from build_wiki import validate_wiki


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python validate_wiki.py <project_dir>")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    if not project_dir.is_dir():
        print(f"❌ 目錄不存在: {project_dir}")
        sys.exit(1)

    found, missing = validate_wiki(project_dir)
    total = len(found) + len(missing)

    if not missing:
        print(f"✅ 驗證通過：{total}/{total} 個 Wiki 引擎檔案皆已產出")
        sys.exit(0)
    else:
        print(f"❌ 驗證失敗：{len(found)}/{total}，缺 {len(missing)} 個\n")
        print("缺失檔案：")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)


if __name__ == "__main__":
    main()
