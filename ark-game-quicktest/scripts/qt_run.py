#!/usr/bin/env python3
"""qt_run — 把快測範本實例化到 <dir>/engine/、套 odds.json、patch 常數、go run、再交 qt_report。

流程：qt_lint（有 null 不跑）→ 複製範本（--template，預設 data/dev-sample/機率工作流/快測範本）→
     patch main.go（GameName / OddsVersion / TotalRound / TuningMode）與 game/game_process.go（ReelAmount / ReelLength / SymbolWild / SymbolScatter）→
     複製 odds/odds_<ver>.json → `go run .`（go 不在 PATH 時用 --go 或 $GO_BIN）→ report_<ver>.txt → qt_report。
🔴 game_process.go 的玩法邏輯不會自動改：範本是 3×3 線型遊戲；新機制（收集 / hold&spin / 分流）由 prob-architect / 工程師改，
   本工具只保證 config 與報告兩頭對得回規格。

用法: python qt_run.py --dir data/quicktest/<slug> [--version 1.0.0] [--rounds 10000000] [--template <範本目錄>] [--go <go 可執行檔>]
                       [--targets quicktest.yaml] [--config-spec …] [--no-run]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qt_common as C  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE.parents[3] / "data" / "dev-sample" / "機率工作流" / "快測範本"


def step(script: str, *args) -> dict:
    r = subprocess.run([sys.executable, str(HERE / script), *args], capture_output=True, text=True, encoding="utf-8")
    try:
        j = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        C.fail("QUERY_FAILED", f"{script} 無 JSON 輸出: {r.stderr[-400:]}")
    if not j.get("success"):
        print(json.dumps(j, ensure_ascii=False))
        sys.exit(r.returncode or 1)
    return j


def patch(text: str, pairs: list[tuple[str, str]]) -> tuple[str, list[str]]:
    done = []
    for pat, rep in pairs:
        new, n = re.subn(pat, rep, text, count=1, flags=re.M)
        if n:
            text = new
            done.append(rep)
    return text, done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--version", default="1.0.0")
    ap.add_argument("--rounds", type=int, default=10_000_000)
    ap.add_argument("--template")
    ap.add_argument("--go", default=os.environ.get("GO_BIN", "go"))
    ap.add_argument("--targets")
    ap.add_argument("--config-spec")
    ap.add_argument("--no-run", action="store_true", help="只實例化與 patch，不執行 go")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--probspec", action="store_true", help="跑完 qt_report 後順手產 data/prob/<slug>/prob-spec.md（qt_probspec + ps_lint）")
    ap.add_argument("--prob-out", default="data/prob")
    a = ap.parse_args()
    d = pathlib.Path(a.dir).resolve()
    lint = step("qt_lint.py", "--dir", str(d), "--version", a.version)["data"]
    tpl = pathlib.Path(a.template) if a.template else DEFAULT_TEMPLATE
    if not (tpl / "main.go").exists():
        C.fail("BAD_INPUT", f"範本不存在：{tpl}", "用 --template 指到快測範本目錄")
    eng = d / "engine"
    if not (eng / "main.go").exists():
        shutil.copytree(tpl, eng, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".vscode", "*.exe", "report_*.txt", "*Data_*.csv"))
    qc = C.yaml_load(d / "qt-config.yaml") if (d / "qt-config.yaml").exists() else {}
    st = qc.get("structure") or {}
    main_go = eng / "main.go"
    txt, done = patch(main_go.read_text(encoding="utf-8"), [
        (r'GameName\s*=\s*".*?"', f'GameName = "{qc.get("game", d.name)}"'),
        (r'OddsVersion\s*=\s*".*?"', f'OddsVersion = "{a.version}"'),
        (r"TotalRound\s*=\s*\d+", f"TotalRound = {a.rounds}"),
    ])
    main_go.write_text(txt, encoding="utf-8")
    gp = eng / "game" / "game_process.go"
    gdone: list[str] = []
    if gp.exists():
        pairs = []
        if st.get("reels"):
            pairs += [(r"ReelAmount\s*=\s*\d+", f"ReelAmount = {st['reels']}"), (r"FreeReelAmount\s*=\s*\d+", f"FreeReelAmount = {st['reels']}")]
        if st.get("rows"):
            pairs += [(r"ReelLength\s*=\s*\d+", f"ReelLength = {st['rows']}"), (r"FreeReelLength\s*=\s*\d+", f"FreeReelLength = {st['rows']}")]
        if st.get("wild_id") is not None:
            pairs.append((r"SymbolWild\s*=\s*\d+", f"SymbolWild = {st['wild_id']}"))
        if st.get("scatter_id") is not None:
            pairs.append((r"SymbolScatter\s*=\s*\d+", f"SymbolScatter = {st['scatter_id']}"))
        t2, gdone = patch(gp.read_text(encoding="utf-8"), pairs)
        gp.write_text(t2, encoding="utf-8")
    shutil.copy2(d / "odds" / f"odds_{a.version}.json", eng / "odds" / f"odds_{a.version}.json")
    result = {"engine": str(eng), "patched_main": done, "patched_game": gdone, "lint": lint["status"], "rounds": a.rounds,
              "warning": "game_process.go 玩法邏輯未自動改（範本為 3×3 線型）；新機制需人工改程式" if (st.get("reels") or 3) != 3 or (st.get("rows") or 3) != 3 else None}
    if a.no_run:
        C.emit(result, {"stage": "qt_run", "ran": False})
        return
    go = shutil.which(a.go) or a.go
    if not pathlib.Path(go).exists() and shutil.which(a.go) is None:
        C.fail("MISSING_DEP", f"找不到 go（{a.go}）", "daemon 主機：export PATH=$HOME/.local/go/bin:$PATH；或 --go <路徑>；或改在有 Go 的機器跑 engine/", result)
    r = subprocess.run([go, "run", "."], cwd=str(eng), capture_output=True, text=True, encoding="utf-8", timeout=a.timeout,
                       env={**os.environ, "GOFLAGS": "-mod=mod", "GOPROXY": os.environ.get("GOPROXY", "off")})
    tail = (r.stdout + r.stderr)[-800:]
    rep = eng / f"report_{a.version}.txt"
    if r.returncode != 0 or not rep.exists():
        C.fail("QUERY_FAILED", "go run 失敗或未產 report", tail, result)
    result["report"] = str(rep)
    result["go_tail"] = tail.strip().splitlines()[-3:]
    rargs = ["--report", str(rep), "--out", str(d / "qt-report")] + (["--targets", a.targets] if a.targets else []) + (["--config-spec", a.config_spec] if a.config_spec else [])
    result["qt_report"] = step("qt_report.py", *rargs)["data"]
    if a.probspec:
        ps = step("qt_probspec.py", "--qt", a.dir, "--out", a.prob_out)["data"]
        ps["xlsx"] = step("qt_probtable.py", "--dir", str(pathlib.Path(ps["md"]).parent))["data"]["xlsx"]
        ps["lint"] = step("ps_lint.py", "--dir", str(pathlib.Path(ps["md"]).parent))["data"]["status"]
        result["prob_spec"] = ps
    C.emit(result, {"stage": "qt_run", "ran": True})


if __name__ == "__main__":
    main()
