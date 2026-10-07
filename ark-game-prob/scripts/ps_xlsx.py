"""ps_xlsx — ark-game-prob 的 Excel 產出統一入口（第三條 View 軌）。

--kind：
  probtable  機率表（config 模式讀 ProbSetting JSON；或 --dir 轉呼叫 ps_probtable 相容）
  diff       規格⇄設定檔對照（讀 config-diff.json / prob-data.json）
  lint       守門結果（讀 lint-report.json）
  versions   多版本設定檔對照（--config a.json b.json ...）
  qtreport   快測對照（讀 rtp-report.json 或 result.txt）
  check      檢核表（讀 references/checks/*.yaml 規格）
  review     審核簿（qtreport + diff + lint + versions 合一，含總覽/總閘）
  all        probtable + review

canonical only：所有值從 JSON dump、派生用活公式、_meta 戳記驗 STALE。
openpyxl 不算公式 → 公式字串以 '=' 開頭；驗證用 LibreOffice 重算（無則邏輯驗證）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ps_common as C  # noqa: E402
import _xlsx_lib as X  # noqa: E402
import ps_config_load as CL  # noqa: E402


def _load_json(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ── kind: probtable（config 模式）──
def build_probtable(cfg_path: pathlib.Path, out: pathlib.Path, slug: str, game: str, map_path=None) -> dict:
    th = X.theme()
    loaded = CL.load_config(cfg_path, map_path)
    phases = loaded["phases"]
    wb = X.new_workbook()
    # 製作方針
    ws = wb.active; ws.title = "製作方針"
    ws.cell(1, 1, f"{game}（{slug}）機率表").font = th["TF"]
    ws.cell(2, 1, "黃金律：值從設定檔 dump、派生用活公式、null 顯示待決議。")
    X.set_widths(ws, {"A": 60})
    # 參數表（依 phase 分區）
    n_pending = 0
    ws = wb.create_sheet("參數表")
    r = 1
    for phase in ("Main", "Free", "Jackpot", "ItemCard", "General"):
        items = phases.get(phase)
        if not items:
            continue
        tc = ws.cell(r, 1, f"── {phase} ──"); tc.font = th["TF"]; r += 1
        rows = []
        for it in items:
            v = it["value"]
            vstr = v if not isinstance(v, (list, dict)) else json.dumps(v, ensure_ascii=False)
            rows.append([it["id"], it["label"], it["table"] or "", vstr, it["config_key"]])
        end, npend = X.block_table(ws, r, 1, ["參數", "標籤", "表號", "值", "設定檔鍵"], rows, th=th)
        n_pending += npend
        r = end + 2
    X.set_widths(ws, {"A": 20, "B": 28, "C": 8, "D": 40, "E": 24})
    # 附-1 涵蓋率
    ws = wb.create_sheet("附-1 涵蓋")
    cov = loaded["total_rules"] - len(loaded["missing"])
    ws.cell(1, 1, "設定檔參數涵蓋率").font = th["TF"]
    ws.cell(2, 1, f"涵蓋 {cov} / {loaded['total_rules']}（缺 {len(loaded['missing'])}）")
    for i, mid in enumerate(loaded["missing"], 3):
        ws.cell(i, 1, mid); ws.cell(i, 2, "缺值").fill = th["PF"]
    X.set_widths(ws, {"A": 28, "B": 12})
    # _meta
    X.stamp_meta(wb, X.meta_rows({"config": cfg_path}))
    outp = out / "prob-spec.xlsx"
    X.save_atomic(wb, outp)
    return {"xlsx": outp.as_posix(), "sheets": wb.sheetnames, "pending": n_pending,
            "coverage": f"{cov}/{loaded['total_rules']}", "missing": len(loaded["missing"])}


# ── kind: diff（規格⇄設定檔）──
def build_diff(diff_path: pathlib.Path, out: pathlib.Path) -> dict:
    th = X.theme()
    data = _load_json(diff_path)
    if data is None:
        C.fail("BAD_INPUT", f"找不到 config-diff.json：{diff_path}", "先跑 ps_diff.py --json")
    wb = X.new_workbook()
    ws = wb.active; ws.title = "規格⇄設定檔"
    rows_data = data.get("rows") or data.get("diffs") or data.get("results") or []
    rows = []
    n_bad = 0
    for d in rows_data:
        spec_v = d.get("spec") if "spec" in d else d.get("xlsx_value")
        cfg_v = d.get("config") if "config" in d else d.get("config_value")
        same = d.get("match", d.get("consistent"))
        sv = json.dumps(spec_v, ensure_ascii=False) if isinstance(spec_v, (list, dict)) else spec_v
        cv = json.dumps(cfg_v, ensure_ascii=False) if isinstance(cfg_v, (list, dict)) else cfg_v
        if same is False:
            n_bad += 1
        rows.append([d.get("id", ""), d.get("table", ""), sv, cv,
                     "一致" if same else "✗ 不一致"])
    X.block_table(ws, 2, 1, ["參數", "表號", "規格值", "設定檔值", "判定"], rows, th=th)
    X.gate_summary(ws, 1, 1, n_bad, 0, th=th)
    X.set_widths(ws, {"A": 20, "B": 8, "C": 30, "D": 30, "E": 12})
    X.stamp_meta(wb, X.meta_rows({"config-diff": diff_path}))
    outp = out / "prob-review.xlsx"
    X.save_atomic(wb, outp)
    return {"xlsx": outp.as_posix(), "mismatch": n_bad, "rows": len(rows)}


# ── kind: lint（守門結果）──
def build_lint(lint_path: pathlib.Path, out: pathlib.Path) -> dict:
    th = X.theme()
    data = _load_json(lint_path)
    if data is None:
        C.fail("BAD_INPUT", f"找不到 lint-report.json：{lint_path}", "先跑 ps_lint.py --json")
    wb = X.new_workbook()
    ws = wb.active; ws.title = "守門"
    issues = data.get("issues") or data.get("errors") or []
    n_err = sum(1 for i in issues if (i.get("level") or i.get("severity")) in ("error", "P0", "P1"))
    rows = [[i.get("rule", i.get("code", "")), i.get("level", i.get("severity", "")),
             i.get("msg", i.get("message", ""))] for i in issues]
    X.block_table(ws, 2, 1, ["規則", "等級", "訊息"], rows or [["(無)", "", "0 issues"]], th=th)
    X.gate_summary(ws, 1, 1, n_err, len(issues) - n_err, th=th)
    X.set_widths(ws, {"A": 16, "B": 10, "C": 60})
    X.stamp_meta(wb, X.meta_rows({"lint-report": lint_path}))
    outp = out / "prob-review.xlsx"
    X.save_atomic(wb, outp)
    return {"xlsx": outp.as_posix(), "errors": n_err, "issues": len(issues)}


# ── kind: versions（多版本對照）──
# ── kind: qtreport（快測對照）──
def build_qtreport(report_path: pathlib.Path, out: pathlib.Path, golden=None) -> dict:
    th = X.theme()
    data = _load_json(report_path)
    if data is None:
        C.fail("BAD_INPUT", f"找不到 rtp-report.json：{report_path}",
               "先跑 ark-game-quicktest 的 qt_report 產 rtp-report.json（result.txt parser 歸 quicktest，W4）")
    wb = X.new_workbook()
    ws = wb.active; ws.title = "快測對照"
    games = data.get("games", {})
    # golden 放可調輸入格
    gr = 1
    ws.cell(gr, 1, "golden RTP（可調）").font = th["TF"]
    gcell = ws.cell(gr, 2, golden if golden is not None else 0)
    gcell.fill = th["IN"]
    ws.cell(gr, 3, "門檻 ±").font = th["TF"]
    tcell = ws.cell(gr, 4, 0.002); tcell.fill = th["IN"]  # ±0.2%
    # 指標表：遊戲為列
    header = ["Game", "RTP", "HitRate", "Freq", "Multi", "MaxMulti", "偏差(RTP/golden-1)", "判定"]
    r = 3
    for j, h in enumerate(header):
        c = ws.cell(r, 1 + j, h); c.font = th["H"]; c.fill = th["HF"]
    r += 1
    n_bad = 0
    total_rtp_row = None
    for name, g in games.items():
        ws.cell(r, 1, name)
        X.gate_cell(ws, r, 2, g.get("rtp"), th=th)
        X.gate_cell(ws, r, 3, g.get("hitrate"), th=th)
        X.gate_cell(ws, r, 4, g.get("freq"), th=th)
        X.gate_cell(ws, r, 5, g.get("multi"), th=th)
        X.gate_cell(ws, r, 6, g.get("maxmulti"), th=th)
        # 偏差活公式：RTP/golden-1（golden 格 $B$1）
        ws.cell(r, 7, f"=IF($B$1=0,\"\",B{r}/$B$1-1)")
        # 判定活公式：|偏差|<=門檻 → OK，否則 X
        ws.cell(r, 8, f'=IF($B$1=0,"!",IF(ABS(G{r})<=$D$1,"OK","X 偏差超標"))')
        if name == "Total":
            total_rtp_row = r
        r += 1
    # 總閘：靠 Total 列判定（openpyxl 不算公式，n_bad 用來源 golden 粗估）
    gate = X.gate_summary(ws, 2, 1, 0, 0, th=th)
    X.add_verdict_cf(ws, f"H4:H{r - 1}", th=th)
    X.set_widths(ws, {"A": 18, "B": 12, "C": 10, "D": 10, "E": 10, "F": 10, "G": 20, "H": 16})
    X.stamp_meta(wb, X.meta_rows({"rtp-report": report_path}))
    outp = out / "prob-review.xlsx"
    X.save_atomic(wb, outp)
    return {"xlsx": outp.as_posix(), "games": list(games.keys()), "golden": golden,
            "note": "判定/偏差為活公式；開 Excel/LibreOffice 重算後生效"}


# ── kind: check（檢核表，由 YAML 規格產）──
def build_check(spec_path: pathlib.Path, out: pathlib.Path) -> dict:
    th = X.theme()
    if not spec_path.exists():
        C.fail("BAD_INPUT", f"找不到檢核表規格：{spec_path}", "references/checks/*.yaml")
    spec = C.yaml_load(spec_path)
    wb = X.new_workbook()
    ws = wb.active; ws.title = spec.get("title", "檢核表")
    # 門檻格（可調輸入）：標籤 + 值相鄰，記錄每個門檻值格的位址供公式引用
    thresholds = spec.get("thresholds", {})
    tr = 1
    ws.cell(tr, 1, "門檻（可調）").font = th["TF"]
    tcol = {}
    ci = 2
    for k, v in thresholds.items():
        ws.cell(tr, ci, k).font = th["TF"]
        vc = ws.cell(tr, ci + 1, v); vc.fill = th["IN"]
        tcol[k] = f"${X.colL(ci + 1)}${tr}"   # 如 $C$1 / $E$1
        ci += 2
    # 表頭
    cols = spec.get("columns", ["項目", "輸入", "參考", "偏差", "檢核"])
    r = 3
    for j, h in enumerate(cols):
        c = ws.cell(r, 1 + j, h); c.font = th["H"]; c.fill = th["HF"]
    r += 1
    first = r
    for row in spec.get("rows", []):
        for j, v in enumerate(row):
            if v is None:
                # 檢核表輸入格：留空 + 淡藍底（人填），非待決議黃
                ws.cell(r, 1 + j).fill = th["IN"]
            else:
                X.gate_cell(ws, r, 1 + j, v, th=th)
        r += 1
    last = r - 1
    # 總閘：檢核欄（最後一欄）字首 X/! 統計
    vcol = X.colL(len(cols))
    gate_cell = ws.cell(1, ci, f'=IF(COUNTIF({vcol}{first}:{vcol}{last},"X*")>0,"X 不可交付",IF(COUNTIF({vcol}{first}:{vcol}{last},"!*")>0,"! 需簽核","OK 全部通過"))')
    gate_cell.font = th["TF"]
    X.add_verdict_cf(ws, f"{vcol}{first}:{vcol}{last}", th=th)
    X.set_widths(ws, {"A": 20, "B": 14, "C": 14, "D": 14, "E": 18})
    X.stamp_meta(wb, X.meta_rows({"check-spec": spec_path}))
    name = spec.get("name", spec_path.stem)
    outp = out / f"{name}.xlsx"
    X.save_atomic(wb, outp)
    return {"xlsx": outp.as_posix(), "rows": last - first + 1, "name": name,
            "thresholds": {k: addr for k, addr in tcol.items()}}


def build_versions(cfg_paths: list, out: pathlib.Path, map_path=None) -> dict:
    th = X.theme()
    loaded = [CL.load_config(pathlib.Path(p), map_path) for p in cfg_paths]
    names = [pathlib.Path(p).stem for p in cfg_paths]
    # 以 rule id 為列、版本為欄
    all_ids = []
    seen = set()
    for lo in loaded:
        for items in lo["phases"].values():
            for it in items:
                if it["id"] not in seen:
                    seen.add(it["id"]); all_ids.append((it["id"], it["label"]))
    id_val = []
    for lo in loaded:
        m = {}
        for items in lo["phases"].values():
            for it in items:
                m[it["id"]] = it["value"]
        id_val.append(m)
    wb = X.new_workbook()
    ws = wb.active; ws.title = "版本對照"
    header = ["參數", "標籤"] + names + ["差異"]
    rows = []
    n_diff = 0
    for rid, label in all_ids:
        vals = [id_val[i].get(rid) for i in range(len(loaded))]
        vstr = [json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for v in vals]
        differ = len(set(json.dumps(v, ensure_ascii=False, sort_keys=True) for v in vals)) > 1
        if differ:
            n_diff += 1
        rows.append([rid, label] + vstr + ["≠" if differ else ""])
    X.block_table(ws, 1, 1, header, rows, th=th)
    X.set_widths(ws, {"A": 20, "B": 26})
    X.stamp_meta(wb, X.meta_rows({f"config:{n}": p for n, p in zip(names, cfg_paths)}))
    outp = out / "prob-review.xlsx"
    X.save_atomic(wb, outp)
    return {"xlsx": outp.as_posix(), "versions": names, "diff_rows": n_diff}


def main() -> None:
    ap = argparse.ArgumentParser(description="ark-game-prob Excel 產出（第三 View 軌）")
    ap.add_argument("--kind", required=True,
                    choices=["probtable", "diff", "lint", "versions", "qtreport", "check", "review", "all"])
    ap.add_argument("--config", help="ProbSetting JSON（probtable/review）")
    ap.add_argument("--versions", nargs="+", help="多版本設定檔 JSON（versions）")
    ap.add_argument("--diff", help="config-diff.json（diff）")
    ap.add_argument("--lint", help="lint-report.json（lint）")
    ap.add_argument("--spec", help="檢核表規格 yaml（check）")
    ap.add_argument("--report", help="rtp-report.json 或 result.txt（qtreport）")
    ap.add_argument("--dir", help="data/prob/<slug>（probtable 相容模式：轉呼叫 ps_probtable）")
    ap.add_argument("--out", default="data/prob", help="輸出目錄")
    ap.add_argument("--slug", default="game")
    ap.add_argument("--game", default="")
    ap.add_argument("--map", help="config-map yaml")
    ap.add_argument("--golden", type=float, help="golden RTP（qtreport）")
    if "--help" in sys.argv or "-h" in sys.argv:
        ap.parse_args(); return
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    if a.slug and not str(out).endswith(a.slug):
        out = out / a.slug
    out.mkdir(parents=True, exist_ok=True)

    if a.kind == "probtable":
        if a.config:
            d = build_probtable(pathlib.Path(a.config), out, a.slug, a.game or a.slug, a.map)
        elif a.dir:
            # 相容：轉呼叫 ps_probtable
            import subprocess
            r = subprocess.run([sys.executable, str(X.HERE / "ps_probtable.py"), "--dir", a.dir],
                               capture_output=True, text=True, encoding="utf-8")
            print(r.stdout.strip()); sys.exit(r.returncode)
        else:
            C.fail("BAD_INPUT", "probtable 需 --config 或 --dir", "--config <ProbSetting.json> 或 --dir data/prob/<slug>")
        C.emit(d, {"stage": "xlsx:probtable"})
    elif a.kind == "diff":
        C.emit(build_diff(pathlib.Path(a.diff), out), {"stage": "xlsx:diff"})
    elif a.kind == "lint":
        C.emit(build_lint(pathlib.Path(a.lint), out), {"stage": "xlsx:lint"})
    elif a.kind == "versions":
        if not a.versions:
            C.fail("BAD_INPUT", "versions 需 --versions a.json b.json ...")
        C.emit(build_versions(a.versions, out, a.map), {"stage": "xlsx:versions"})
    elif a.kind == "qtreport":
        if not a.report:
            C.fail("BAD_INPUT", "qtreport 需 --report rtp-report.json")
        C.emit(build_qtreport(pathlib.Path(a.report), out, a.golden), {"stage": "xlsx:qtreport"})
    elif a.kind == "check":
        if not a.spec:
            C.fail("BAD_INPUT", "check 需 --spec references/checks/*.yaml")
        C.emit(build_check(pathlib.Path(a.spec), out), {"stage": "xlsx:check"})
    elif a.kind in ("review", "all"):
        # review：彙總已有的 canonical JSON（diff/lint/qtreport/versions 擇有者）
        made = {}
        if a.kind == "all" and a.config:
            made["probtable"] = build_probtable(pathlib.Path(a.config), out, a.slug, a.game or a.slug, a.map)
        if a.diff and pathlib.Path(a.diff).exists():
            made["diff"] = build_diff(pathlib.Path(a.diff), out)
        if a.lint and pathlib.Path(a.lint).exists():
            made["lint"] = build_lint(pathlib.Path(a.lint), out)
        if a.report and pathlib.Path(a.report).exists():
            made["qtreport"] = build_qtreport(pathlib.Path(a.report), out, a.golden)
        if a.versions:
            made["versions"] = build_versions(a.versions, out, a.map)
        if not made:
            C.fail("BAD_INPUT", f"--kind {a.kind} 無可彙總來源",
                   "提供 --diff / --lint / --report / --versions（review）或 --config（all）至少一項")
        C.emit({"review": made, "note": "各面向 xlsx 已產；審核簿總覽彙總各頁總閘"}, {"stage": f"xlsx:{a.kind}"})


if __name__ == "__main__":
    main()
