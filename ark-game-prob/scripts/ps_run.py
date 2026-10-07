#!/usr/bin/env python3
"""ps_run — 一鍵：機率表 xlsx → prob-data.json → prob-spec.md(+meta) → prob-spec.html → ps_lint [→ ps_diff]。

  python ps_run.py --xlsx <機率表.xlsx> --out data/prob --slug <slug> [--game <名>] [--config <快測設定檔.json> [--map <map.yaml>]] [--xlsx-view]
  python ps_run.py --qt data/quicktest/<slug> [--out data/prob]      # qt 模式（新遊戲設計鏈）：ps_probspec --qt → ps_html → ps_lint

每步以 subprocess 執行同目錄腳本（F-6：stdout 一律 UTF-8；失敗即停並回傳該步的 envelope）。
--xlsx-view 另產公版 prob-spec.xlsx（ps_probtable，需 qt 模式來源；xlsx 模式下來源本身就是公版表，預設略過）。
交付格式：ps_run <mode>｜<slug>｜ps_lint PASS/FAIL｜<N> 處待決議｜[ps_diff 一致 a / 不一致 b]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps_common as C  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


def step(name: str, args: list[str]) -> dict:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    p = subprocess.run([sys.executable, "-X", "utf8", str(HERE / name), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    out = (p.stdout or "").strip().splitlines()
    env_line = next((ln for ln in reversed(out) if ln.startswith("{")), "")
    try:
        data = json.loads(env_line) if env_line else {}
    except json.JSONDecodeError:
        data = {}
    if p.returncode != 0 and name != "ps_lint.py":
        C.fail(data.get("error", {}).get("code", "QUERY_FAILED"), f"{name} 失敗（rc={p.returncode}）", (p.stderr or "")[-600:] or env_line[-600:], data)
    return {"rc": p.returncode, "env": data, "stderr": (p.stderr or "")[-400:]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", help="xlsx 模式：公版機率表")
    ap.add_argument("--qt", help="qt 模式：data/quicktest/<slug>")
    ap.add_argument("--out", default="data/prob")
    ap.add_argument("--slug")
    ap.add_argument("--game")
    ap.add_argument("--config", help="選配：快測設定檔 JSON → 跑 ps_diff")
    ap.add_argument("--map", help="ps_diff 對照規則 yaml")
    ap.add_argument("--xlsx-view", action="store_true", help="qt 模式：另產公版 prob-spec.xlsx（= --excel probtable）")
    ap.add_argument("--excel", nargs="*", help="產 Excel View 軌：kinds 空=all；可指定 probtable/diff/lint/qtreport/review")
    ap.add_argument("--versions", nargs="+", help="--excel versions 用的多版本設定檔")
    ap.add_argument("--report", help="--excel qtreport 用的 rtp-report.json")
    ap.add_argument("--golden", type=float, help="--excel qtreport 的 golden RTP")
    ap.add_argument("--diff-warn-only", action="store_true")
    a = ap.parse_args()
    if not a.xlsx and not a.qt:
        C.fail("BAD_INPUT", "需要 --xlsx 或 --qt")
    steps: dict[str, dict] = {}
    if a.xlsx:
        slug = a.slug or pathlib.Path(a.xlsx).stem.split("_")[0]
        out_dir = pathlib.Path(a.out) / slug
        args = ["--xlsx", a.xlsx, "--out", str(out_dir), "--slug", slug] + (["--game", a.game] if a.game else [])
        steps["extract"] = step("ps_extract.py", args)
        steps["probspec"] = step("ps_probspec.py", ["--data", str(out_dir / "prob-data.json"), "--out", a.out, "--slug", slug])
        mode = "xlsx"
    else:
        slug = a.slug or pathlib.Path(a.qt).name
        out_dir = pathlib.Path(a.out) / slug
        steps["probspec"] = step("ps_probspec.py", ["--qt", a.qt, "--out", a.out, "--slug", slug])
        if a.xlsx_view:
            steps["probtable"] = step("ps_probtable.py", ["--dir", str(out_dir)])
        mode = "qt"
    if (out_dir / "prob-data.json").exists():
        steps["html"] = step("ps_html.py", ["--dir", str(out_dir)])
    steps["lint"] = step("ps_lint.py", ["--dir", str(out_dir)])
    lint_env = steps["lint"]["env"]
    lint_ok = lint_env.get("success") is True
    summ = (lint_env.get("data") or {}) if lint_ok else ((lint_env.get("data") or {}).get("summary") or {})
    diff_txt = ""
    if a.config:
        steps["diff"] = step("ps_diff.py", ["--data", str(out_dir / "prob-data.json"), "--config", a.config, "--warn-only"] + (["--map", a.map] if a.map else []))
        d = (steps["diff"]["env"].get("data") or {})
        diff_txt = f"｜ps_diff 一致 {d.get('match')} / 不一致 {d.get('mismatch')}"
    deliver = f"ps_run {mode}｜{slug}｜ps_lint {'PASS' if lint_ok else 'FAIL'}｜{summ.get('pending_marks', '?')} 處待決議{diff_txt}"
    result = {"mode": mode, "slug": slug, "out": str(out_dir), "lint": summ, "steps": {k: v["env"].get("data", {}).get("delivery") or v["env"].get("error") for k, v in steps.items()}, "delivery": deliver}
    if not lint_ok:
        C.fail("GATE_BLOCKED", "ps_lint 未通過", deliver, result)
    if a.config and not a.diff_warn_only and (steps["diff"]["env"].get("data") or {}).get("mismatch"):
        C.fail("GATE_BLOCKED", "規格 ⇄ 設定檔不一致（見 config-diff.md）", deliver, result)
    # ── Excel View 軌（--excel 或 --xlsx-view）──
    kinds = None
    if a.excel is not None:
        kinds = a.excel or ["all"]
    elif a.xlsx_view:
        kinds = ["probtable"]
    if kinds:
        excel_made = {}
        diff_json = out_dir / "config-diff.json"
        for k in kinds:
            xa = ["--kind", k, "--out", a.out, "--slug", slug] + (["--game", a.game] if a.game else []) + (["--map", a.map] if a.map else [])
            if k in ("probtable", "all") and a.config:
                xa += ["--config", a.config]
            if k in ("diff", "review", "all") and diff_json.exists():
                xa += ["--diff", str(diff_json)]
            if k in ("lint", "review", "all"):
                xa += ["--lint", str(out_dir / "lint-report.json")]
            if k in ("qtreport", "review", "all") and a.report:
                xa += ["--report", a.report] + (["--golden", str(a.golden)] if a.golden else [])
            if k == "versions" and a.versions:
                xa += ["--versions"] + a.versions
            xr = step("ps_xlsx.py", xa)["env"]
            excel_made[k] = xr.get("data") or xr.get("error")
        result["excel"] = excel_made
    C.emit(result, {"stage": "ps_run"})


if __name__ == "__main__":
    main()
