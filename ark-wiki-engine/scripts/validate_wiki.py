#!/usr/bin/env python3
"""validate_wiki.py — 知識庫骨架驗證（v3）

    python validate_wiki.py <project_dir> [--json]

等同 `python build_wiki.py --validate <project_dir>` 的快捷入口。
驗 `knowledge/*/` 的四個必要檔案，以及（若存在）`.index/manifest.json`
的 `tokenizer` / `bm25_backend` 是否為合法值。

v2 驗的是 23 個模板檔（`src/skills/wiki_skills/*` 等），那些 v3 已不再產出
→ 照舊會永遠 missing 21 個。**驗一個不該存在的東西，比不驗更糟。**
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _wikilib import ErrorCode, emit_error, emit_json  # noqa: E402
from build_wiki import validate_wiki  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="知識庫骨架驗證（v3）")
    p.add_argument("project_dir", help="專案根目錄（其下應有 knowledge/）")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    project_dir = Path(args.project_dir)
    if not project_dir.is_dir():
        emit_error(ErrorCode.WIKI_DIR_NOT_FOUND, f"目錄不存在：{project_dir}")

    found, missing = validate_wiki(project_dir)
    total = len(found) + len(missing)
    if args.json:
        emit_json({"ok": not missing, "action": "validate", "checked": total,
                   "found": found, "missing": missing}, 1 if missing else 0)

    if missing:
        print(f"❌ 驗證失敗：{len(found)}/{total}，缺 {len(missing)} 個\n")
        print("缺失檔案：")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)
    print(f"✅ 驗證通過：{total}/{total}")


if __name__ == "__main__":
    main()
