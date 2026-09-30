#!/usr/bin/env python3
"""plan_parse.py — 解析 plan.md 任務表 → tasks.json（含 DAG 執行順序）

Usage:
    python plan_parse.py <plan.md> [--out data/<name>-tasks.json] [--milestone 1] [--no-implicit-seq] [--dry-run] [--json]

契約（references/plan-contract.md）：
    7 欄 | # | 任務 | 角色 | 產出檔案 | 估時 | AC-ID | AC |     （plan-full）
    4 欄 | # | 任務 | 產出檔案 | AC |                          （plan-onepager，角色由產出路徑推斷）
    #        {milestone}.{seq}；跨 milestone 依賴在任務名尾加 [← X.Y]（同 milestone 依序號隱含依賴，--no-implicit-seq 關閉）
    角色     coder | ai-dev | qa | human（大小寫不敏感）
    AC-ID    AC-NNN 三位數，全檔唯一；AC 文字可含 verify: <method> 提示（見 references/verify-methods.md）

exit：0 解析成功；2 契約違反（缺任務表、欄數錯、角色非法、AC-ID 重複/格式錯、依賴不存在、循環依賴）——fail-closed，不產出 tasks.json
"""
import sys

if __name__ == "__main__" and ({"-h", "--help"} & set(sys.argv[1:]) or len(sys.argv) < 2):
    print(__doc__ or "")
    raise SystemExit(0)

import json
import re
from collections import defaultdict
from pathlib import Path

ROLES = {"coder", "ai-dev", "qa", "human"}
RE_ID = re.compile(r"^\d+\.\d+$")
RE_AC = re.compile(r"^AC-\d{3}$")
RE_DEP = re.compile(r"\[\s*(?:←|<-)\s*(\d+\.\d+)\s*\]")
RE_VERIFY = re.compile(r"verify:\s*([a-z_]+)(?::\s*([^;|]+))?", re.I)


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def split_row(line: str) -> list[str]:
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def infer_role(output_file: str, name: str) -> str:
    low = f"{output_file} {name}".lower()
    if "test" in low or "測試" in low:
        return "qa"
    if any(k in low for k in ("prompt", "llm", "agent", "skill")):
        return "ai-dev"
    return "coder"


def parse_tasks(text: str, implicit_seq: bool = True) -> tuple[list[dict], list[str]]:
    tasks, errors = [], []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("|"):
            header = split_row(line)
            if header and header[0] == "#" and "任務" in header[1:2]:
                ncol = len(header)
                if ncol not in (7, 4):
                    errors.append(f"L{i+1}: 任務表欄數 {ncol}，契約只接受 7 或 4")
                    i += 1; continue
                i += 2  # skip separator
                while i < len(lines) and lines[i].strip().startswith("|"):
                    cells = split_row(lines[i])
                    if len(cells) != ncol:
                        errors.append(f"L{i+1}: 欄數 {len(cells)} ≠ 表頭 {ncol}")
                        i += 1; continue
                    if ncol == 7:
                        tid, name, role, out, est, acid, ac = cells
                    else:
                        tid, name, out, ac = cells
                        role, est, acid = "", "", ""
                    if not RE_ID.match(tid):
                        errors.append(f"L{i+1}: 任務編號 '{tid}' 不符 {{milestone}}.{{seq}}")
                        i += 1; continue
                    deps = RE_DEP.findall(name)
                    name_clean = RE_DEP.sub("", name).strip()
                    out_clean = out.strip("`").strip()
                    role_n = role.lower().strip() if role else infer_role(out_clean, name_clean)
                    if role_n not in ROLES:
                        errors.append(f"L{i+1}: 角色 '{role}' 不在枚舉 {sorted(ROLES)}")
                    if acid and not RE_AC.match(acid):
                        errors.append(f"L{i+1}: AC-ID '{acid}' 不符 AC-NNN")
                    vm = RE_VERIFY.search(ac)
                    verify = {"method": vm.group(1).lower(), "arg": (vm.group(2) or "").strip()} if vm else None
                    tasks.append({
                        "id": tid, "milestone": int(tid.split(".")[0]), "seq": int(tid.split(".")[1]),
                        "name": name_clean, "role": role_n, "output_file": out_clean, "estimate": est,
                        "ac_id": acid or None, "ac": ac, "deps": deps, "verify_hint": verify, "line": i + 1,
                    })
                    i += 1
                continue
        i += 1

    if not tasks and not errors:
        errors.append("找不到任務表（表頭需為 | # | 任務 | … |）")
    ids = [t["id"] for t in tasks]
    for d in {x for x in ids if ids.count(x) > 1}:
        errors.append(f"任務編號重複：{d}")
    acids = [t["ac_id"] for t in tasks if t["ac_id"]]
    for d in {x for x in acids if acids.count(x) > 1}:
        errors.append(f"AC-ID 重複：{d}")
    idset = set(ids)
    for t in tasks:
        for d in t["deps"]:
            if d not in idset:
                errors.append(f"{t['id']} 依賴不存在的任務 {d}")
    if implicit_seq:
        by_ms = defaultdict(list)
        for t in tasks:
            by_ms[t["milestone"]].append(t)
        for ms, ts in by_ms.items():
            ts.sort(key=lambda t: t["seq"])
            for prev, cur in zip(ts, ts[1:]):
                if prev["id"] not in cur["deps"]:
                    cur["deps"].append(prev["id"])
                    cur.setdefault("implicit_deps", []).append(prev["id"])
    return tasks, errors


