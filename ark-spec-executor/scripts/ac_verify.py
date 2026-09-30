#!/usr/bin/env python3
"""ac_verify.py — 對任務做 AC 驗收，留證據，不猜

Usage:
    python ac_verify.py <tasks.json> --workspace <ws> [--task 1.1 ...] [--out data/<name>-verify.json] [--timeout 300]

驗證方法解析優先序（references/verify-methods.md）：
    1. AC 文字的 verify: 提示  → file | import:<module> | pytest:<path> | cmd:<command> | manual
    2. 產出檔案在 tests/ 或名為 test_*.py → pytest <file>（並檢查 docstring 有 `AC: <AC-ID>`）
    3. AC 關鍵字：import/載入 → import 產出模組；檔案/存在/建立 → file_exists；測試/test/pass → pytest 產出檔
    4. 都不命中 → manual：狀態 pending，**不算通過**（fail-closed）

每筆結果：{task, method, status: pass|fail|pending, command, exit, evidence(stdout/err 尾 20 行), duration_ms}
exit：0 全部 pass；1 有 fail 或 pending
"""
import sys

if __name__ == "__main__" and ({"-h", "--help"} & set(sys.argv[1:]) or len(sys.argv) < 2):
    print(__doc__ or "")
    raise SystemExit(0)

import json
import re
import subprocess
import time
from pathlib import Path


def tail(s: str, n: int = 20) -> str:
    return "\n".join((s or "").strip().splitlines()[-n:])


def module_from_path(p: str) -> str:
    q = re.sub(r"\.py$", "", p).replace("\\", "/").strip("/")
    parts = q.split("/")
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def resolve(task: dict) -> tuple[str, str]:
    """回傳 (method, arg)"""
    h = task.get("verify_hint")
    if h:
        return h["method"], h.get("arg", "")
    out = task.get("output_file", "")
    if out.startswith("tests/") or Path(out).name.startswith("test_"):
        return "pytest", out
    ac = task.get("ac", "").lower()
    if "import" in ac or "載入" in ac:
        return "import", module_from_path(out)
    if any(k in ac for k in ("測試", "pytest", "test")) and out.endswith(".py"):
        return "pytest", out
    if any(k in task.get("ac", "") for k in ("檔案", "存在", "建立")) or ac.startswith("file"):
        return "file", out
    return "manual", ""


def run(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str, str]:
    import os
    env = {**os.environ, "PYTHONPATH": f"{cwd}{os.pathsep}{cwd / 'src'}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"}
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except FileNotFoundError as e:
        return 127, "", str(e)


def verify_task(task: dict, ws: Path, timeout: int) -> dict:
    method, arg = resolve(task)
    t0 = time.time()
    res = {"task": task["id"], "ac_id": task.get("ac_id"), "method": method, "command": "", "exit": None, "evidence": ""}
    if task.get("role") == "human":
        res.update(status="pending", evidence="human 任務：需人工確認"); return res
    if method == "file":
        p = ws / (arg or task["output_file"])
        ok = p.exists() and p.stat().st_size > 0
        res.update(status="pass" if ok else "fail", command=f"test -s {p.relative_to(ws) if p.is_relative_to(ws) else p}",
                   exit=0 if ok else 1, evidence="exists, non-empty" if ok else "missing or empty")
    elif method == "import":
        mod = arg or module_from_path(task["output_file"])
        code, out, err = run([sys.executable, "-c", f"import {mod}"], ws, timeout)
        res.update(status="pass" if code == 0 else "fail", command=f"python -c 'import {mod}'", exit=code, evidence=tail(err or out))
    elif method == "pytest":
        target = arg or task["output_file"]
        code, out, err = run([sys.executable, "-m", "pytest", target, "-q", "-p", "no:cacheprovider"], ws, timeout)
        ev = tail(out + err)
        if "No module named pytest" in err:
            ev = "環境缺 pytest（pip install pytest）——這是環境問題不是任務失敗，先 ark-env-doctor\n" + ev
        acid = task.get("ac_id")
        if acid and (ws / target).exists() and f"AC: {acid}" not in (ws / target).read_text(encoding="utf-8", errors="ignore"):
            ev = f"⚠️ 測試檔缺 docstring 標記 `AC: {acid}`（validator 追蹤鏈會斷）\n" + ev
        res.update(status="pass" if code == 0 else "fail", command=f"pytest {target} -q", exit=code, evidence=ev)
    elif method == "cmd":
        if not arg:
            res.update(status="pending", evidence="verify: cmd 缺指令"); return res
        code, out, err = run(["sh", "-c", arg], ws, timeout)
        res.update(status="pass" if code == 0 else "fail", command=arg, exit=code, evidence=tail(out + err))
    else:
        res.update(status="pending", evidence="無可自動驗證的方法；需人工確認（不算通過）")
    res["duration_ms"] = int((time.time() - t0) * 1000)
    return res


def main() -> int:
    argv = sys.argv[1:]
    tasks_json = Path(argv[0])
    ws = Path(argv[argv.index("--workspace") + 1]).resolve() if "--workspace" in argv else Path(".").resolve()
    timeout = int(argv[argv.index("--timeout") + 1]) if "--timeout" in argv else 300
    only = []
    if "--task" in argv:
        i = argv.index("--task") + 1
        while i < len(argv) and not argv[i].startswith("--"):
            only.append(argv[i]); i += 1
    data = json.loads(tasks_json.read_text(encoding="utf-8"))
    tasks = [t for t in data["tasks"] if not only or t["id"] in only]
    results = [verify_task(t, ws, timeout) for t in tasks]
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else tasks_json.with_name(tasks_json.name.replace("-tasks", "-verify"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    p = sum(r["status"] == "pass" for r in results); f = sum(r["status"] == "fail" for r in results); pe = len(results) - p - f
    for r in results:
        mark = {"pass": "✅", "fail": "❌", "pending": "⏸"}[r["status"]]
        print(f"{mark} {r['task']:5} {r['method']:7} {r['command'][:60]}")
    print(f"\npass {p} · fail {f} · pending {pe}  → {out}")
    return 0 if f == 0 and pe == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
