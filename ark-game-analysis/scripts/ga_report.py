#!/usr/bin/env python3
"""ga_report — game-analysis.yaml → ark-md-report 契約報告（Content 軌）＋ 選配 View 軌 HTML。

把 ark-game-analysis 的結構化產出（game-analysis.yaml / kb-refs.yaml / evidence.jsonl / manifest.json）
deterministic 編成一份 `type: data` 的分析報告，讓 A 段（競品分析）的結論能被
日報 CollectorRunner / wiki ingest / 其他 agent 直接消費。**不呼叫 LLM、不改寫任何 claim**。

假設（data 型）：「本 run 的 evidence 足以支撐 game-spec 草稿」
  verdict: confirmed   UNKNOWN 佔比 ≤ 30% 且無 P0
           inconclusive UNKNOWN 佔比 ≤ 60%
           rejected     UNKNOWN 佔比 > 60%（domain 或素材可疑）

Findings 全部由規則產生（見 RULES），每條 P0/P1 都有 Evidence 區塊支持，Actions 對回 Finding。

用法:
    python ga_report.py --run artifacts/cva/<run_id>                # → <run>/report/<date>-game-analysis-<slug>.md
    python ga_report.py --run <run> --html                          # 另產同名 .html（midnight token）＋雙軌戳記
    python ga_report.py --run <run> --publish docs/reports          # 複製到 docs/reports/ 並 report_register
    python ga_report.py --run <run> --wiki-schema knowledge/shared/schema.md   # lint 加驗 tags 白名單

exit: 0 OK / 2 BAD_INPUT / 6 QUERY_FAILED（lint FAIL — 代表引擎 bug，不是報告該手改）/ 8 缺依賴
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ga_common as C  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
MD_REPORT = HERE.parent.parent / "ark-md-report" / "scripts"

REPORT_TAGS = ["case", "game"]            # 受控詞彙（knowledge/shared/schema.md 白名單）
PROV_ORDER = ("OBSERVED", "INFERRED", "FROM_KB", "PROPOSED", "DECIDED", "NOT_OBSERVED", "UNKNOWN")


# ── 載入 ──────────────────────────────────────────────────────────────────

def load_inputs(run: pathlib.Path) -> dict:
    ga_p = run / "game-analysis.yaml"
    if not ga_p.exists():
        C.fail("BAD_INPUT", f"缺 {ga_p}", "先跑 ga_run.py")
    ga = C.yaml_load(ga_p)
    kb = C.yaml_load(run / "kb-refs.yaml") if (run / "kb-refs.yaml").exists() else {"items": []}
    ev = C.load_evidence(run)
    manifest = C.load_manifest(run)
    ent_p = run / "entities.json"
    entities = json.loads(ent_p.read_text(encoding="utf-8")) if ent_p.exists() else {"entities": {}, "all_ids": []}
    return {"ga": ga, "kb": kb, "evidence": ev, "manifest": manifest, "entities": entities}


# ── 統計 ──────────────────────────────────────────────────────────────────

def compute_stats(inp: dict) -> dict:
    ga, ev, kb = inp["ga"], inp["evidence"], inp["kb"]
    prov = {p: 0 for p in PROV_ORDER}
    conf = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    items = []
    total = 0
    kb_by_item = {i.get("item_id"): i for i in kb.get("items", [])}
    for it in ga.get("items", []):
        claims = it.get("claims", [])
        n = len(claims)
        unk = sum(1 for c in claims if c.get("provenance") == "UNKNOWN")
        for c in claims:
            prov[c.get("provenance", "UNKNOWN")] = prov.get(c.get("provenance", "UNKNOWN"), 0) + 1
            conf[c.get("confidence", "unknown")] = conf.get(c.get("confidence", "unknown"), 0) + 1
        total += n
        k = kb_by_item.get(it.get("id"), {})
        items.append({
            "id": it.get("id"), "name": it.get("name"), "claims": n, "unknown": unk,
            "all_unknown": n > 0 and unk == n,
            "entities": len(it.get("entities", [])),
            "kb_informative": bool(k.get("informative")),
            "kb_refs": [r for r in k.get("refs", []) if not r.get("cross_domain")],
            "kb_cross": [r for r in k.get("refs", []) if r.get("cross_domain")],
        })
    unknown_ratio = (prov["UNKNOWN"] / total) if total else 1.0
    visual = sum(1 for e in ev if e.get("type") == "visual")
    transcript = sum(1 for e in ev if e.get("type") == "transcript")
    st = ga.get("stats", {})
    return {
        "claims": total, "prov": prov, "conf": conf, "unknown_ratio": unknown_ratio,
        "coverage_pct": round((1 - unknown_ratio) * 100, 1),
        "schema_violations": int(st.get("schema_violations", 0) or 0),
        "entities": int(st.get("entities", 0) or 0),
        "evidence_visual": visual, "evidence_transcript": transcript,
        "items": items,
    }


# ── 規則 → Findings / Evidence / Actions ─────────────────────────────────

def build_findings(s: dict, inp: dict) -> list[dict]:
    """每條 finding: sev, what, where, impact, ev_method, ev_output, ev_conf, action, est"""
    f: list[dict] = []
    ur = round(s["unknown_ratio"] * 100, 1)
    if s["unknown_ratio"] > 0.6:
        f.append(dict(sev="P0", what=f"UNKNOWN 主張佔 {ur}%，超過 60% 門檻", where="game-analysis.yaml stats",
                      impact="domain 判定或素材可能錯誤；規格草稿將幾乎全是 Open Question",
                      ev_method="統計 game-analysis.yaml 全部 claims 的 provenance",
                      ev_output=f"claims={s['claims']}，UNKNOWN={s['prov']['UNKNOWN']}（{ur}%）", ev_conf="high",
                      action="先查 manifest.detect / domain 是否判錯；再確認影片是否涵蓋核心玩法；不要硬填規格", est="30min"))
    if s["schema_violations"] > 0:
        f.append(dict(sev="P1", what=f"模型違反 claim 契約 {s['schema_violations']} 次（未宣告 key / 壞 evidence / 型別不符）",
                      where="game-analysis.yaml stats.schema_violations",
                      impact="被守門丟棄或降級的主張不會進規格，覆蓋率被低估",
                      ev_method="讀 ga_analyze 後處理守門的 schema_violations 計數",
                      ev_output=f"schema_violations={s['schema_violations']}，model={inp['ga'].get('model')}", ev_conf="high",
                      action="換模型或檢查 pack prompt 是否漏了 key 宣告；守門規則本身不動", est="20min"))
    if s["evidence_visual"] == 0:
        f.append(dict(sev="P1", what="沒有任何 visual evidence，全部主張只能靠口白", where="evidence.jsonl",
                      impact="口白不能撐 OBSERVED，所有主張最高只到 INFERRED",
                      ev_method="計數 evidence.jsonl 的 type", ev_output=f"visual=0，transcript={s['evidence_transcript']}",
                      ev_conf="high", action="重跑 ark-video-understanding 檢查抽幀設定", est="15min"))
    for it in s["items"]:
        if it["all_unknown"]:
            f.append(dict(sev="P2", what=f"分析項 {it['id']}（{it['name']}）{it['claims']} 條主張全部 UNKNOWN",
                          where=f"game-analysis.yaml items[{it['id']}]",
                          impact="這一章在規格草稿裡沒有內容，全部進 Open Questions",
                          ev_method=f"逐條檢查 {it['id']} 的 provenance",
                          ev_output=f"unknown={it['unknown']}/{it['claims']}", ev_conf="high",
                          action="補拍或補影片段落；或由企劃在 ark-grill-me 直接決議", est="視素材"))
    for it in s["items"]:
        if it["kb_informative"] and not it["kb_refs"] and not it["all_unknown"]:
            f.append(dict(sev="P3", what=f"分析項 {it['id']}（{it['name']}）無同 domain 知識庫命中",
                          where=f"kb-refs.yaml items[{it['id']}]",
                          impact="可能是新手法，或 pack tag 沒對到；prob-architect 無 K 卡可援引",
                          ev_method="讀 kb-refs.yaml 的 refs（排除 cross_domain）",
                          ev_output=f"refs={len(it['kb_refs'])}，cross_domain={len(it['kb_cross'])}", ev_conf="medium",
                          action="若機制成立，比照 K-XXX 立案；或走 wiki_taxonomy propose 補 tag", est="30min"))
    if s["entities"] == 0:
        f.append(dict(sev="P3", what="未辨識任何實體（符號 / 魚種 / 角色）", where="entities.json",
                      impact="規格的符號表與命名字典為空", ev_method="讀 entities.json all_ids",
                      ev_output="all_ids=[]", ev_conf="high", action="確認影片有清晰的符號特寫；必要時補抽幀", est="15min"))
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    f.sort(key=lambda x: (order[x["sev"]], x["what"]))
    for i, x in enumerate(f, 1):
        x["id"] = f"F-{i}"
    return f


def verdict_of(s: dict, findings: list[dict]) -> tuple[str, str]:
    has_p0 = any(x["sev"] == "P0" for x in findings)
    if s["unknown_ratio"] <= 0.3 and not has_p0:
        v = "confirmed"
    elif s["unknown_ratio"] <= 0.6:
        v = "inconclusive"
    else:
        v = "rejected"
    if s["evidence_visual"] >= 10 and s["schema_violations"] == 0:
        c = "high"
    elif s["evidence_visual"] >= 3:
        c = "medium"
    else:
        c = "low"
    return v, c


# ── Markdown ──────────────────────────────────────────────────────────────

def _cell(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, tuple)):
        return ", ".join(_cell(x) for x in v) or "—"
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return str(v).replace("|", "\\|").replace("\n", " ")


def render_md(inp: dict, s: dict, findings: list[dict], date: str, md_name: str) -> str:
    ga, man = inp["ga"], inp["manifest"]
    run_id, domain = ga.get("run_id"), ga.get("domain")
    verdict, confidence = verdict_of(s, findings)
    sev = {"p0": 0, "p1": 0, "p2": 0, "p3": 0}
    for x in findings:
        sev[x["sev"].lower()] += 1
    dur = (man.get("video") or {}).get("duration")
    L: list[str] = []
    L += ["---",
          f'title: "競品機制分析：{domain} · run {run_id}"',
          "type: data",
          f'subject: "cva/{run_id}"',
          f"date: {date}",
          "author: ark-game-analysis",
          "source_skill: ark-game-analysis",
          f"verdict: {verdict}",
          f"confidence: {confidence}",
          f"findings: {{ p0: {sev['p0']}, p1: {sev['p1']}, p2: {sev['p2']}, p3: {sev['p3']} }}",
          f"score: {s['coverage_pct']}",
          'score_version: "ga-coverage-1"',
          f"tags: [{', '.join(REPORT_TAGS)}]",
          "loop_stage: post-analysis",
          "sources:",
          f"  - artifacts/cva/{run_id}/game-analysis.yaml",
          f"  - artifacts/cva/{run_id}/kb-refs.yaml",
          f"  - artifacts/cva/{run_id}/evidence.jsonl",
          f"  - artifacts/cva/{run_id}/manifest.json",
          "run:",
          f"  run_id: {run_id}",
          f"  domain: {domain}",
          f"  pack_version: \"{ga.get('pack_version')}\"",
          f"  pack_sha256: {ga.get('pack_sha256')}",
          f"  model: {ga.get('model')}",
          f"  video_sha256: {(man.get('video') or {}).get('sha256')}",
          "---", ""]
    L += [f"# 競品機制分析：{domain} · run {run_id}", "",
          f"> 由 ga_report 從 `game-analysis.yaml` deterministic 編成；主張逐條繼承，未經改寫。"
          f" 影片 {dur or '?'} 秒，evidence visual {s['evidence_visual']} / transcript {s['evidence_transcript']}。", ""]

    # Verdict
    L += ["## Verdict", "",
          f"{verdict} — 假設「本 run 的 evidence 足以支撐 game-spec 草稿」。"
          f"覆蓋率 {s['coverage_pct']}%（{s['claims']} 條主張中 UNKNOWN {s['prov']['UNKNOWN']} 條），"
          f"OBSERVED {s['prov']['OBSERVED']}、INFERRED {s['prov']['INFERRED']}，守門違規 {s['schema_violations']} 次。"
          f" 門檻：UNKNOWN ≤ 30% 且無 P0 為 confirmed；≤ 60% 為 inconclusive；其餘 rejected。", ""]

    # 假設與方法
    L += ["## 假設與方法", "",
          "- 假設：影片 evidence（visual 為主、transcript 為輔）足以支撐該 domain pack 宣告的分析項，讓 ark-game-spec 產出可決議的草稿。",
          "- 方法：ark-video-understanding 抽幀 → ga_observe 逐 sheet 多模態觀察 → ga_analyze 逐分析項產 claim（provenance / evidence / confidence）→ deterministic 後處理守門 → kb_match 受控詞彙比對知識庫。",
          "- 判準：UNKNOWN 佔比、守門違規次數、visual evidence 數量；Findings 全由規則產生，不含主觀評語。",
          f"- 版本：pack {ga.get('pack_version')}（sha {str(ga.get('pack_sha256'))[:12]}）、模型 {ga.get('model')}。", ""]

    # Findings
    L += ["## Findings", "", "| ID | 嚴重度 | 現象 | 來源 | 影響 |", "|----|--------|------|------|------|"]
    if findings:
        for x in findings:
            L.append(f"| {x['id']} | {x['sev']} | {_cell(x['what'])} | {_cell(x['where'])} | {_cell(x['impact'])} |")
    L.append("")
    if not findings:
        L += ["（規則未觸發任何 finding。）", ""]

    # Evidence
    L += ["## Evidence", ""]
    if findings:
        for i, x in enumerate(findings, 1):
            L += [f"### E-{i}（支持 {x['id']}）", "",
                  f"- 方法：{x['ev_method']}", f"- 輸出：`{x['ev_output']}`", f"- confidence: {x['ev_conf']}", ""]
    else:
        L += ["（無 finding，無需證據。）", ""]

    # Actions
    L += ["## Actions", "", "| ID | 對應 Finding | 建議 | 估時 |", "|----|--------------|------|------|"]
    for i, x in enumerate(findings, 1):
        L.append(f"| A-{i} | {x['id']} | {_cell(x['action'])} | {x['est']} |")
    L.append("")

    # 機制主張總表
    L += ["## 機制主張總表", "",
          "每條主張直接取自 game-analysis.yaml；provenance 五分法：OBSERVED（有畫面證據）/ INFERRED（推論）/ UNKNOWN（影片未涵蓋）。", ""]
    for it in ga.get("items", []):
        L += [f"### {it.get('id')} {it.get('name')}", "",
              "| key | value | provenance | evidence | confidence |", "|-----|-------|------------|----------|------------|"]
        for c in it.get("claims", []):
            L.append(f"| `{c.get('key')}` | {_cell(c.get('value'))} | {c.get('provenance')} | {_cell(c.get('evidence'))} | {c.get('confidence')} |")
        L.append("")
        ents = it.get("entities", [])
        if ents:
            L += ["實體：" + "、".join(f"`{e.get('id')}`（{e.get('entity_type')}，{e.get('provenance')}）" for e in ents), ""]

    # 知識庫命中
    L += ["## 知識庫命中", "", "| 分析項 | 同 domain 命中 | 跨 domain 命中 |", "|--------|----------------|----------------|"]
    for it in s["items"]:
        same = "、".join(f"{r['id']}（{r.get('title', '')}，{r.get('score')}）" for r in it["kb_refs"]) or "—"
        cross = "、".join(f"{r['id']}（{r.get('domain')}）" for r in it["kb_cross"]) or "—"
        L.append(f"| {it['id']} {it['name']} | {_cell(same)} | {_cell(cross)} |")
    L.append("")

    # 邊界聲明
    L += ["## 邊界聲明", "",
          f"- 本報告基於 run `{run_id}` 於 {date} 的 game-analysis.yaml 快照；重跑 ga_run 後需重產本報告。",
          "- 只陳述影片可觀察或可推論的機制，不含 RTP / 數值（數值一律待 quicktest 反推）。",
          "- 未涵蓋：影片未拍到的玩法、口白宣稱但無畫面佐證的內容（守門已降級）。",
          "- 不為競品符號 / 角色取名；競品畫面僅供內部使用。",
          f"- Content 軌檔名：`{md_name}`；View 軌 HTML 若存在，以雙軌戳記為準。", ""]
    return "\n".join(L)


# ── HTML（View 軌，midnight token；只裁剪不新增）───────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg:#0d1219;--surface:#151c26;--surface-2:#1c2532;--border:#273140;--text:#e8edf4;--text-2:#a8b4c4;--text-3:#68758a;
--accent:#3dd6c3;--accent-soft:rgba(61,214,195,.12);--ok:#4ade80;--warn:#fbbf24;--danger:#f87171;--info:#60a5fa;
--font-display:"Space Grotesk","Noto Sans TC","Microsoft JhengHei",sans-serif;--font-body:"Noto Sans TC","Microsoft JhengHei","PingFang TC",sans-serif;
--font-mono:"JetBrains Mono","Noto Sans TC",monospace;--radius:12px;--radius-sm:7px;--shadow:0 0 0 1px rgba(255,255,255,.03),0 8px 24px rgba(0,0,0,.35);--maxw:1080px;}
*{box-sizing:border-box;margin:0;padding:0}body{background:var(--bg);color:var(--text);font-family:var(--font-body);font-size:15px;line-height:1.75;-webkit-font-smoothing:antialiased}
.page{max-width:var(--maxw);margin:0 auto;padding:48px 28px 80px}h1,h2,h3{font-family:var(--font-display);line-height:1.3}a{color:var(--accent)}
.report-header{padding:8px 0 32px;border-bottom:1px solid var(--border);margin-bottom:40px}.eyebrow{font-family:var(--font-mono);font-size:12px;letter-spacing:.14em;color:var(--accent);text-transform:uppercase;margin-bottom:14px}
.report-header h1{font-size:clamp(26px,3.5vw,38px);margin-bottom:12px}.lede{font-size:17px;color:var(--text-2);max-width:44em}.meta{display:flex;gap:10px;align-items:center;margin-top:18px;font-size:13px;color:var(--text-3);flex-wrap:wrap}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-family:var(--font-mono);border:1px solid var(--border)}.badge-ok{color:var(--ok);border-color:var(--ok)}.badge-warn{color:var(--warn);border-color:var(--warn)}.badge-danger{color:var(--danger);border-color:var(--danger)}.badge-accent{color:var(--accent);border-color:var(--accent)}
.summary{background:var(--accent-soft);border-left:4px solid var(--accent);border-radius:var(--radius-sm);padding:22px 26px;margin-bottom:40px}.summary h2{font-size:15px;letter-spacing:.06em;color:var(--accent);margin-bottom:10px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:40px}.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:20px 22px}
.kpi-label{font-size:12px;letter-spacing:.08em;color:var(--text-3);margin-bottom:8px}.kpi-value{font-family:var(--font-display);font-size:30px;font-weight:700;line-height:1.1}
.section{margin-bottom:44px}.section-head{display:flex;align-items:baseline;gap:14px;padding-bottom:12px;border-bottom:1px solid var(--border);margin-bottom:20px}.section-no{font-family:var(--font-mono);font-size:13px;color:var(--accent);font-weight:600}.section h2{font-size:22px}.section h3{font-size:16px;margin:22px 0 10px;color:var(--text)}.section p,.section li{color:var(--text-2);margin-bottom:10px}
.table-wrap{overflow-x:auto;margin:16px 0;border:1px solid var(--border);border-radius:var(--radius)}.table{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--surface)}.table th{background:var(--surface-2);text-align:left;font-weight:600;padding:10px 14px;border-bottom:1px solid var(--border);white-space:nowrap}.table td{padding:9px 14px;border-bottom:1px solid var(--border);color:var(--text-2);vertical-align:top}.table tbody tr:hover{background:var(--accent-soft)}
code{font-family:var(--font-mono);font-size:12.5px;background:var(--surface-2);padding:1px 6px;border-radius:4px}
.callout{border:1px solid var(--border);border-left-width:4px;border-radius:var(--radius-sm);padding:16px 20px;margin:16px 0;background:var(--surface)}.callout-title{font-weight:700;font-size:13.5px;margin-bottom:6px}.callout-info{border-left-color:var(--info)}.callout-info .callout-title{color:var(--info)}
.prov-OBSERVED{color:var(--ok)}.prov-INFERRED{color:var(--warn)}.prov-UNKNOWN{color:var(--text-3)}.prov-FROM_KB{color:var(--info)}
.report-footer{border-top:1px solid var(--border);padding-top:20px;font-size:12.5px;color:var(--text-3);font-family:var(--font-mono)}
@media print{body{background:#fff}.kpi,.callout{box-shadow:none!important}}
"""


