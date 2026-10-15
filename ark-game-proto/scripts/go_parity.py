#!/usr/bin/env python3
"""go_parity — 雛型引擎 ⇄ Go 快測引擎 逐局對照（同 seed、同 RNG 流，逐局比 輪帶組 / MG / FG / 封頂後總贏分 / 組別）。

  python go_parity.py --engine data/slot/milefo/quicktest/engine --go-config data/slot/milefo/quicktest/config/a-standard.json \\
      --game-config output/slot-proto/milefo/game-config.json --seed 42 --n 200000 --out parity.seed42.json
  python go_parity.py ... --seed 777 --n 40000000 --fg-only      # 大量手數只輸出 FG 局（找封頂 / JACKPOT）

流程：把 goparity/<model>_trace.go 放進引擎的「暫存複本」cmd/slotproto-trace/（不動原引擎）→ go run 產 trace →
node tests/go_parity.js 以 GoRand（Go math/rand 逐位元移植）逐局重算比對 → parity JSON（可餵 proto_build --go-parity）。
需要：go 1.20+、node 18+。exit 0 = 0 差異；1 = 有差異；2 = 輸入錯；8 = 缺 go / node。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent


def out(ok: bool, data=None, err: str = "", hint: str = "", code: int = 0) -> None:
    print(json.dumps({"success": ok, "data": data} if ok else {"success": False, "error": {"message": err, "hint": hint}, "data": data}, ensure_ascii=False))
    sys.exit(code)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", required=True, help="Go 快測引擎目錄（含 go.mod）")
    ap.add_argument("--go-config", required=True, help="引擎讀的設定檔（milefo: config/*.json；tiger-dragon: odds/odds_*.json）")
    ap.add_argument("--game-config", required=True, help="proto_build 產的 game-config.json")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n", type=int, default=200000)
    ap.add_argument("--fg-only", action="store_true")
    ap.add_argument("--out", help="parity JSON 輸出路徑")
    a = ap.parse_args()
    for exe in ("go", "node"):
        if not shutil.which(exe):
            out(False, err=f"找不到 {exe}", hint="Windows：$env:PATH += ';C:\\Go\\bin'；node 18+", code=8)
    eng, gc = pathlib.Path(a.engine).resolve(), pathlib.Path(a.game_config).resolve()
    if not (eng / "go.mod").exists() or not gc.exists():
        out(False, err="--engine 需含 go.mod；--game-config 需存在", code=2)
    model = json.loads(gc.read_text(encoding="utf-8"))["fg"].get("model", "collect-mult")
    tpl = HERE / "goparity" / f"{model}_trace.go"
    if not tpl.exists():
        out(False, err=f"沒有 {tpl.name}", hint="新玩法模型需補一支 trace（見 references/go-parity.md）", code=2)
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td) / "engine"
        shutil.copytree(eng, work, ignore=shutil.ignore_patterns("*.exe", "*.txt", "__debug_bin*"))
        (work / "cmd" / "slotproto-trace").mkdir(parents=True, exist_ok=True)
        shutil.copy(tpl, work / "cmd" / "slotproto-trace" / "main.go")
        trace = pathlib.Path(td) / "trace.txt"
        args = ["go", "run", "./cmd/slotproto-trace", "--config", str(pathlib.Path(a.go_config).resolve()), "--seed", str(a.seed), "--n", str(a.n)]
        if a.fg_only:
            args.append("--fg-only")
        with trace.open("w", encoding="utf-8") as fh:
            p = subprocess.run(args, cwd=work, stdout=fh, stderr=subprocess.PIPE, text=True, env={**os.environ, "GOFLAGS": "-mod=mod"})
        if p.returncode:
            out(False, err="go run 失敗", hint=p.stderr[-600:], code=2)
        q = subprocess.run(["node", str(HERE / "tests" / "go_parity.js"), str(gc), str(trace)], capture_output=True, text=True)
    try:
        res = json.loads(q.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        out(False, err="go_parity.js 沒有輸出", hint=q.stderr[-600:], code=2)
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    res["delivery"] = f"go_parity {model}｜seed {res['seed']}｜{res['spins']:,} 手｜FG {res['fg']:,}｜封頂 {res['capped']}｜差異 {res['mismatch']}"
    out(res["mismatch"] == 0, res, err="逐局有差異（見 data.first）", code=0 if res["mismatch"] == 0 else 1)


if __name__ == "__main__":
    main()
