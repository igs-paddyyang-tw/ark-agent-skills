#!/usr/bin/env python3
"""cpp_parity — C++ 快測（cpp_trace.py）與 Go 移植（portkit -trace）同 seed 逐局對照：總贏分、主遊戲贏分、SFMT／rand 累計次數四欄全等才算一致。
用法：python cpp_parity.py --cpp-src <C++ 專案> --engine <quicktest/engine> --config <cpp-original.json> --n 1000000 --seed 20261022 --out port/parity.json [--define K=V]
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, pathlib, subprocess, sys, tempfile

KIT = pathlib.Path(__file__).resolve().parent


def sha16(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cpp-src", required=True); ap.add_argument("--engine", required=True); ap.add_argument("--config", required=True)
    ap.add_argument("--n", type=int, default=1000000); ap.add_argument("--seed", type=int, default=20261022); ap.add_argument("--out", required=True)
    ap.add_argument("--define", action="append", default=[]); ap.add_argument("--patch", help="傳給 cpp_trace.py --patch")
    ap.add_argument("--cpp-label", help="parity.json 裡記的 C++ 路徑（預設 slot_math_squad/SLOT/…）")
    a = ap.parse_args()
    td = pathlib.Path(tempfile.mkdtemp(prefix="parity-"))
    ct, gt = td / "cpp.txt", td / "go.txt"
    r = subprocess.run([sys.executable, str(KIT / "cpp" / "cpp_trace.py"), "--src", a.cpp_src, "--n", str(a.n), "--seed", str(a.seed), "--out", str(ct)]
                       + [x for d in a.define for x in ("--define", d)] + (["--patch", a.patch] if a.patch else []), capture_output=True, text=True)
    cinfo = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"success": False, "error": r.stderr[-800:]}
    if not cinfo.get("success"):
        print(json.dumps({"success": False, "stage": "cpp", **cinfo}, ensure_ascii=False)); sys.exit(3)
    eng = pathlib.Path(a.engine).resolve()
    b = subprocess.run(["go", "build", "-o", str(td / "eng"), "."], cwd=eng, capture_output=True, text=True)
    if b.returncode:
        print(json.dumps({"success": False, "stage": "go-build", "error": b.stderr[-1500:]}, ensure_ascii=False)); sys.exit(3)
    g = subprocess.run([str(td / "eng"), "-config", str(pathlib.Path(a.config).resolve()), "-n", str(a.n), "-seed", str(a.seed), "-trace", str(gt), "-report", str(td / "r.txt")],
                       capture_output=True, text=True)
    if g.returncode:
        print(json.dumps({"success": False, "stage": "go-run", "error": g.stderr[-1500:]}, ensure_ascii=False)); sys.exit(3)
    mism, first = 0, None
    with ct.open() as f1, gt.open() as f2:
        for i, (x, y) in enumerate(zip(f1, f2)):
            if x != y:
                mism += 1
                if first is None:
                    first = {"hand": i + 1, "cpp": x.split(), "go": y.split()}
    n1 = sum(1 for _ in ct.open()); n2 = sum(1 for _ in gt.open())
    rep = {"schema": "port-parity/1", "date": dt.date.today().isoformat(), "hands": min(n1, n2), "hands_cpp": n1, "hands_go": n2, "seed": a.seed,
           "fields": ["hand", "total_win", "main_win", "sfmt_calls", "rand_calls"], "mismatch": mism + abs(n1 - n2), "first_mismatch": first,
           "cpp": {"src": a.cpp_label or ("slot_math_squad/SLOT/" + a.cpp_src.split("/cpp/", 1)[-1] if "/cpp/" in a.cpp_src else a.cpp_src), "defines": a.define, "sources": cinfo.get("sources"), "hook": cinfo.get("hand_patch"), "patch_env": {k: v for k, v in __import__("os").environ.items() if k.startswith("QT_")}},
           "go": {"engine": "quicktest/engine" if eng.name == "engine" else str(eng), "config": a.config, "config_sha16": sha16(pathlib.Path(a.config))},
           "trace_sha16": {"cpp": sha16(ct), "go": sha16(gt)}}
    pathlib.Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"success": rep["mismatch"] == 0, "hands": rep["hands"], "mismatch": rep["mismatch"], "first": first}, ensure_ascii=False))
    sys.exit(0 if rep["mismatch"] == 0 else 1)


if __name__ == "__main__":
    main()
