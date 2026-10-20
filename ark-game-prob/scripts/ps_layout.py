#!/usr/bin/env python3
"""ps_layout — 一款遊戲的產出佈局守門（layout_check）：`output/games/<slug>/{spec, prob, quicktest, docs}/`。

狀態卡（LAYOUT.md）不再手寫：本腳本實際讀檔、比 sha、比數字，產 `layout-report.json`，`--write-md` 時一併重寫 LAYOUT.md。
規範：aidev docs/designs/2026-10-07-game-pipeline-output-layout.md；單一版本原則（一款一份設定檔，例：A 版）。

規則（error 擋畢業；warning 列出不擋）：
  L-DIRS     prob/、quicktest/ 必須存在；design 模式另需 spec/；analysis/①、server/⑥、docs/ 選配
  L-STRAY    出現 data/prob/<slug>/ 這類多一層的舊佈局 → error（請用 ps_run --dest <game>/prob 重產後移除）
  L-PROB     prob/ 需有 prob-spec.md / .meta.json / .html / lint-report.json；md frontmatter source_skill 必須是 ark-game-prob
             （非 skill 產物 → error）；ps_lint 重跑 0 error
  L-STAMP    prob/、docs/、analysis/report/、spec/、quicktest/qt-report/、game/（契約 v3.5：定版家 md 旁的 html）下每個 .html：同名 .md 存在時，content-src 戳記的 sha 必須 = 該 md 的 sha16（綁錯對象 / 過期 → error；無戳記 → warning）
  L-SPEC     config-spec.yaml：<game>/spec/ 為規範位置（只在 quicktest/ → warning）；mode restore-live 時 $ref 全可解析、設定檔 sha 一致、鍵全覆蓋
  L-QT       quicktest/quicktest.yaml 需有 target_rtp；qt-report/rtp-report.json 存在；gate.verdict confirmed（rejected → error、inconclusive → warning）
  L-DIFF     prob/config-diff.json：mismatch > 0 → error；沒有 → warning（還原模式建議跑 ps_run --config）
  L-SIZE     體積守門（設計文件 §2，data/slot/<slug> 目標 < 1 MB）：*.exe/*.dll/*.bin 進 game → error；
             單檔 > 500 KB（排除 *.html View 軌與 _retired/）→ warning；quicktest/config/ 有 > 1 個 *.json（多版本設定檔，違反單一版本原則）→ error
  L-SERVER   server/handoff.md 存在時：frontmatter 的 config_sha256_16 / rtp_report_sha256_16 必須 = 現檔實算 sha
             （不符 → error；只對帳交付件來源，不改 server code）；無 handoff.md → 不報（⑥ 選配）
  L-REVIEW   review/ 拍板包（契約 v3.3，選配）：總量 > 5 MB → error；二進位／影片 → error；有 review/ 但缺 index.html → warning；
             review-manifest.json 列的檔案（files）與連到的定版家成品（links，v3.5）不存在或 sha 不符 → warning（拍板包過期，送審前重跑 review_build）
  L-RTP      docs/ 下（人寫的）md 提到的「Total RTP / 總 RTP」實測數字 ≠ rtp-report（±0.01 個百分點）→ warning（列檔名:行號；數字前後出現 golden／目標／理論／參數表者略過）

用法: python ps_layout.py --game output/games/<slug> [--mode restore|design] [--write-md] [--strict]
exit: 0 PASS / 3 有 error（--strict 時 warning 也算）/ 2 BAD_INPUT
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps_common as C  # noqa: E402

STAMP_RE = re.compile(r"([\w\-.]+\.md)\s+sha256:([0-9a-f]{16})")
RTP_RE = re.compile(r"(?:Total\s*RTP|總\s*RTP|總計\s*RTP)\D{0,30}?(\d{2,3}\.\d{1,4})\s*%", re.I)
PROB_FILES = ("prob-spec.md", "prob-spec.meta.json", "prob-spec.html", "lint-report.json")


def fm_get(md: str, key: str):
    if not md.startswith("---"):
        return None
    end = md.find("\n---", 3)
    m = re.search(rf"^{re.escape(key)}:\s*(.+)$", md[3:end] if end > 0 else "", re.M)
    return m.group(1).strip().strip('"\'') if m else None


def resolve_ref(ref: str, base: pathlib.Path):
    path, _, frag = ref.partition("#")
    cur = json.loads((base / path).read_text(encoding="utf-8"))
    for tok in [t for t in frag.split("/") if t]:
        tok = tok.replace("~1", "/").replace("~0", "~")
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


def check(game: pathlib.Path, mode: str) -> dict:
    V: list[dict] = []
    facts: dict = {}

    def add(rule, where, msg, sev="error"):
        V.append({"rule": rule, "severity": sev, "where": where, "message": msg})

    rel = lambda p: p.relative_to(game).as_posix() if p.is_relative_to(game) else p.as_posix()  # noqa: E731
    slug = game.name
    prob, qt, spec, docs = game / "prob", game / "quicktest", game / "spec", game / "docs"
    analysis, server = game / "analysis", game / "server"
    gamedir, proto = game / "game", game / "proto"   # 佈局契約 v3：⑥ proto/、⑦ game/{go-server,pixi-client}

    # L-DIRS（analysis/①、server/⑥、docs/ 為選配，認識但不強制）
    for d, need in ((prob, True), (qt, True), (spec, mode == "design")):
        if not d.is_dir():
            add("L-DIRS", rel(d), f"缺 {d.name}/", "error" if need else "warning")
    facts["dirs"] = {d.name: d.is_dir() for d in (prob, qt, spec, analysis, proto, gamedir, server, docs)}
    # L-STRAY
    for stray in sorted(game.glob("data/prob/*")) + sorted(game.glob("data/quicktest/*")):
        if stray.is_dir():
            add("L-STRAY", rel(stray), "舊佈局多一層（data/<kind>/<slug>/）：用 ps_run --dest <game>/prob 重產到規範位置後移除此目錄")

    # L-PROB
    if prob.is_dir():
        for f in PROB_FILES:
            if not (prob / f).exists():
                add("L-PROB", f"prob/{f}", "缺 skill 標準輸出檔")
        md_p = prob / "prob-spec.md"
        if md_p.exists():
            md = md_p.read_text(encoding="utf-8")
            src_skill = fm_get(md, "source_skill")
            facts["prob_source_skill"] = src_skill
            if src_skill != "ark-game-prob":
                add("L-PROB", "prob/prob-spec.md", f"不是 ark-game-prob 產物（source_skill={src_skill}）：用 ps_run 重產，自寫腳本退役")
            try:
                import ps_lint
                rep = ps_lint.lint(prob)
                s = rep["summary"]
                facts["ps_lint"] = s
                if s.get("errors"):
                    add("L-PROB", "prob/", f"ps_lint {s['errors']} error：" + "；".join(v["message"] for v in rep["violations"] if v["severity"] == "error")[:300])
            except SystemExit:
                add("L-PROB", "prob/", "ps_lint 無法執行（缺 meta 或來源）")
            except Exception as e:  # noqa: BLE001
                add("L-PROB", "prob/", f"ps_lint 例外：{e}")

    # L-STAMP
    for base in (prob, docs, game / "analysis" / "report", spec, qt / "qt-report", game / "game"):
        if not base.is_dir():
            continue
        for h in sorted(base.rglob("*.html")):
            if "_retired" in h.parts:
                continue
            txt = h.read_text(encoding="utf-8", errors="replace")
            head = txt[:4000] + txt[-4000:]          # ps_html 戳記在檔頭；ark-md-report report_pair 戳記在檔尾（1.4.3）
            sib = h.with_suffix(".md")
            stamps = STAMP_RE.findall(head)
            if not sib.exists():
                continue
            if not stamps:
                add("L-STAMP", rel(h), f"無 content-src 戳記，無法偵測與 {sib.name} 的漂移", "warning")
                continue
            want = C.sha16(sib)
            if not any(sha == want for _, sha in stamps):
                names = ", ".join(f"{n}:{sha}" for n, sha in stamps)
                add("L-STAMP", rel(h), f"戳記（{names}）≠ 同名 {sib.name} 的 sha {want}：綁錯對象或 md 改了未重渲染")

    # L-SPEC
    cs_p = next((p for p in (spec / "config-spec.yaml", qt / "config-spec.yaml") if p.exists()), None)
    facts["config_spec"] = rel(cs_p) if cs_p else None
    if not cs_p:
        add("L-SPEC", "spec/config-spec.yaml", "缺 config-spec（還原模式：ark-game-spec gs_run --stage restore）")
    else:
        if cs_p.parent != spec:
            add("L-SPEC", rel(cs_p), "config-spec 不在規範位置 spec/", "warning")
        cs = C.yaml_load(cs_p) or {}
        if mode == "restore" and cs.get("mode") != "restore-live":
            add("L-SPEC", rel(cs_p), f"還原模式需 mode: restore-live（現為 {cs.get('mode')}）")
        if cs.get("mode") == "restore-live":
            # 設定檔來源兩種寫法皆接受：sources.config（巢狀）或頂層 source_config（扁平）
            src = (cs.get("sources") or {}).get("config") or cs.get("source_config") or {}
            cfg_p = cs_p.parent / str(src.get("path") or "")
            if not src.get("path") or not cfg_p.is_file():
                add("L-SPEC", rel(cs_p), f"restore-live 找不到設定檔來源 sources.config / source_config（{src.get('path')}）")
            else:
                facts["config"] = {"path": rel(cfg_p.resolve()) if cfg_p.resolve().is_relative_to(game.resolve()) else cfg_p.as_posix(), "sha256_16": C.sha16(cfg_p)}
                if src.get("sha256_16") != C.sha16(cfg_p):
                    add("L-SPEC", rel(cs_p), "設定檔 sha 已變：重跑 gs_run --stage restore")
                cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
                names, bad = set(), []
                for prm in cs.get("parameters") or []:
                    names.add(prm.get("name"))
                    v = prm.get("value")
                    try:
                        if not (isinstance(v, dict) and "$ref" in v):
                            raise ValueError
                        resolve_ref(v["$ref"], cs_p.parent)
                    except Exception:  # noqa: BLE001
                        bad.append(str(prm.get("name")))
                miss = sorted(set(cfg) - names)
                facts["config_spec_keys"] = f"{len(names & set(cfg))}/{len(cfg)}"
                if bad:
                    add("L-SPEC", rel(cs_p), "value 非 $ref 或解析失敗：" + ", ".join(bad[:10]))
                if miss:
                    add("L-SPEC", rel(cs_p), f"設定檔 {len(miss)} 鍵未列入：" + ", ".join(miss[:10]))

    # L-QT
    rtp_total = None
    tgt = qt / "quicktest.yaml"
    if not tgt.exists():
        add("L-QT", "quicktest/quicktest.yaml", "缺快測目標檔（ark-game-quicktest qt_target.py）")
    else:
        t = C.yaml_load(tgt) or {}
        if t.get("target_rtp") is None:
            add("L-QT", "quicktest/quicktest.yaml", "缺 target_rtp")
        facts["target_rtp"] = t.get("target_rtp")
    rr = qt / "qt-report" / "rtp-report.json"
    if not rr.exists():
        add("L-QT", "quicktest/qt-report/rtp-report.json", "缺快測報告（qt_report）")
    else:
        rep = json.loads(rr.read_text(encoding="utf-8"))
        rtp_total = rep.get("rtp_total")
        verdict = (rep.get("gate") or {}).get("verdict")
        facts["rtp_report"] = {"rtp_total": rtp_total, "spins": rep.get("spins"), "verdict": verdict, "sha256_16": C.sha16(rr)}
        if verdict == "rejected":
            add("L-QT", rel(rr), "三向 verdict rejected")
        elif verdict != "confirmed":
            add("L-QT", rel(rr), f"三向 verdict {verdict}（缺目標或 config-spec → 有向 SKIP）", "warning")

    # L-DIFF
    cd = prob / "config-diff.json"
    if cd.exists():
        summ = (json.loads(cd.read_text(encoding="utf-8")).get("summary") or {})
        facts["config_diff"] = summ
        if summ.get("mismatch"):
            add("L-DIFF", "prob/config-diff.json", f"規格 ⇄ 設定檔不一致 {summ['mismatch']} 條：機率人員裁定後改正，重跑 ps_run --config")
    else:
        add("L-DIFF", "prob/config-diff.json", "沒有規格 ⇄ 設定檔對照（ps_run --xlsx … --config <設定檔>）", "warning")

    # L-SIZE（體積守門：設計文件 §2，data/slot/<slug> 目標 < 1 MB、禁二進位、單一版本原則）
    BIN_EXT = (".exe", ".dll", ".bin")
    SIZE_WARN = 500 * 1024
    max_file, exe_count = ("", 0), 0
    review = game / "review"
    for f in game.rglob("*"):
        if not f.is_file() or "_retired" in f.parts or review in f.parents:
            continue
        suf = f.suffix.lower()
        if suf in BIN_EXT:
            exe_count += 1
            add("L-SIZE", rel(f), f"二進位檔不得進 data（{suf}）：移到 output/slot/<slug>/build/")
            continue
        sz = f.stat().st_size
        if sz > max_file[1]:
            max_file = (rel(f), sz)
        if sz > SIZE_WARN and suf != ".html":  # html View 軌允許較大
            add("L-SIZE", rel(f), f"單檔 {sz // 1024} KB > 500 KB：可重產大檔請移到 output/slot/<slug>/", "warning")
    cfg_dir = qt / "config"
    cfg_jsons = sorted(cfg_dir.glob("*.json")) if cfg_dir.is_dir() else []
    if len(cfg_jsons) > 1:
        add("L-SIZE", "quicktest/config/", f"{len(cfg_jsons)} 個設定檔（違反單一版本原則，只收 A 版）：" + ", ".join(p.name for p in cfg_jsons[:6]) + "；其餘移到 output/slot/<slug>/")
    facts["size"] = {"max_file": max_file[0], "max_bytes": max_file[1], "exe_count": exe_count, "config_versions": len(cfg_jsons)}

    # L-REVIEW（契約 v3.3：review/ 拍板包另計 5 MB；給人拍板 / demo 的成品，禁二進位與影片）
    if review.is_dir():
        REVIEW_KB, BAN = 5120, (".exe", ".dll", ".bin", ".so", ".mp4", ".mov", ".webm", ".zip", ".7z")
        files = [f for f in review.rglob("*") if f.is_file()]
        total = sum(f.stat().st_size for f in files)
        for f in files:
            if f.suffix.lower() in BAN:
                add("L-REVIEW", rel(f), f"拍板包不得放二進位／影片（{f.suffix}）")
        if total > REVIEW_KB * 1024:
            add("L-REVIEW", "review/", f"拍板包 {total // 1024} KB > {REVIEW_KB} KB（契約 v3.3）：縮圖品質降一級或精簡 checks/ 截圖")
        if not (review / "index.html").is_file():
            add("L-REVIEW", "review/index.html", "拍板包缺導覽頁（ark-game-proto review_build.py 產生）", "warning")
        man_p, stale = review / "review-manifest.json", []
        if man_p.is_file():
            try:
                man = json.loads(man_p.read_text(encoding="utf-8"))
                for it in man.get("files", []) + man.get("links", []):   # v3.5：links＝拍板書連到的定版家成品
                    fp = review / it["path"]
                    if not fp.is_file() or (it.get("sha256_16") and C.sha16(fp) != it["sha256_16"]):
                        stale.append(it["path"])
            except (json.JSONDecodeError, KeyError, TypeError):
                stale.append("review-manifest.json（無法解析）")
            if stale:
                add("L-REVIEW", "review/review-manifest.json", f"{len(stale)} 個檔與清冊不符：" + ", ".join(stale[:5]) + "（送審前重跑 review_build）", "warning")
        facts["review"] = {"files": len(files), "total_kb": total // 1024, "stale": len(stale)}

    # L-SERVER（⑥ 交付守門：server/handoff.md 的來源 sha 必須與現檔一致；只對帳不改 server code）
    handoff = gamedir / "handoff.md" if (gamedir / "handoff.md").is_file() else server / "handoff.md"
    if handoff.is_file():
        htxt = handoff.read_text(encoding="utf-8", errors="replace")
        srv_facts: dict = {"handoff": True}
        checks = (("config_sha256_16", facts.get("config", {}).get("sha256_16") if isinstance(facts.get("config"), dict) else None),
                  ("rtp_report_sha256_16", facts.get("rtp_report", {}).get("sha256_16") if isinstance(facts.get("rtp_report"), dict) else None))
        for key, want in checks:
            declared = fm_get(htxt, key)
            srv_facts[key] = {"declared": declared, "actual": want}
            if declared and want and declared != want:
                add("L-SERVER", rel(handoff), f"{key} 宣告 {declared} ≠ 現檔 {want}：交付件來源已變，重出 handoff")
        facts["server"] = srv_facts

    # L-RTP
    if rtp_total is not None:
        want = rtp_total * 100
        hits = []
        for base in (docs,):  # prob/ 是 skill 產物（PS-NUM 已保證可回溯）；只掃人寫的 docs/
            if not base.is_dir():
                continue
            for md_f in sorted(base.rglob("*.md")):
                if "_retired" in md_f.parts:
                    continue
                for i, ln in enumerate(md_f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    for m in RTP_RE.finditer(ln):
                        if re.search(r"golden|目標|target|理論|參數表", ln[max(0, m.start() - 25):m.end()], re.I):
                            continue  # 目標值 / 理論值不是實測，不比
                        v = float(m.group(1))
                        if abs(v - want) > 0.01:
                            hits.append(f"{rel(md_f)}:{i}（{v}%）")
        facts["rtp_mentions_mismatch"] = len(hits)
        if hits:
            add("L-RTP", "docs/", f"{len(hits)} 處 Total RTP ≠ rtp-report {want:.4f}%：" + "；".join(hits[:12]) + ("…" if len(hits) > 12 else ""), "warning")

    errs = sum(1 for v in V if v["severity"] == "error")
    warns = sum(1 for v in V if v["severity"] == "warning")
    return {"contract": C.CONTRACT, "kind": "layout-report", "game": slug, "mode": mode, "generated": dt.datetime.now().isoformat(timespec="seconds"),
            "summary": {"errors": errs, "warnings": warns, "verdict": "PASS" if errs == 0 else "FAIL"}, "facts": facts, "violations": V}


def render_md(rep: dict) -> str:
    s = rep["summary"]
    L = [f"# {rep['game']} — 佈局狀態卡（自動產生）", "",
         f"> 由 ark-game-prob `ps_layout.py` 於 {rep['generated']} 產生，**勿手改**；改了產物請重跑 `python ps_layout.py --game <game> --write-md`。",
         f"> 模式：{rep['mode']}｜結果：**{s['verdict']}**（error {s['errors']} / warning {s['warnings']}）", "",
         "## 事實（實際讀檔）", "", "| 項目 | 值 |", "|---|---|"]
    for k, v in rep["facts"].items():
        L.append(f"| {k} | `{json.dumps(v, ensure_ascii=False)}` |")
    L += ["", "## 檢查結果", ""]
    if not rep["violations"]:
        L.append("全部通過。")
    else:
        L += ["| 嚴重度 | 規則 | 位置 | 說明 |", "|---|---|---|---|"]
        for v in sorted(rep["violations"], key=lambda x: (x["severity"] != "error", x["rule"])):
            L.append(f"| {'🔴 error' if v['severity'] == 'error' else '🟡 warning'} | {v['rule']} | `{v['where']}` | {v['message'].replace('|', '／')} |")
    L += ["", "## 畢業判準", "", "error = 0（ps_lint PASS、無舊佈局殘留、html 戳記綁對、config-spec 可驗、三向 confirmed、規格 ⇄ 設定檔一致、無二進位 / 單一設定檔、交付件 sha 對帳）。",
          "warning 不擋，但 L-RTP 代表文件裡還有過期數字、L-SIZE warning 代表有可重產大檔該移到 output/。", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description="遊戲產出佈局守門（output/games/<slug>/）")
    ap.add_argument("--game", required=True, help="output/games/<slug>")
    ap.add_argument("--mode", choices=["restore", "design"], default="restore")
    ap.add_argument("--write-md", action="store_true", help="重寫 <game>/LAYOUT.md")
    ap.add_argument("--strict", action="store_true", help="warning 也算失敗")
    a = ap.parse_args()
    game = pathlib.Path(a.game).resolve()
    if not game.is_dir():
        C.fail("BAD_INPUT", f"找不到 {a.game}")
    rep = check(game, a.mode)
    C.atomic_write(game / "layout-report.json", json.dumps(rep, ensure_ascii=False, indent=1))
    if a.write_md:
        C.atomic_write(game / "LAYOUT.md", render_md(rep))
    s = rep["summary"]
    deliver = f"ps_layout {rep['game']}｜{a.mode}｜{s['verdict']}｜error {s['errors']} / warning {s['warnings']}"
    data = {**s, "report": (game / "layout-report.json").as_posix(), "violations": rep["violations"], "delivery": deliver}
    if s["errors"] or (a.strict and s["warnings"]):
        C.fail("GATE_BLOCKED", "佈局守門未通過", deliver, data)
    C.emit(data, {"stage": "ps_layout"})


if __name__ == "__main__":
    main()
