#!/usr/bin/env python3
"""agent_cli — 統一 one-shot 呼叫（kiro / claude / gemini / codex / fake）。自足版，不依賴 bot 套件。

  python agent_cli.py -b claude -m haiku "分析需求"
  echo "分析這段 log" | python agent_cli.py -b kiro
  python agent_cli.py -b claude --json --lean "分類意圖"
  python agent_cli.py -b kiro --agent admin --session <id> --cwd agents/admin "..."
stdout：envelope {success, data{text, json_data, backend, model, elapsed_ms, timed_out, exit_code}}；
CLI exit code 不可靠（有 stdout 就算成功）；超時 → TIMEOUT（exit 7）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_common as C  # noqa: E402


def call(backend: str, prompt: str, model: str | None = None, json_output=False, session=None, agent=None, lean=False,
         cwd: str | None = None, timeout: int = C.DEFAULT_TIMEOUT, env_extra: dict | None = None) -> dict:
    argv, stdin_text = C.build_argv(backend, prompt, model, json_output, session, agent, lean)
    t0 = time.time()
    try:
        cp = subprocess.run(argv, input=stdin_text, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=timeout, cwd=cwd, env={**os.environ, **(env_extra or {})})
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode(errors="replace")) if e.stdout else ""
        return {"success": False, "timed_out": True, "text": C.clean_output(partial), "json_data": None, "backend": backend, "model": model,
                "elapsed_ms": int((time.time() - t0) * 1000), "exit_code": None, "raw_stderr": ""}
    except FileNotFoundError:
        return {"success": False, "timed_out": False, "text": "", "json_data": None, "backend": backend, "model": model, "elapsed_ms": 0,
                "exit_code": None, "raw_stderr": f"CLI not found: {argv[0]}", "driver_missing": True}
    text = C.clean_output(cp.stdout)
    data = C.extract_json(text) if json_output or backend in ("claude", "gemini") and json_output else None
    if json_output and isinstance(data, dict) and "result" in data and backend == "claude":  # claude --output-format json 包一層
        text = str(data.get("result", text)); data = C.extract_json(text)
    return {"success": bool(text), "timed_out": False, "text": text, "json_data": data, "backend": backend, "model": model,
            "elapsed_ms": int((time.time() - t0) * 1000), "exit_code": cp.returncode, "raw_stderr": (cp.stderr or "")[-2000:]}


def main():
    ap = argparse.ArgumentParser(description="統一 agent CLI 呼叫")
    ap.add_argument("prompt", nargs="?")
    ap.add_argument("-b", "--backend", default=None); ap.add_argument("-m", "--model")
    ap.add_argument("--json", action="store_true"); ap.add_argument("--lean", action="store_true")
    ap.add_argument("--session"); ap.add_argument("--agent"); ap.add_argument("--cwd")
    ap.add_argument("--timeout", type=int, default=C.DEFAULT_TIMEOUT)
    a = ap.parse_args()
    prompt = a.prompt if a.prompt is not None else sys.stdin.read()
    if not prompt.strip():
        C.fail("BAD_INPUT", "prompt 為空", "給參數或 stdin")
    backend, model = (C.parse_model_spec(a.model) if (a.model and "/" in a.model) else (a.backend or C.DEFAULT_BACKEND, a.model))
    if backend not in C.BACKENDS:
        C.fail("BAD_INPUT", f"未知 backend {backend}", f"可用 {list(C.BACKENDS)}")
    r = call(backend, prompt, model, a.json, a.session, a.agent, a.lean, a.cwd, a.timeout)
    if r.get("driver_missing"):
        C.fail("DRIVER_MISSING", r["raw_stderr"], f"安裝 {backend} CLI 或設 {C.BACKENDS[backend]['env'][0]}")
    if r["timed_out"]:
        C.fail("TIMEOUT", f"{backend} 超過 {a.timeout}s", "加大 --timeout 或改用 agent_spawn 背景跑", data=r)
    if not r["success"]:
        C.fail("QUERY_FAILED", "CLI 無輸出", r["raw_stderr"][-300:], data=r)
    C.emit(r, {"backend": backend})


if __name__ == "__main__":
    main()
