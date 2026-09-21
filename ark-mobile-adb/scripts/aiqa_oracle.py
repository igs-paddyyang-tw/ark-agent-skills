"""aiqa_oracle — 斷言判定（deterministic）。AI 只提供 observations；這裡算 PASS/FAIL/NEEDS_HUMAN/UNCERTAIN。

assertion 欄位：id, oracle ∈ ORACLES, expr（safe_eval，可讀 obs 名稱）, expect（人讀）, spec_ref|origin, when（條件 expr）,
  visual: question + min_confidence（預設 0.8）；timing: expr 以秒為單位；no_crash: 讀 obs['crash'] / obs['foreground']。
回每條 {id, oracle, result: PASS|FAIL|NEEDS_HUMAN|SKIPPED|ERROR, detail}。
"""
from __future__ import annotations

import aiqa_common as C


def _flatten(obs: dict) -> dict:
    """observations：單值或 list（repeat 內累積）。提供 <name> 與 <name>_list 兩種名字。"""
    names = {}
    for k, v in obs.items():
        if isinstance(v, list):
            names[k + "_list"] = v
            names[k] = v[-1] if v else None
        else:
            names[k] = v
    return names


def evaluate(assertions: list[dict], obs: dict) -> list[dict]:
    names = _flatten(obs)
    out = []
    for a in assertions:
        res = {"id": a.get("id"), "oracle": a.get("oracle"), "expect": a.get("expect"), "spec_ref": a.get("spec_ref") or a.get("origin")}
        try:
            if a.get("when") and not C.safe_eval(a["when"], names):
                res.update(result="SKIPPED", detail="when 條件不成立"); out.append(res); continue
            o = a.get("oracle")
            if o == "visual":
                v = obs.get(a.get("obs") or a["id"])
                v = v[-1] if isinstance(v, list) and v else v
                if not isinstance(v, dict) or v.get("answer") is None or v.get("confidence", 0) < float(a.get("min_confidence", 0.8)):
                    res.update(result="NEEDS_HUMAN", detail=f"視覺判定信心不足或無答案: {v}")
                else:
                    want = a.get("expect_answer", True)
                    res.update(result="PASS" if v["answer"] == want else "FAIL", detail=f"answer={v['answer']} conf={v['confidence']} {v.get('detail', '')}")
            elif o == "no_crash":
                crash = names.get("crash"); fg = names.get("foreground", True)
                res.update(result="FAIL" if crash or fg is False else "PASS", detail=f"crash={crash} foreground={fg}")
            else:  # ocr_number / text / state / sequence / timing / expr → 皆以 expr 判
                expr = a.get("expr")
                if not expr:
                    res.update(result="ERROR", detail="缺 expr"); out.append(res); continue
                missing = [n for n in _names_in(expr) if n not in names and n not in C.SAFE_FUNCS]
                if missing:
                    res.update(result="NEEDS_HUMAN", detail=f"觀察值缺失 {missing}（讀數失敗或未執行）"); out.append(res); continue
                if " is " not in expr and any(names.get(n) is None for n in _names_in(expr) if n in names and not n.endswith("_list")):
                    res.update(result="NEEDS_HUMAN", detail="觀察值為 null（讀數失敗）"); out.append(res); continue
                ok = bool(C.safe_eval(expr, names))
                res.update(result="PASS" if ok else "FAIL", detail=_detail(expr, names))
        except Exception as e:  # noqa: BLE001
            res.update(result="ERROR", detail=f"{type(e).__name__}: {e}")
        out.append(res)
    return out


def _names_in(expr: str) -> list[str]:
    import ast
    tree = ast.parse(expr, mode="eval")
    bound = {t.id for n in ast.walk(tree) if isinstance(n, ast.comprehension) for t in ast.walk(n.target) if isinstance(t, ast.Name)}
    return [n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id not in bound and n.id not in ("True", "False", "None")]


def _detail(expr: str, names: dict) -> str:
    used = {n: names[n] for n in _names_in(expr) if n in names}
    s = ", ".join(f"{k}={str(v)[:60]}" for k, v in used.items())
    return f"{expr} | {s}"[:400]


def item_verdict(rep_results: list[list[dict]], blocked: str | None = None, na: str | None = None) -> dict:
    """多次重複的斷言結果 → 項目 verdict。"""
    if na:
        return {"verdict": "NA", "reason": na}
    if blocked:
        return {"verdict": "BLOCK", "reason": blocked}
    if not rep_results:
        return {"verdict": "BLOCK", "reason": "無執行結果"}
    per_rep = []
    for rs in rep_results:
        results = [r["result"] for r in rs if r["result"] != "SKIPPED"]
        if any(r in ("ERROR",) for r in results):
            per_rep.append("NEEDS_HUMAN")
        elif "FAIL" in results:
            per_rep.append("FAIL")
        elif "NEEDS_HUMAN" in results:
            per_rep.append("NEEDS_HUMAN")
        else:
            per_rep.append("PASS")
    if len(set(per_rep)) > 1 and ("PASS" in per_rep and "FAIL" in per_rep):
        return {"verdict": "FLAKY", "reason": f"重複結果不一致 {per_rep}"}
    if "FAIL" in per_rep:
        return {"verdict": "FAIL", "reason": "至少一條斷言 FAIL"}
    if "NEEDS_HUMAN" in per_rep:
        return {"verdict": "NEEDS_HUMAN", "reason": "有斷言需人工覆核"}
    return {"verdict": "PASS", "reason": "全部斷言 PASS"}
