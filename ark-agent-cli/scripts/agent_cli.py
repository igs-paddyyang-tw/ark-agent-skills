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
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_common as C  # noqa: E402


def _finish(backend, cp_stdout, cp_stderr, returncode, t0, json_output, model, timed_out=False):
    text = C.clean_output(cp_stdout)
    data = C.extract_json(text) if json_output else None
    if json_output and isinstance(data, dict) and "result" in data and backend == "claude":  # claude --output-format json 包一層
        usage = C.extract_usage(text, data)
        text = str(data.get("result", text)); data = C.extract_json(text) or data
    else:
        usage = C.extract_usage(text, data)
    return {"success": bool(text) and not timed_out, "timed_out": timed_out, "text": text, "json_data": data, "backend": backend, "model": model,
            "elapsed_ms": int((time.time() - t0) * 1000), "exit_code": returncode, "raw_stderr": (cp_stderr or "")[-2000:], "usage": usage}


def call(backend: str, prompt: str, model: str | None = None, json_output=False, session=None, agent=None, lean=False,
         cwd: str | None = None, timeout: int = C.DEFAULT_TIMEOUT, env_extra: dict | None = None, access: str = "full",
         allow_tools=None, prompt_file=None, force_argv=False) -> dict:
    """one-shot。預設 access=full（互動式問一句）；sub-agent 由 worker 傳 read-only。"""
    argv, stdin_text, pf = C.build_argv(backend, prompt, model, json_output, session, agent, lean, access, allow_tools, prompt_file, force_argv)
    t0 = time.time()
    try:
        cp = subprocess.run(argv, input=stdin_text, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=timeout, cwd=cwd, env={**os.environ, **(env_extra or {})})
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode(errors="replace")) if e.stdout else ""
        return _finish(backend, partial, "", None, t0, json_output, model, timed_out=True)
    except FileNotFoundError:
        return {"success": False, "timed_out": False, "text": "", "json_data": None, "backend": backend, "model": model, "elapsed_ms": 0,
                "exit_code": None, "raw_stderr": f"CLI not found: {argv[0]}", "driver_missing": True, "usage": None}
    return _finish(backend, cp.stdout, cp.stderr, cp.returncode, t0, json_output, model)


def call_watch(backend: str, prompt: str, watch_file, grace_s: float = 60, poll_s: float = 2, **kw) -> dict:
    """kill policy：Popen 後輪詢 watch_file（checkpoint）；檔案出現後 CLI 仍未退出 → grace 後 kill 並視為成功；逾時 → kill 視為白做。"""
    timeout = kw.pop("timeout", C.DEFAULT_TIMEOUT); cwd = kw.pop("cwd", None); env_extra = kw.pop("env_extra", None)
    model = kw.get("model"); json_output = kw.get("json_output", False)
    argv, stdin_text, pf = C.build_argv(backend, prompt, model, json_output, kw.get("session"), kw.get("agent"), kw.get("lean", False),
                                        kw.get("access", "read-only"), kw.get("allow_tools"), kw.get("prompt_file"), kw.get("force_argv", False))
    t0 = time.time(); watch_file = pathlib.Path(watch_file) if watch_file else None
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding="utf-8", errors="replace", cwd=cwd, env={**os.environ, **(env_extra or {})})
    except FileNotFoundError:
        return {"success": False, "timed_out": False, "text": "", "json_data": None, "backend": backend, "model": model, "elapsed_ms": 0,
                "exit_code": None, "raw_stderr": f"CLI not found: {argv[0]}", "driver_missing": True, "usage": None}
    out_buf, err_buf = [], []
    import threading
    def pump(stream, buf):
        for line in stream:
            buf.append(line)
    th = [threading.Thread(target=pump, args=(p.stdout, out_buf), daemon=True), threading.Thread(target=pump, args=(p.stderr, err_buf), daemon=True)]
    for t in th:
        t.start()
    if stdin_text is not None:
        try:
            p.stdin.write(stdin_text); p.stdin.close()
        except Exception:  # noqa: BLE001
            pass
    seen_at = None; killed_reason = None
    while p.poll() is None:
        now = time.time()
        if watch_file is not None and seen_at is None and watch_file.exists():
            seen_at = now
        if seen_at is not None and now - seen_at > grace_s:
            killed_reason = "handoff_grace"; p.kill(); break
        if now - t0 > timeout:
            killed_reason = "timeout"; p.kill(); break
        time.sleep(poll_s)
    for t in th:
        t.join(timeout=5)
    r = _finish(backend, "".join(out_buf), "".join(err_buf), p.returncode, t0, json_output, model, timed_out=(killed_reason == "timeout"))
    r["killed"] = killed_reason
    if killed_reason == "handoff_grace":
        r["success"] = True
    return r


def main():
    ap = argparse.ArgumentParser(description="統一 agent CLI 呼叫")
    ap.add_argument("prompt", nargs="?")
    ap.add_argument("-b", "--backend", default=None); ap.add_argument("-m", "--model")
    ap.add_argument("--json", action="store_true"); ap.add_argument("--lean", action="store_true")
    ap.add_argument("--session"); ap.add_argument("--agent"); ap.add_argument("--cwd")
    ap.add_argument("--timeout", type=int, default=C.DEFAULT_TIMEOUT)
    ap.add_argument("--access", default="full", choices=list(C.ACCESS_LEVELS), help="one-shot 預設 full；sub-agent 預設 read-only")
    ap.add_argument("--allow-tools", help="逗號分隔，kiro/claude 覆蓋 access 的工具清單")
    ap.add_argument("--argv", action="store_true", help="強制 prompt 走 argv（只給極短 prompt / 除錯）")
    a = ap.parse_args()
    prompt = a.prompt if a.prompt is not None else sys.stdin.read()
    if not prompt.strip():
        C.fail("BAD_INPUT", "prompt 為空", "給參數或 stdin")
    backend, model = (C.parse_model_spec(a.model) if (a.model and "/" in a.model) else (a.backend or C.DEFAULT_BACKEND, a.model))
    if backend not in C.BACKENDS:
        C.fail("BAD_INPUT", f"未知 backend {backend}", f"可用 {list(C.BACKENDS)}")
    r = call(backend, prompt, model, a.json, a.session, a.agent, a.lean, a.cwd, a.timeout, access=a.access,
             allow_tools=a.allow_tools.split(",") if a.allow_tools else None, force_argv=a.argv)
    if r.get("driver_missing"):
        C.fail("DRIVER_MISSING", r["raw_stderr"], f"安裝 {backend} CLI 或設 {C.BACKENDS[backend]['env'][0]}")
    if r["timed_out"]:
        C.fail("TIMEOUT", f"{backend} 超過 {a.timeout}s", "加大 --timeout 或改用 agent_spawn 背景跑", data=r)
    if not r["success"]:
        C.fail("QUERY_FAILED", "CLI 無輸出", r["raw_stderr"][-300:], data=r)
    C.emit(r, {"backend": backend})


if __name__ == "__main__":
    main()
