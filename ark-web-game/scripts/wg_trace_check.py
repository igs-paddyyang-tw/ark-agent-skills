#!/usr/bin/env python3
"""wg_trace_check — 檢查抽選點對照表（trace-map.md）。

檢查三件事：
  1. 表格：表頭必須是「# | 抽選點 | 參數 | Go | SpinResult 欄位 | 演出步驟」，每列六欄都不可空白，# 不重複。
  2. 欄位：「SpinResult 欄位」欄中以反引號包住的路徑（例 `reel.stops`、`base.ways[]{sym,len}`、
     `feature.script.hands[]`）必須存在於 SpinResult JSON Schema；schema 未展開的物件（base.extra、
     feature.draw、feature.script）底下由遊戲自訂，不再往下檢查。
  3. 參數：給 --prob-spec 時，prob-spec 第 3、4 節出現的每個 P-xx 都要出現在「參數」欄。
     還原（xlsx）模式的 prob-spec 沒有 P-xx、改用「### 表 M-1」這類表號：此時改檢查每個表號都出現在「參數」欄（0.9.0）。

用法:
  python wg_trace_check.py data/slot/<slug>/game/trace-map.md --prob-spec data/slot/<slug>/prob/prob-spec.md [--schema <spin-result.schema.json>] [--json]

exit：0 通過；1 有錯；2 輸入錯誤（檔案不存在、找不到表格）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

HEADER = ["#", "抽選點", "參數", "Go", "SpinResult 欄位", "演出步驟"]
DEFAULT_SCHEMA = pathlib.Path(__file__).resolve().parents[2] / "ark-game-proto" / "scripts" / "stage" / "schema" / "spin-result.schema.json"
P_ID = re.compile(r"(?<![\w-])P-\d{2}(?!\d)")
T_HEAD = re.compile(r"^###\s*表\s*([A-Z]-\d+)", re.M)          # 還原模式 prob-spec 的參數表號（### 表 M-1　…）
T_ID = re.compile(r"(?<![\w-])([A-Z]-\d+)(?!\d)")
SEG = re.compile(r"^([A-Za-z_]\w*)(\[\])?(?:\{([^}]*)\})?$")


def cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def read_table(text: str) -> tuple[list[list[str]] | None, str]:
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith("|") and cells(ln) == HEADER:
            rows = []
            for ln2 in lines[i + 2:]:
                if not ln2.strip().startswith("|"):
                    break
                rows.append(cells(ln2))
            return rows, ""
    return None, "找不到表頭：| " + " | ".join(HEADER) + " |"


def props_of(node: dict) -> dict | None:
    if not isinstance(node, dict):
        return None
    if "properties" in node:
        return node["properties"]
    for k in ("oneOf", "anyOf"):
        for br in node.get(k, []):
            if isinstance(br, dict) and "properties" in br:
                return br["properties"]
    return None


def check_path(path: str, schema: dict) -> str | None:
    node: dict = schema
    for seg in path.split("."):
        m = SEG.match(seg)
        if not m:
            return f"路徑格式不對：{path}"
        name, arr, fields = m.group(1), m.group(2), m.group(3)
        props = props_of(node)
        if props is None:
            return None  # 未展開的物件：遊戲自訂，不再往下檢查
        if name not in props:
            return f"schema 沒有欄位「{name}」：{path}"
        node = props[name]
        if arr:
            node = node.get("items", {}) if isinstance(node, dict) else {}
        if fields is not None:
            sub = props_of(node)
            if sub is not None:
                bad = [f.strip() for f in fields.split(",") if f.strip() and f.strip() not in sub]
                if bad:
                    return f"schema 沒有欄位 {bad}：{path}"
    return None


def prob_spec_params(text: str) -> tuple[list[str], str]:
    """回傳（參數編號, 模式）：有 P-xx 用 P-xx（設計模式）；沒有但有「### 表 X-n」用表號（還原 xlsx 模式）。"""
    m3 = re.search(r"^## 3[.．]", text, re.M)
    m5 = re.search(r"^## 5[.．]", text, re.M)
    part = text[m3.start(): m5.start() if m5 and (not m3 or m5.start() > m3.start()) else len(text)] if m3 else text
    ps = sorted(set(P_ID.findall(part)))
    if ps:
        return ps, "P"
    return sorted(set(T_HEAD.findall(part))), "table"


def check(trace: pathlib.Path, schema: dict, prob_spec: pathlib.Path | None) -> dict:
    text = trace.read_text(encoding="utf-8")
    rows, err = read_table(text)
    if rows is None:
        return {"ok": False, "fatal": err, "errors": [err], "warnings": []}
    errors, warnings, ids, params_seen, tables_seen = [], [], set(), set(), set()
    for n, r in enumerate(rows, 1):
        if len(r) != len(HEADER):
            errors.append(f"第 {n} 列欄數 {len(r)} ≠ {len(HEADER)}")
            continue
        rid = r[0]
        if any(not c for c in r):
            errors.append(f"{rid or f'第 {n} 列'}：有空白欄（不演出請寫「不演出」）")
        if rid in ids:
            errors.append(f"# 重複：{rid}")
        ids.add(rid)
        params_seen.update(P_ID.findall(r[2]))
        tables_seen.update(T_ID.findall(r[2]))
        toks = re.findall(r"`([^`]+)`", r[4])
        if not toks and r[4] not in ("—", "-", "無"):
            warnings.append(f"{rid}：SpinResult 欄位沒有以反引號標出路徑，未檢查")
        for t in toks:
            e = check_path(t.strip(), schema)
            if e:
                errors.append(f"{rid}：{e}")
    params = None
    if prob_spec is not None:
        expected, mode = prob_spec_params(prob_spec.read_text(encoding="utf-8"))
        missing = [p for p in expected if p not in (params_seen if mode == "P" else tables_seen)]
        extra = sorted(p for p in params_seen if p not in expected) if mode == "P" else []
        if missing:
            errors.append("prob-spec 的參數沒有對應抽選點：" + "、".join(missing))
        if extra:
            warnings.append("trace-map 的參數不在 prob-spec 第 3、4 節：" + "、".join(extra))
        params = {"mode": mode, "expected": expected, "covered": sorted((params_seen if mode == "P" else tables_seen) & set(expected)), "missing": missing}
    return {"ok": not errors, "rows": len(rows), "errors": errors, "warnings": warnings, "params": params}


def main() -> None:
    ap = argparse.ArgumentParser(description="檢查 trace-map.md")
    ap.add_argument("trace")
    ap.add_argument("--prob-spec")
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    tp = pathlib.Path(a.trace)
    sp = pathlib.Path(a.schema)
    pp = pathlib.Path(a.prob_spec) if a.prob_spec else None
    for p in [tp, sp] + ([pp] if pp else []):
        if not p.is_file():
            print(json.dumps({"ok": False, "fatal": f"找不到檔案：{p}"}, ensure_ascii=False))
            sys.exit(2)
    res = check(tp, json.loads(sp.read_text(encoding="utf-8")), pp)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(("✅ PASS" if res["ok"] else "❌ FAIL") + f"：{tp}（{res.get('rows', 0)} 列）")
        for e in res["errors"]:
            print("  ✗ " + e)
        for w in res["warnings"]:
            print("  ⚠ " + w)
        if res.get("params"):
            pr = res["params"]
            print(f"  參數（{pr.get('mode')}）：prob-spec {len(pr['expected'])} 個，已對應 {len(pr['covered'])} 個" + (f"；缺 {'、'.join(pr['missing'])}" if pr['missing'] else ""))
    if res.get("fatal"):
        sys.exit(2)
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