def _md_table_to_html(block: str, prov_col: bool = False) -> str:
    rows = [r for r in block.strip().splitlines() if r.startswith("|")]
    if len(rows) < 2:
        return ""
    def cells(r):
        return [c.strip() for c in r.strip().strip("|").split("|")]
    head = cells(rows[0])
    out = ["<div class=\"table-wrap\"><table class=\"table\"><thead><tr>" + "".join(f"<th>{_inline(h)}</th>" for h in head) + "</tr></thead><tbody>"]
    for r in rows[2:]:
        cs = cells(r)
        tds = []
        for i, c in enumerate(cs):
            cls = ""
            if head[i] in ("嚴重度",) and c in ("P0", "P1", "P2", "P3"):
                cls = {"P0": "badge badge-danger", "P1": "badge badge-warn", "P2": "badge badge-accent", "P3": "badge"}[c]
                tds.append(f"<td><span class=\"{cls}\">{c}</span></td>")
            elif head[i] == "provenance":
                tds.append(f"<td class=\"prov-{c}\">{c}</td>")
            else:
                tds.append(f"<td>{_inline(c)}</td>")
        out.append("<tr>" + "".join(tds) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def _inline(t: str) -> str:
    t = htmlmod.escape(t.replace("\\|", "|"))
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def render_html(md_text: str, fm: dict, md_rel: str) -> str:
    body = md_text.split("\n---\n", 1)[1] if md_text.startswith("---") else md_text
    # 切章節
    parts = re.split(r"^## ", body, flags=re.M)
    secs: list[tuple[str, str]] = []
    for p in parts[1:]:
        title, _, rest = p.partition("\n")
        secs.append((title.strip(), rest))
    verdict = str(fm.get("verdict"))
    badge = {"confirmed": "badge-ok", "inconclusive": "badge-warn", "rejected": "badge-danger"}.get(verdict, "")
    f = fm.get("findings", {})
    H = [f"<!DOCTYPE html><html lang=\"zh-Hant\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
         f"<title>{htmlmod.escape(str(fm.get('title')))}</title><style>{CSS}</style></head><body data-theme=\"dark\"><div class=\"page\">",
         "<header class=\"report-header\"><div class=\"eyebrow\">ark-game-analysis · data report · internal</div>",
         f"<h1>{htmlmod.escape(str(fm.get('title')))}</h1>",
         f"<p class=\"lede\">假設「evidence 足以支撐規格草稿」的 deterministic 判定；主張逐條來自 game-analysis.yaml。</p>",
         f"<div class=\"meta\"><span>{fm.get('date')}</span><span>·</span><span>{fm.get('author')}</span><span>·</span>"
         f"<span class=\"badge {badge}\">{verdict}</span><span class=\"badge\">confidence {fm.get('confidence')}</span></div></header>"]
    H.append("<div class=\"kpis\">" + "".join(
        f"<div class=\"kpi\"><div class=\"kpi-label\">{k}</div><div class=\"kpi-value\">{v}</div></div>" for k, v in [
            ("覆蓋率 %", fm.get("score")), ("P0", f.get("p0", 0)), ("P1", f.get("p1", 0)), ("P2", f.get("p2", 0)), ("P3", f.get("p3", 0))]) + "</div>")
    # Evidence 只渲染 P0/P1 對應的 E-x（html-mapping 裁剪原則），其餘指路回 MD
    sev_of: dict[str, str] = {}
    for t, r in secs:
        if t == "Findings":
            for row in r.splitlines():
                m = re.match(r"\|\s*(F-\d+)\s*\|\s*(P\d)\s*\|", row)
                if m:
                    sev_of[m.group(1)] = m.group(2)
    n = 0
    for title, rest in secs:
        n += 1
        if title == "Verdict":
            H.append(f"<div class=\"summary\"><h2>VERDICT</h2><p>{_inline(rest.strip())}</p></div>")
            continue
        H.append(f"<section class=\"section\"><div class=\"section-head\"><span class=\"section-no\">{n:02d}</span><h2>{_inline(title)}</h2></div>")
        chunks = re.split(r"(?m)^(?=### )", rest)
        if title == "Evidence":
            keep = [c for c in chunks if not c.startswith("### ") or
                    sev_of.get((re.search(r"支持 (F-\d+)", c) or [None, ""])[1], "") in ("P0", "P1")]
            omitted = len(chunks) - len(keep)
            if omitted:
                H.append(f"<p>只列 P0 / P1 的證據；其餘 {omitted} 項見 <code>{htmlmod.escape(md_rel)}</code>。</p>")
            chunks = keep
        for ch in chunks:
            if ch.startswith("### "):
                h3, _, ch = ch.partition("\n")
                H.append(f"<h3>{_inline(h3[4:].strip())}</h3>")
            tbl = "\n".join(l for l in ch.splitlines() if l.startswith("|"))
            if tbl:
                H.append(_md_table_to_html(tbl))
            lis = [l[2:] for l in ch.splitlines() if l.startswith("- ")]
            if lis:
                wrap = "callout callout-info" if title == "邊界聲明" else ""
                H.append((f"<div class=\"{wrap}\"><div class=\"callout-title\">{_inline(title)}</div>" if wrap else "") +
                         "<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in lis) + "</ul>" + ("</div>" if wrap else ""))
            paras = [l for l in ch.splitlines() if l.strip() and not l.startswith(("|", "- ", "### ", "（"))]
            for p in paras:
                H.append(f"<p>{_inline(p)}</p>")
        H.append("</section>")
    H.append(f"<footer class=\"report-footer\">Content 軌來源：{htmlmod.escape(md_rel)} · 渲染：ga_report（midnight token，只裁剪不新增）· distribution: internal</footer>")
    H.append("</div></body></html>")
    return "\n".join(H)


# ── lint / pair / register（借 ark-md-report 腳本）────────────────────────

def run_tool(script: str, *args) -> tuple[int, str]:
    p = MD_REPORT / script
    if not p.exists():
        C.fail("BAD_INPUT", f"找不到 {p}", "ark-md-report 需與 ark-game-analysis 同層", )
    r = subprocess.run([sys.executable, str(p), *args], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout + r.stderr)[-1200:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", help="輸出目錄（預設 <run>/report）")
    ap.add_argument("--html", action="store_true", help="同時產 View 軌 HTML 並寫雙軌戳記")
    ap.add_argument("--publish", help="複製到此 reports 目錄並 report_register（如 docs/reports）")
    ap.add_argument("--wiki-schema", help="report_lint 加驗 tags 白名單的 schema.md")
    ap.add_argument("--date", help="覆寫報告日期（預設取 manifest.stages.analyze.at 的日期，deterministic）")
    a = ap.parse_args()

    run = C.run_dir(a.run)
    inp = load_inputs(run)
    s = compute_stats(inp)
    findings = build_findings(s, inp)
    at = ((inp["manifest"].get("stages") or {}).get("analyze") or {}).get("at") or ""
    date = a.date or (at[:10] if re.match(r"\d{4}-\d{2}-\d{2}", at) else __import__("datetime").date.today().isoformat())
    run_id = inp["ga"].get("run_id", run.name)
    slug = re.sub(r"[^a-z0-9-]+", "-", run_id.lower()).strip("-")
    md_name = f"{date}-game-analysis-{slug}.md"
    out = pathlib.Path(a.out) if a.out else run / "report"
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / md_name
    md_text = render_md(inp, s, findings, date, md_name)
    C.atomic_write(md_path, md_text)

    lint_args = ([ "--wiki-schema", a.wiki_schema] if a.wiki_schema else []) + [str(md_path)]
    rc, lint_out = run_tool("report_lint.py", *lint_args)
    result = {"md": str(md_path), "lint": "PASS" if rc == 0 else "FAIL", "lint_output": lint_out.strip().splitlines()[-6:],
              "verdict": verdict_of(s, findings)[0], "coverage_pct": s["coverage_pct"],
              "findings": {k: sum(1 for x in findings if x["sev"] == k) for k in ("P0", "P1", "P2", "P3")}}
    if rc != 0:
        C.fail("QUERY_FAILED", "ga_report 產出未通過 report_lint（引擎 bug，請勿手改報告）", lint_out, result)

    if a.html:
        fm = __import__("yaml").safe_load(md_text.split("\n---\n", 1)[0].lstrip("-\n"))
        html_path = md_path.with_suffix(".html")
        html_path.write_text(render_html(md_text, fm, md_name), encoding="utf-8")
        run_tool("report_pair.py", "stamp", str(md_path), str(html_path))
        prc, _ = run_tool("report_pair.py", "check", str(md_path))
        result["html"] = str(html_path)
        result["pair"] = "OK" if prc == 0 else "STALE"

    if a.publish:
        dst = pathlib.Path(a.publish)
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md_path, dst / md_name)
        if a.html:
            shutil.copy2(md_path.with_suffix(".html"), dst / md_path.with_suffix(".html").name)
            run_tool("report_pair.py", "stamp", str(dst / md_name), str(dst / md_path.with_suffix(".html").name))
        rrc, rout = run_tool("report_register.py", str(dst / md_name))
        result["published"] = str(dst / md_name)
        result["register"] = "OK" if rrc == 0 else rout

    C.stage_record(run, "report", 0.0, md=md_name, verdict=result["verdict"], coverage_pct=s["coverage_pct"])
    C.emit(result, {"stage": "ga_report"})


if __name__ == "__main__":
    main()
