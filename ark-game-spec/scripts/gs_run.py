#!/usr/bin/env python3
"""gs_run — ark-game-spec 2.0 總編排（薄派發器）：一個入口、八個 stage，各 stage runner 原封保留在 scripts/<stage>/，flag 全部透傳。

  python scripts/gs_run.py --stage video   --source <url|mp4> [--domain auto|slot-game|…] [--out artifacts/cva] [vu_run 其他 flag]
  python scripts/gs_run.py --stage detect  --run <run>                      # auto 模式：ga_detect 判 domain 並續跑 vu_run 剩餘 stage
  python scripts/gs_run.py --stage analyze --run <run> [--force] [--no-report] [--report-html] [--wiki-schema …]
  python scripts/gs_run.py --stage draft|decide|dev --run <run> [--answer-key …] [--llm] [--allow-deferred]
  python scripts/gs_run.py --stage gdd     --pack <gdd-pack> [--out] [--style]            # lint → build（素材總覽.html + todo.md）
  python scripts/gs_run.py --stage gdd     --from xlsx --xlsx <規格書.xlsx> --out <pack>  # gdd_extract → lint → build
  python scripts/gs_run.py --stage gdd     --from spec --run <run> --out <pack>           # gdd_from_spec → lint → build
  …上面三種加 --export [--export-out <dir>] [--export-all-assets]                                 # 再產企劃樣板交付夾（與 kaiji-gdd-sample 同結構）
  python scripts/gs_run.py --stage atlas   --run <run> --slug <slug> | --gdd <pack> [--out data/atlas] [--library …]
  python scripts/gs_run.py --stage pack    [--domain <d> | --all]                          # pack_lint
  python scripts/gs_run.py --stage all     --source <url|mp4> [--domain …] [--decisions decisions.yaml] [--slug <slug>]
        all = video →（auto 時 detect）→ analyze → draft；有 --decisions 則續 decide → dev → atlas。中間人工決議是刻意的斷點（ark-grill-me）。

每個 stage 以 subprocess 執行 runner（F-6：stdout 一律 UTF-8）；失敗即停並回傳該 runner 的 envelope。
`--stage analyze` 另在 ga_run 之後呼叫 ga_report（D-3：ga_run 1.x 未呼叫 report 的補救放在派發器，不動 ga_run 本身），`--no-report` 可關。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from _lib import run_common as C  # noqa: E402

STAGES = {
    "video": HERE / "video" / "vu_run.py",
    "detect": HERE / "analysis" / "ga_detect.py",
    "analyze": HERE / "analysis" / "ga_run.py",
    "report": HERE / "analysis" / "ga_report.py",
    "draft": HERE / "spec" / "gs_run.py",
    "decide": HERE / "spec" / "gs_run.py",
    "dev": HERE / "spec" / "gs_run.py",
    "gdd": HERE / "gdd" / "gdd_run.py",
    "atlas": HERE / "atlas" / "atlas_run.py",
    "pack": HERE / "pack" / "pack_lint.py",
}


def step(script: pathlib.Path, args: list[str], *, tolerate_rc: tuple[int, ...] = ()) -> dict:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    p = subprocess.run([sys.executable, "-X", "utf8", str(script), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    lines = (p.stdout or "").strip().splitlines()
    line = next((ln for ln in reversed(lines) if ln.startswith("{")), "")
    try:
        envl = json.loads(line) if line else {}
    except json.JSONDecodeError:
        envl = {}
    if p.returncode != 0 and p.returncode not in tolerate_rc:
        err = envl.get("error") or {}
        C.fail(err.get("code", "QUERY_FAILED"), f"{script.parent.name}/{script.name} 失敗（rc={p.returncode}）：{err.get('message', '')}",
               err.get("hint") or (p.stderr or "")[-600:], {"stage": script.stem, "envelope": envl})
    return {"rc": p.returncode, "env": envl, "data": envl.get("data") or {}}


def main() -> None:
    ap = argparse.ArgumentParser(description="ark-game-spec 2.x 總編排（薄派發器）", allow_abbrev=False)  # 透傳旗標不可被前綴吃掉（如 pack 的 --all）
    ap.add_argument("--stage", required=True, choices=list(STAGES) + ["all"])
    ap.add_argument("--run")
    ap.add_argument("--source")
    ap.add_argument("--domain")
    ap.add_argument("--out")
    ap.add_argument("--pack")
    ap.add_argument("--gdd")
    ap.add_argument("--export", action="store_true", help="gdd：build 後產企劃樣板交付夾（<short_title>_素材總覽.html + symbols/ illustrations/ spec-reference-images/）")
    ap.add_argument("--export-out", help="gdd：交付夾位置（預設 <pack>/export）")
    ap.add_argument("--export-all-assets", action="store_true", help="gdd：交付夾連同來源三夾未引用的圖一起帶")
    ap.add_argument("--xlsx")
    ap.add_argument("--from", dest="src", help="gdd：xlsx|spec（預設讀既有 pack）；atlas：v1|draft")
    ap.add_argument("--slug")
    ap.add_argument("--decisions", help="all：有則續跑 decide → dev → atlas")
    ap.add_argument("--no-report", action="store_true")
    ap.add_argument("--report-html", action="store_true")
    a, rest = ap.parse_known_args()
    results: dict[str, dict] = {}

    def opt(*pairs):
        out = []
        for flag, val in pairs:
            if val not in (None, False):
                out += [flag] if val is True else [flag, str(val)]
        return out

    st = a.stage
    if st == "video":
        r = step(STAGES["video"], opt(("--source", a.source), ("--run", a.run), ("--domain", a.domain), ("--out", a.out)) + rest)
        results["video"] = r["data"]
        run = r["data"].get("run")
        if r["data"].get("domain") is None and run:  # auto 模式：判 domain 後續跑
            d = step(STAGES["detect"], ["--run", run] + rest)
            results["detect"] = d["data"]
            dom = d["data"].get("domain")
            if dom and dom != "unknown":
                results["video_full"] = step(STAGES["video"], ["--run", run, "--domain", dom])["data"]
        C.emit({**results, "run": run, "next": f"python scripts/gs_run.py --stage analyze --run {run}"}, {"stage": "video"})
    if st == "detect":
        r = step(STAGES["detect"], opt(("--run", a.run)) + rest)
        dom = r["data"].get("domain")
        results["detect"] = r["data"]
        if dom and dom != "unknown":
            results["video_full"] = step(STAGES["video"], ["--run", a.run, "--domain", dom])["data"]
        C.emit(results, {"stage": "detect"})
    if st == "analyze":
        r = step(STAGES["analyze"], opt(("--run", a.run)) + [x for x in rest if x not in ("--report-html",)])
        results["analyze"] = r["data"]
        if not a.no_report:
            results["report"] = step(STAGES["report"], ["--run", a.run] + (["--html"] if a.report_html else []))["data"]
        C.emit({**results, "next": f"python scripts/gs_run.py --stage draft --run {a.run}"}, {"stage": "analyze"})
    if st in ("draft", "decide", "dev"):
        r = step(STAGES[st], ["--run", a.run, "--stage", st] + rest)
        C.emit(r["data"], {"stage": st})
    if st == "report":
        C.emit(step(STAGES["report"], opt(("--run", a.run), ("--out", a.out)) + rest)["data"], {"stage": "report"})
    if st == "gdd":
        pack = a.pack
        if a.src == "xlsx":
            if not a.xlsx or not a.out:
                C.fail("BAD_INPUT", "--from xlsx 需要 --xlsx 與 --out")
            results["extract"] = step(HERE / "gdd" / "gdd_extract.py", ["--xlsx", a.xlsx, "--out", a.out] + rest)["data"]
            pack = a.out
        elif a.src == "spec":
            if not a.run or not a.out:
                C.fail("BAD_INPUT", "--from spec 需要 --run 與 --out")
            results["from_spec"] = step(HERE / "gdd" / "gdd_from_spec.py", ["--run", a.run, "--out", a.out] + opt(("--slug", a.slug)) + rest)["data"]
            pack = a.out
        if not pack:
            C.fail("BAD_INPUT", "需要 --pack，或 --from xlsx/--from spec 加 --out")
        exp = (["--export"] if a.export else []) + (["--export-out", a.export_out] if a.export_out else []) \
            + (["--all-assets"] if a.export_all_assets else [])
        results["gdd"] = step(STAGES["gdd"], ["--pack", pack] + exp + rest)["data"]
        C.emit(results, {"stage": "gdd"})
    if st == "atlas":
        args = opt(("--run", a.run), ("--gdd", a.gdd), ("--slug", a.slug), ("--out", a.out), ("--from", a.src)) + rest
        C.emit(step(STAGES["atlas"], args)["data"], {"stage": "atlas"})
    if st == "pack":
        C.emit(step(STAGES["pack"], opt(("--domain", a.domain)) + rest)["data"], {"stage": "pack"})
    if st == "all":
        if not a.source:
            C.fail("BAD_INPUT", "--stage all 需要 --source")
        v = step(STAGES["video"], opt(("--source", a.source), ("--domain", a.domain), ("--out", a.out)))
        run = v["data"].get("run"); results["video"] = v["data"]
        if v["data"].get("domain") is None:
            d = step(STAGES["detect"], ["--run", run]); results["detect"] = d["data"]
            dom = d["data"].get("domain")
            if not dom or dom == "unknown":
                C.fail("GATE_BLOCKED", "ga_detect 判不出 domain", f"python scripts/gs_run.py --stage video --run {run} --domain <d>", results)
            step(STAGES["video"], ["--run", run, "--domain", dom])
        results["analyze"] = step(STAGES["analyze"], ["--run", run])["data"]
        if not a.no_report:
            results["report"] = step(STAGES["report"], ["--run", run] + (["--html"] if a.report_html else []))["data"]
        results["draft"] = step(STAGES["draft"], ["--run", run, "--stage", "draft"], tolerate_rc=(3,))["data"]
        if not a.decisions:
            C.emit({**results, "run": run, "next": f"人員以 ark-grill-me 決議 → {run}/decisions.yaml → python scripts/gs_run.py --stage all … --decisions（或 --stage decide --run {run}）"}, {"stage": "all", "stopped_at": "draft"})
        import shutil
        shutil.copy2(a.decisions, pathlib.Path(run) / "decisions.yaml")
        results["decide"] = step(STAGES["decide"], ["--run", run, "--stage", "decide"])["data"]
        results["dev"] = step(STAGES["dev"], ["--run", run, "--stage", "dev"])["data"]
        slug = a.slug or pathlib.Path(run).name
        results["atlas"] = step(STAGES["atlas"], ["--run", run, "--slug", slug])["data"]
        C.emit({**results, "run": run}, {"stage": "all"})


if __name__ == "__main__":
    main()
