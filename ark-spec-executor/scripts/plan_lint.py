#!/usr/bin/env python3
"""plan_lint.py — plan.md 契約 lint（ark-superpowers doc_lint SP-070 的委派端）

Usage:
    python plan_lint.py <plan.md> [--json]

規則（PL = plan-lint）：
    PL-001 P0  任務表缺失 / 欄數非 7 或 4 / 欄數與表頭不符
    PL-002 P0  任務編號格式、重複；依賴指向不存在的任務；循環依賴
    PL-003 P0  角色非 coder|ai-dev|qa|human
    PL-004 P1  AC-ID 格式錯 / 重複 / 7 欄表缺 AC-ID
    PL-005 P1  產出檔案為空或含佔位符 {…} / TBD / TODO
    PL-006 P2  AC 文字無 verify 提示且無法自動推斷（將以 manual 處理，不算通過）
    PL-007 P1  human 任務無 AC 說明「人工確認什麼」

exit：0 無 P0/P1；1 有 P1（可執行但建議修）；2 有 P0（骨架 FAIL，executor 拒跑）
"""
import sys

if __name__ == "__main__" and ({"-h", "--help"} & set(sys.argv[1:]) or len(sys.argv) < 2):
    print(__doc__ or "")
    raise SystemExit(0)

import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_parse import load_plan  # noqa: E402

PLACEHOLDER = re.compile(r"\{[^}]*\}|\bTBD\b|\bTODO\b|（待填）|\[NEEDS CLARIFICATION\]")
AUTO_KEYS = ("檔案", "存在", "建立", "import", "載入", "測試", "test", "pytest", "pass")


def lint(plan: Path) -> list[dict]:
    res = load_plan(plan)
    findings = []
    for e in res["errors"]:
        code = "PL-003" if "角色" in e else "PL-004" if "AC-ID" in e else "PL-002" if any(k in e for k in ("編號", "依賴", "循環")) else "PL-001"
        sev = "P1" if code == "PL-004" else "P0"
        findings.append({"code": code, "severity": sev, "msg": e})
    for t in res["tasks"]:
        loc = f"{t['id']} L{t['line']}"
        if not t["output_file"] or PLACEHOLDER.search(t["output_file"]):
            findings.append({"code": "PL-005", "severity": "P1", "msg": f"{loc}: 產出檔案為空或含佔位符 '{t['output_file']}'"})
        if t["role"] != "human" and not t["ac_id"] and len(res["tasks"]) and "AC-ID" in plan.read_text(encoding="utf-8"):
            findings.append({"code": "PL-004", "severity": "P1", "msg": f"{loc}: 7 欄表缺 AC-ID"})
        if t["role"] == "human" and len(t["ac"].strip()) < 4:
            findings.append({"code": "PL-007", "severity": "P1", "msg": f"{loc}: human 任務需在 AC 說明要人工確認什麼"})
        if t["role"] != "human" and not t["verify_hint"] and not any(k in t["ac"].lower() for k in AUTO_KEYS) and not t["output_file"].startswith("tests/"):
            findings.append({"code": "PL-006", "severity": "P2", "msg": f"{loc}: AC 無 verify 提示且無法推斷，將以 manual 處理（不算通過）"})
    return findings


def main() -> int:
    plan = Path(sys.argv[1])
    if not plan.exists():
        print(f"❌ 找不到 {plan}"); return 2
    findings = lint(plan)
    sev = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        sev[f["severity"]] += 1
    if "--json" in sys.argv:
        print(json.dumps({"plan": str(plan), "findings": findings, "summary": sev}, ensure_ascii=False, indent=1))
    else:
        for f in findings:
            print(f"[{f['severity']}] {f['code']} {f['msg']}")
        mark = "❌" if sev["P0"] else "⚠️" if sev["P1"] else "✅"
        print(f"\n{mark} plan-lint {plan.name} · P0:{sev['P0']} P1:{sev['P1']} P2:{sev['P2']}")
    return 2 if sev["P0"] else 1 if sev["P1"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
