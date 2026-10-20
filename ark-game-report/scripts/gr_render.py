#!/usr/bin/env python3
"""gr_render — report.json → 單檔 HTML（版面 assets/report_template.html），並做資料一致性檢查。

也可單獨使用：任何人把資料整理成 report.json（契約見 references/data-contract.md），就能套版。

用法:
  python gr_render.py --config report.yaml                     # 讀 <data_dir>/report.json，輸出到 out_dir
  python gr_render.py --data report.json --out report.html     # 不用設定檔
  python gr_render.py --data report.json --check               # 只檢查覆蓋率與一致性
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gr_common as C  # noqa: E402

SECTIONS = {
    "Q1 規模": ["kpi", "share.game"], "Q1 歷史基準": ["share.bench_p50"],
    "Q2 玩家結構": ["composition"], "Q3 黏著": ["retention.game", "retention.cohorts"], "Q3 歷史基準": ["retention.bench"],
    "Q4 深度": ["depth.rows"], "Q5 RTP": ["rtp.actual_cum"], "Q5 觸發率": ["triggers"],
    "Q6 增量": ["sources", "increment"], "健康觀察": ["health.tiles"], "健康：時段": ["health.hours"],
}


def get(d, path):
    for k in path.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def check(data: dict) -> dict:
    errs = [f"meta.{k} 缺少" for k in ("game_name", "launch_date", "data_through", "stage") if k not in (data.get("meta") or {})]
    if not data.get("views"):
        errs.append("views 為空")
    cov = {}
    for vn, v in (data.get("views") or {}).items():
        cov[vn] = {s: ("OK" if all(get(v, p) not in (None, [], {}) for p in ps) else "缺") for s, ps in SECTIONS.items()}
        s = v.get("share") or {}
        for k in ("game", "bench_p50", "bench_p30", "bench_p60"):
            if s.get(k) and len(s[k]) != len(s.get("days", [])):
                errs.append(f"[{vn}] share.{k} 長度 ≠ days")
        r = v.get("retention") or {}
        for c in r.get("cohorts", []):
            if len(c.get("values", [])) != len(r.get("days", [])):
                errs.append(f"[{vn}] cohort {c.get('date')} 欄數 ≠ retention.days")
        for comp in v.get("composition", []):
            for k in ("game", "all"):
                t = sum(comp.get(k) or [])
                if comp.get(k) and abs(t - 1) > 0.02:
                    errs.append(f"[{vn}] composition「{comp.get('title')}」{k} 加總 {t:.3f}")
    return {"errors": errs, "coverage": cov}


def render(data: dict, out: pathlib.Path) -> None:
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    html = (C.ASSETS / "report_template.html").read_text(encoding="utf-8").replace("__REPORT_DATA__", payload)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="report.json → HTML")
    ap.add_argument("--config")
    ap.add_argument("--data")
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    cfg = C.load_config(a.config) if a.config else None
    src = pathlib.Path(a.data) if a.data else (C.data_dir(cfg) / "report.json" if cfg else None)
    if not src or not src.is_file():
        C.fail("BAD_INPUT", f"找不到 report.json：{src}", "先跑 gr_run.py build，或用 --data 指定")
    data = json.loads(src.read_text(encoding="utf-8"))
    rep = check(data)
    if a.check or rep["errors"]:
        if rep["errors"]:
            C.fail("GATE_BLOCKED", f"資料一致性錯誤 {len(rep['errors'])} 筆", "見 data.errors", rep)
        C.emit(rep, {"stage": "render-check"})
        return
    m = data["meta"]
    if a.out:
        out = pathlib.Path(a.out)
    elif cfg:
        out = pathlib.Path(cfg.get("out_dir") or ".") / f"{m['data_through']}-{cfg['game'].get('slug', 'game')}-d{m['stage']}.html"
    else:
        out = src.with_suffix(".html")
    render(data, out)
    if cfg:  # 定版：report.json 跟 HTML 放一起，之後可重渲染
        shutil.copyfile(src, out.with_suffix(".json"))
    C.emit({"html": str(out), "coverage": rep["coverage"]}, {"stage": "render"})


if __name__ == "__main__":
    main()
