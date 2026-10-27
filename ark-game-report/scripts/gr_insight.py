#!/usr/bin/env python3
"""gr_insight — 分析思維層：metrics.json × playbook → 發現、假設、待查、建議、知識庫參考。

產出：
  - <data_dir>/insights.md：分析草稿（依六問整理，附知識庫參考與本期提醒）
  - 回填 report.json 的 verdict.headline／next（標「草稿」；已有人工結論時不覆寫，除非 --overwrite）

知識庫：playbook 的 kb.page 是固定參考；有 ark-wiki-engine 時另用 kb_query 跑 wiki_query 補搜（--no-kb 關閉）。
結論一律是草稿：假設要照 checks 驗證後，人工改寫 report.json 的 verdict 再 render。

用法:
  python gr_insight.py --config report.yaml [--playbook my_playbook.yaml] [--no-kb] [--overwrite]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gr_common as C  # noqa: E402

QNAME = {"Q1": "Q1 規模", "Q2": "Q2 玩家結構", "Q3": "Q3 黏著", "Q4": "Q4 深度", "Q5": "Q5 機率表現", "Q6": "Q6 增量", "H": "健康觀察"}
LNAME = {"g": "達標", "y": "觀察", "r": "未達標", "na": "資料不足"}
SEV = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def getp(m: dict, path: str):
    cur = m
    for k in str(path).split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


def derive(m: dict) -> dict:
    m = dict(m)
    if m.get("share_first") and m.get("share_last") is not None:
        m["decay_ratio"] = m["share_last"] / m["share_first"]
    q5 = dict(m.get("q5") or {})
    q5["trigger_alert_count"] = len(q5.get("trigger_alerts") or [])
    q5["trigger_alert_names"] = "、".join(a["name"] for a in q5.get("trigger_alerts") or []) or None
    m["q5"] = q5
    m["ret"] = {str(k): v for k, v in (m.get("ret") or {}).items()}
    return m


OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "==": lambda a, b: a == b}


def evaluate(rule: dict, m: dict):
    """回傳 True／False／None（None＝缺值無法判斷）。"""
    for c in rule.get("when") or []:
        a = getp(m, c["m"])
        b = getp(m, c["ref"]) if "ref" in c else c.get("value")
        if a is None or b is None:
            return None
        try:
            if not OPS[c["op"]](a, b):
                return False
        except TypeError:
            return None
    return True


def fill(tmpl: str, m: dict) -> str:
    def rep(mo):
        key, spec = mo.group(1), mo.group(2) or ""
        v = getp(m, key)
        if v is None:
            return "—"
        if spec == "%":
            return C.pct(v)
        if spec == "%2":
            return C.pct(v, 2)
        if spec == "+%":
            return f"{v * 100:+.1f}%"
        if spec == "x":
            return f"{v:.2f}"
        return str(v)
    return re.sub(r"\{([\w.]+)(?::([^}]+))?\}", rep, tmpl)


def kb_search(cfg: dict, query: str) -> list:
    if not query or not (C.WIKI / "wiki_query.py").is_file():
        return []
    kb = cfg.get("kb") or {}
    hits = []
    for wd in kb.get("wiki_dirs") or []:
        if not pathlib.Path(wd).is_dir():
            continue
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", str(C.WIKI / "wiki_query.py"), "--wiki_dir", wd, "--query", query,
                                "--top_k", str(kb.get("top_k", 3))], capture_output=True, text=True, encoding="utf-8", timeout=60)
            data = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
        except Exception:  # noqa: BLE001
            continue
        for h in (data.get("results") or data.get("data", {}).get("results") or [])[: kb.get("top_k", 3)]:
            hits.append({"page": h.get("page") or h.get("path"), "title": h.get("title", "")})
    return hits


def headline(stage: int, lights: dict, top: list) -> str:
    good = [QNAME[q] for q, v in lights.items() if v == "g"]
    bad = [QNAME[q] for q, v in lights.items() if v == "r"]
    s = f"D+{stage} {'初判' if stage <= 7 else ('檢查點' if stage <= 14 else '定調')}："
    s += ("、".join(good) + " 達標" if good else "沒有達標項目")
    if bad:
        s += "；" + "、".join(bad) + " 未達標"
    if top:
        s += "。主要問題：" + top[0]["finding"]
    return s + "（草稿）"


def main() -> None:
    ap = argparse.ArgumentParser(description="指標 → 分析草稿與策略參考")
    ap.add_argument("--config", required=True)
    ap.add_argument("--playbook", help="自訂 playbook（預設 assets/playbook.yaml）")
    ap.add_argument("--no-kb", action="store_true")
    ap.add_argument("--overwrite", action="store_true", help="覆寫 report.json 既有的人工結論")
    a = ap.parse_args()
    cfg = C.load_config(a.config)
    dd = C.data_dir(cfg)
    if not (dd / "metrics.json").is_file():
        C.fail("BAD_INPUT", "找不到 metrics.json", "先跑 gr_run.py build")
    metrics = json.loads((dd / "metrics.json").read_text(encoding="utf-8"))
    report = json.loads((dd / "report.json").read_text(encoding="utf-8"))
    pb = C.yaml_load(pathlib.Path(a.playbook) if a.playbook else C.ASSETS / "playbook.yaml") or {}
    stage = int(cfg["stage"])
    out = {}
    L = [f"# {cfg['game']['name']} D+{stage} 分析草稿", "",
         "> 由 ark-game-report gr_insight 依 playbook 產生。發現是**待驗證的起點**：照「要查什麼」驗證後，再改寫 report.json 的結論。", ""]
    for vn, m0 in metrics.items():
        m = derive(m0)
        fired, unknown = [], []
        for rule in pb.get("rules") or []:
            res = evaluate(rule, m)
            if res is None:
                unknown.append(rule["id"])
            elif res:
                item = {"id": rule["id"], "q": rule.get("q", "Q1"), "severity": rule.get("severity", "P2"),
                        "finding": fill(rule.get("finding", rule["id"]), m), "hypotheses": rule.get("hypotheses") or [],
                        "checks": rule.get("checks") or [], "actions": rule.get("actions") or [], "kb": rule.get("kb") or [],
                        "kb_hits": [] if a.no_kb else kb_search(cfg, rule.get("kb_query", ""))}
                fired.append(item)
        fired.sort(key=lambda x: SEV.get(x["severity"], 9))
        problems = [f for f in fired if f["severity"] in ("P0", "P1")]
        lights = m.get("lights") or {}
        out[vn] = {"fired": fired, "unknown": unknown}
        view = report["views"].get(vn, {})
        vd = view.setdefault("verdict", {})
        if a.overwrite or not vd.get("headline"):
            vd["headline"] = headline(stage, lights, problems)
            vd["next"] = [x for f in (problems or fired)[:3] for x in f["actions"][:1]] or ["指標都在預期範圍，維持觀察"]
        # md
        L += [f"## 切分：{vn}", "", f"**結論草稿**：{vd['headline']}", "", "| 問題 | 燈號 |", "|------|------|"]
        L += [f"| {QNAME[q]} | {LNAME.get(lights.get(q, 'na'))} |" for q in QNAME]
        L += ["", "### 發現（依嚴重度）", ""]
        if not fired:
            L += ["- 沒有觸發任何 playbook 規則。", ""]
        for f in fired:
            L += [f"#### [{f['severity']}] {QNAME.get(f['q'], f['q'])}｜{f['finding']}（{f['id']}）", ""]
            if f["hypotheses"]:
                L += ["- **可能原因**："] + [f"  - {h}" for h in f["hypotheses"]]
            if f["checks"]:
                L += ["- **要查什麼**："] + [f"  - {c}" for c in f["checks"]]
            if f["actions"]:
                L += ["- **建議方向**："] + [f"  - {x}" for x in f["actions"]]
            refs = [f"[[{k['page']}]]：{k.get('why', '')}" for k in f["kb"]] + \
                   [f"[[{h['page']}]] {h.get('title', '')}（wiki_query 補搜）" for h in f["kb_hits"] if h.get("page")]
            if refs:
                L += ["- **知識庫參考**："] + [f"  - {r}" for r in refs]
            L.append("")
        if unknown:
            L += ["### 無法判斷（缺資料或缺基準）", "", "- " + "、".join(unknown), ""]
    rem = (pb.get("reminders") or {}).get(stage) or (pb.get("reminders") or {}).get(str(stage)) or []
    if rem:
        L += ["## 本期分析提醒", ""] + [f"- {r}" for r in rem] + [""]
    L += ["## 分析思維檢查", "", "寫結論前，逐項確認：", "",
          "1. 每個數字都有比較對象嗎？（歷史同期、前一期、規格）",
          "2. 有沒有被活動、節日、同期新機干擾？",
          "3. 是「人數」還是「人均」造成的變化？（押量 ＝ 人數 × 人均手數 × 平均押注）",
          "4. 樣本夠嗎？（D+7 的回訪率、低頻特色的觸發率）",
          "5. 結論有沒有建立在少數玩家身上？（健康觀察的集中度）",
          "6. 建議能被執行嗎？每條要對到負責人（企劃、機率、營運）",
          "", "詳見 `references/analysis-thinking.md`。", ""]
    first = next(iter(report["views"].values()))
    report["verdict"] = {**report.get("verdict", {}), **{k: first["verdict"][k] for k in ("headline", "next") if k in first.get("verdict", {})}}
    (dd / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (dd / "insights.md").write_text("\n".join(L), encoding="utf-8")
    (dd / "insights.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    C.emit({"insights": str(dd / "insights.md"),
            "fired": {vn: [f["id"] for f in v["fired"]] for vn, v in out.items()},
            "next": f"確認／改寫 report.json 的 verdict 後：gr_run.py render --config {a.config}"}, {"stage": "insight"})


if __name__ == "__main__":
    main()
