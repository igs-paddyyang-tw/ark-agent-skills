#!/usr/bin/env python3
"""pack_new — 從 _template 建立新 domain pack 骨架，並回傳「還要補什麼」的 checklist。

用法:
  python pack_new.py --domain mahjong-game --display-name 麻將
新 domain 在 pack_lint 綠燈之前不算存在。
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pack_common as P  # noqa: E402
import pack_lint  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="scaffold a new domain pack")
    ap.add_argument("--domain", required=True, help="kebab-case，建議 <domain>-game")
    ap.add_argument("--display-name", required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    root = P.domains_dir()
    dst = root / a.domain
    if not a.domain.replace("-", "").isalnum() or a.domain.startswith("_"):
        P.fail("BAD_INPUT", "domain 名需 kebab-case 且不以 _ 開頭", "例: mahjong-game")
    if dst.exists() and not a.force:
        P.fail("BAD_INPUT", f"{dst} 已存在", "加 --force 覆寫（會刪除既有內容）")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(root / "_template", dst)
    for p in dst.rglob("*"):
        if p.is_file():
            t = p.read_text(encoding="utf-8").replace("__DOMAIN__", a.domain).replace("__DISPLAY_NAME__", a.display_name)
            p.write_text(t, encoding="utf-8")
    vs = pack_lint.lint_domain(a.domain, root)
    P.emit({"created": str(dst),
            "checklist": [f"[{x['severity']}] {x['rule']}: {x['message']}" for x in vs],
            "next": f"編輯 {dst} 後執行 python scripts/pack_lint.py --domain {a.domain}"})


if __name__ == "__main__":
    main()