def topo_order(tasks: list[dict]) -> tuple[list[str], list[str]]:
    indeg = {t["id"]: 0 for t in tasks}
    graph = defaultdict(list)
    for t in tasks:
        for d in t["deps"]:
            graph[d].append(t["id"]); indeg[t["id"]] += 1
    key = {t["id"]: (t["milestone"], t["seq"]) for t in tasks}
    # 優先佇列：永遠取「可執行者中 (milestone, seq) 最小」→ milestone 優先、依賴不違反
    import heapq
    q = [(key[i], i) for i, n in indeg.items() if n == 0]; heapq.heapify(q)
    order = []
    while q:
        _, n = heapq.heappop(q); order.append(n)
        for m in graph[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                heapq.heappush(q, (key[m], m))
    cyc = [i for i, n in indeg.items() if n > 0]
    return order, cyc


def load_plan(plan_path: Path, implicit_seq: bool = True) -> dict:
    text = plan_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    tasks, errors = parse_tasks(text, implicit_seq)
    order, cyc = topo_order(tasks) if not errors else ([], [])
    if cyc:
        errors.append(f"循環依賴：{sorted(cyc)}")
    return {"plan": str(plan_path), "name": plan_path.stem.replace("-plan", ""), "frontmatter": fm,
            "tasks": tasks, "order": order, "errors": errors}


def main() -> int:
    argv = sys.argv[1:]
    plan = Path(argv[0])
    if not plan.exists():
        print(f"❌ 找不到 {plan}"); return 2
    implicit = "--no-implicit-seq" not in argv
    ms = int(argv[argv.index("--milestone") + 1]) if "--milestone" in argv else None
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else Path("data") / f"{plan.stem}-tasks.json"
    res = load_plan(plan, implicit)
    if ms is not None:
        res["tasks"] = [t for t in res["tasks"] if t["milestone"] == ms]
        keep = {t["id"] for t in res["tasks"]}
        res["order"] = [i for i in res["order"] if i in keep]
        for t in res["tasks"]:
            t["deps"] = [d for d in t["deps"] if d in keep]
    if res["errors"]:
        print(f"❌ plan 契約違反（{len(res['errors'])}）：")
        for e in res["errors"]:
            print("   - " + e)
        return 2
    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False, indent=1)); return 0
    by = {t["id"]: t for t in res["tasks"]}
    print(f"✅ {plan.name}：{len(res['tasks'])} 任務，{len({t['milestone'] for t in res['tasks']})} milestone")
    if "--dry-run" in argv:
        print(f"{'順序':4} {'#':5} {'角色':7} {'驗證':12} 任務 → 產出")
        for n, i in enumerate(res["order"], 1):
            t = by[i]; v = (t["verify_hint"] or {}).get("method", "auto")
            dep = f"  ⇐ {','.join(t['deps'])}" if t["deps"] else ""
            print(f"{n:<4} {i:<5} {t['role']:<7} {v:<12} {t['name'][:38]} → {t['output_file']}{dep}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"   → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
