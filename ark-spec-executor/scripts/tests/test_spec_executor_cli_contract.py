#!/usr/bin/env python3
"""CLI 契約守門 + fixture 回歸：五支 --help 零依賴 exit 0；守衛先於第三方 import；三個 fixture 的 lint exit 碼。
Usage: python scripts/tests/test_spec_executor_cli_contract.py
"""
import ast, subprocess, sys
from pathlib import Path
if __name__ == "__main__" and {"-h", "--help"} & set(sys.argv[1:]):
    print(__doc__); raise SystemExit(0)
ROOT = Path(__file__).resolve().parent.parent.parent
CLIS = ["plan_lint.py", "plan_parse.py", "ac_verify.py", "run_plan.py", "report_gen.py"]
STD = set(getattr(sys, "stdlib_module_names", ())) | {"__future__", "plan_parse", "ac_verify"}
def guard(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Set) and {"-h", "--help"} <= {c.value for c in n.elts if isinstance(c, ast.Constant)}:
            return n.lineno
def first_3p(tree):
    for n in tree.body:
        names = [a.name for a in n.names] if isinstance(n, ast.Import) else ([n.module] if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module else [])
        for m in names:
            if m.split(".")[0] not in STD: return n.lineno
fails = []
for rel in CLIS:
    p = ROOT / "scripts" / rel
    r = subprocess.run([sys.executable, str(p), "--help"], capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0: fails.append(f"{rel}: --help exit {r.returncode}")
    t = ast.parse(p.read_text(encoding="utf-8")); g, i = guard(t), first_3p(t)
    if i is not None and (g is None or i < g): fails.append(f"{rel}: 第三方 import L{i} 先於守衛")
for fx, want in [("plan-valid", 0), ("plan-cycle", 2), ("plan-badrole", 2)]:
    r = subprocess.run([sys.executable, str(ROOT / "scripts/plan_lint.py"), str(ROOT / "tests/fixtures" / f"{fx}.md")], capture_output=True, text=True)
    if r.returncode != want: fails.append(f"fixture {fx}: lint exit {r.returncode} ≠ {want}")
print("❌\n   " + "\n   ".join(fails) if fails else f"✅ CLI 契約 + fixture 回歸通過（{len(CLIS)} 支 / 3 fixtures）")
raise SystemExit(1 if fails else 0)
