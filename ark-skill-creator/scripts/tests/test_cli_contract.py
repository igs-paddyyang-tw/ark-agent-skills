#!/usr/bin/env python3
"""CLI 契約守門：ark-skill-creator 全部腳本必須遵守的兩條規則。

規則 1 — `--help` 必須零第三方依賴、exit 0：
    沒裝套件的人至少要看得到「這支怎麼用」，不能拿到 traceback。
規則 2 — help 守衛必須出現在第一個第三方 import 之前（靜態 AST 檢查）：
    守衛寫在 import 之後等於沒寫（import 先炸）。

Usage:
    python scripts/tests/test_cli_contract.py        # 全部通過 exit 0，任一違反 exit 1
"""

import ast
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__" and {"-h", "--help"} & set(sys.argv[1:]):
    print(__doc__ or "")
    raise SystemExit(0)

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent

# 受契約約束的 CLI 清單（新增腳本請加進來）
CLIS = [
    "scripts/run_eval.py",
    "scripts/run_loop.py",
    "scripts/improve_description.py",
    "scripts/aggregate_benchmark.py",
    "scripts/generate_report.py",
    "scripts/quick_validate.py",
    "scripts/package_skill.py",
    "eval-viewer/generate_review.py",
]

STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {"__future__", "scripts"}


def guard_line(tree: ast.Module) -> int | None:
    """回傳 help 守衛（含 '-h'/'--help' 集合字面值）所在行，找不到回傳 None。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Set):
            values = {c.value for c in node.elts if isinstance(c, ast.Constant)}
            if {"-h", "--help"} <= values:
                return node.lineno
    return None


def first_third_party_import_line(tree: ast.Module) -> int | None:
    """回傳模組頂層第一個第三方 import 的行號（只看 module-level，函式內延遲 import 不算）。"""
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in STDLIB:
                    return node.lineno
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] not in STDLIB:
                return node.lineno
    return None


def main() -> int:
    failures: list[str] = []
    for rel in CLIS:
        path = SKILL_ROOT / rel
        if not path.exists():
            failures.append(f"{rel}: 檔案不存在（CLIS 清單過期？）")
            continue

        # 規則 1：--help exit 0
        proc = subprocess.run(
            [sys.executable, str(path), "--help"],
            capture_output=True, text=True, timeout=30, cwd=SKILL_ROOT,
        )
        if proc.returncode != 0:
            failures.append(f"{rel}: --help exit {proc.returncode}（{(proc.stderr or '').strip().splitlines()[-1:]}）")

        # 規則 2：守衛先於第三方 import
        tree = ast.parse(path.read_text(encoding="utf-8"))
        g, imp = guard_line(tree), first_third_party_import_line(tree)
        if g is None and imp is not None:
            failures.append(f"{rel}: 有第三方 import（L{imp}）但找不到 help 守衛")
        elif g is not None and imp is not None and imp < g:
            failures.append(f"{rel}: 第三方 import（L{imp}）先於 help 守衛（L{g}）——無依賴環境 --help 會炸")

    if failures:
        print("❌ CLI 契約違反：")
        for f in failures:
            print(f"   - {f}")
        return 1
    print(f"✅ CLI 契約通過（{len(CLIS)} 支）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
