#!/usr/bin/env python3
"""agent_spawn — 把長時間任務丟給背景 sub-agent（像 subagent），主對話只負責啟動與收報告。

  spawn  --name aiqa-steward --task task.md [--backend kiro --model auto --agent aiqa --cwd DIR]
         [--max-minutes 90 --max-segments 12 --segment-minutes 8 --segment-timeout 900]
         [--attach-exec <job_id>] [--notify-cmd "python notify.py {job_id} {state}"]   → 立即回 job_id
  exec   --name aiqa-run --cmd "python aiqa_run.py ..." [--cwd DIR --max-minutes 120]   → 純腳本背景 job（零 LLM）
  status --job <id>          state / segment / 心跳 / 最後 checkpoint
  list   [--state running]   所有 job
  tail   --job <id> [-n 40]  最近事件 + 最後一段輸出
  wait   --job <id> --timeout 600 [--poll 5]   等到終態（exit 0 done / 3 blocked / 6 failed / 7 timeout）
  cancel --job <id>          放 cancel 旗標，worker 下一個檢查點停
  resume --job <id>          從最後 checkpoint 續跑（blocked / timeout / failed 的 job）
  result --job <id>          印 result.md 路徑與摘要（給主 agent 回報用）
所有輸出 envelope {success, contract:"1", data}；job 目錄 ARK_AGENT_JOBS_DIR（預設 ~/.ark/agent-jobs）。
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
import roster as R  # noqa: E402

TERMINAL = ("done", "blocked", "failed", "timeout", "cancelled")
STATE_EXIT = {"done": 0, "blocked": 3, "failed": 6, "timeout": 7, "cancelled": 6}


def jdir(job_id: str) -> pathlib.Path:
    return C.JOBS_ROOT / job_id


def load(job_id: str) -> dict:
    j = C.read_json(jdir(job_id) / "job.json")
    if not j:
        C.fail("BAD_INPUT", f"job 不存在: {job_id}", f"agent_spawn.py list（目錄 {C.JOBS_ROOT}）")
    return j


def detach(job_id: str) -> int:
    """啟動 worker 為獨立進程：POSIX 用 start_new_session；Windows 用 DETACHED_PROCESS。父進程結束不影響它。"""
    d = jdir(job_id)
    log = (d / "worker.log").open("a", encoding="utf-8")
    argv = [sys.executable, str(C.HERE / "agent_worker.py"), "--job", job_id]
    kw = {"stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen(argv, **kw)
    return p.pid


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        # 不用 tasklist：並發高負載下它慢又不可靠（會誤判 running 的 worker 已死）。
        # 改用 OpenProcess 查 exit code：拿不到 handle = 不存在；STILL_ACTIVE(259) = 活著。
        import ctypes
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return False
        try:
            code = wintypes.DWORD()
            if not k.GetExitCodeProcess(h, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:  # noqa: BLE001
        return False


def public(j: dict) -> dict:
    j = dict(j); j.pop("_started_ts", None)
    j["worker_alive"] = _alive(j.get("pid")) if j.get("state") == "running" else False
    j["dir"] = str(jdir(j["job_id"]))
    return j


# ---------------------------------------------------------------- commands
def cmd_spawn(a):
    task = pathlib.Path(a.task).resolve()
    if not task.exists():
        C.fail("BAD_INPUT", f"task 檔不存在: {task}", "寫一份 task.md（見 references/subagent-protocol.md 的 task 契約）")
    if a.backend not in C.BACKENDS:
        C.fail("BAD_INPUT", f"未知 backend {a.backend}", f"可用 {list(C.BACKENDS)}")
    # --route agent:<name>：讀 agents.yaml 驗證該 agent 可派工，自動填 --agent 與 --cwd（從 yaml 的 dir）。
    # 選角本身由 manager（LLM）在對話層決定；腳本只負責「驗名字 + 補 cwd」這段確定性工作。
    if a.route:
        if not a.route.startswith("agent:"):
            C.fail("BAD_INPUT", f"--route 格式應為 agent:<name>: {a.route}",
                   "先 `agent_spawn.py roster` 看可派工名單，再 --route agent:<name>")
        name = a.route.split(":", 1)[1].strip()
        try:
            v = R.resolve(name)
        except R.RosterError as e:
            C.fail("BAD_INPUT", str(e), "`agent_spawn.py roster` 看可派工名單")
        a.agent = a.agent or v["name"]
        if not a.cwd:
            a.cwd = v["cwd"]
    if a.attach_exec:
        load(a.attach_exec)
    job_id = C.new_job_id(a.name)
    d = jdir(job_id); (d / "segments").mkdir(parents=True); (d / "artifacts").mkdir()
    task_copy = d / "task.md"; task_copy.write_text(task.read_text(encoding="utf-8"), encoding="utf-8")
    j = {"job_id": job_id, "name": a.name, "type": "agent", "backend": a.backend, "model": a.model, "agent": a.agent, "cwd": str(pathlib.Path(a.cwd).resolve()) if a.cwd else None,
         "task_file": str(task_copy), "state": "queued", "created_at": C.now(), "segment": 0, "max_segments": a.max_segments, "max_minutes": a.max_minutes,
         "segment_minutes": a.segment_minutes, "segment_timeout_s": a.segment_timeout, "segment_gap_s": a.segment_gap,
         "attached_exec": a.attach_exec, "notify_cmd": a.notify_cmd, "notify_agent": a.notify_agent, "protocol": C.PROTOCOL_VERSION, "skill_version": C.SKILL_VERSION, "last_checkpoint": None}
    C.write_json(d / "job.json", j)
    pid = detach(job_id)
    C.emit({"job_id": job_id, "dir": str(d), "worker_pid": pid, "state": "queued",
            "next": [f"python agent_spawn.py status --job {job_id}", f"python agent_spawn.py wait --job {job_id} --timeout {a.max_minutes * 60}", f"python agent_spawn.py result --job {job_id}"]})


def cmd_exec(a):
    job_id = C.new_job_id(a.name)
    d = jdir(job_id); d.mkdir(parents=True)
    j = {"job_id": job_id, "name": a.name, "type": "exec", "command": a.cmd, "cwd": str(pathlib.Path(a.cwd).resolve()) if a.cwd else None, "state": "queued",
         "created_at": C.now(), "max_minutes": a.max_minutes, "notify_cmd": a.notify_cmd, "notify_agent": a.notify_agent, "skill_version": C.SKILL_VERSION}
    C.write_json(d / "job.json", j)
    pid = detach(job_id)
    C.emit({"job_id": job_id, "dir": str(d), "worker_pid": pid, "log": str(d / "exec.log"), "next": f"python agent_spawn.py wait --job {job_id}"})


def cmd_status(a):
    C.emit(public(load(a.job)))


def cmd_list(a):
    rows = []
    for p in sorted(C.JOBS_ROOT.glob("*/job.json"), reverse=True):
        j = C.read_json(p)
        if j and (not a.state or j.get("state") == a.state):
            rows.append({k: j.get(k) for k in ("job_id", "name", "type", "state", "segment", "created_at", "finished_at")})
    C.emit({"jobs": rows[: a.limit], "dir": str(C.JOBS_ROOT)})


def cmd_tail(a):
    j = load(a.job); d = jdir(a.job)
    ev = (d / "events.jsonl").read_text(encoding="utf-8").splitlines()[-a.n:] if (d / "events.jsonl").exists() else []
    outs = sorted((d / "segments").glob("*.out.txt")) if (d / "segments").exists() else []
    last_out = outs[-1].read_text(encoding="utf-8")[-2000:] if outs else ((d / "exec.log").read_text(encoding="utf-8")[-2000:] if (d / "exec.log").exists() else "")
    C.emit({"job_id": a.job, "state": j.get("state"), "segment": j.get("segment"), "events": [C.json.loads(e) for e in ev], "last_output": last_out})


def cmd_wait(a):
    t0 = time.time()
    while True:
        j = load(a.job)
        if j.get("state") in TERMINAL:
            code = STATE_EXIT[j["state"]]
            if code == 0:
                C.emit(public(j))
            C.fail({3: "GATE_BLOCKED", 6: "QUERY_FAILED", 7: "TIMEOUT"}[code], f"job {j['state']}: {j.get('error') or (j.get('last_checkpoint') or {}).get('reason', '')}", f"result --job {a.job}", data=public(j))
        if j.get("state") == "running" and not _alive(j.get("pid")) and (time.time() - t0) > 10:
            C.fail("QUERY_FAILED", "worker 進程已不存在但 job 仍 running（可能被殺）", f"resume --job {a.job}", data=public(j))
        if time.time() - t0 > a.timeout:
            C.fail("TIMEOUT", f"等待超過 {a.timeout}s，job 仍 {j.get('state')}", "之後再 status / wait；job 仍在背景跑", data=public(j))
        time.sleep(a.poll)


def cmd_cancel(a):
    j = load(a.job)
    if j.get("state") in TERMINAL:
        C.emit({"job_id": a.job, "state": j["state"], "note": "已是終態"})
    (jdir(a.job) / "cancel").write_text(C.now(), encoding="utf-8")
    C.emit({"job_id": a.job, "cancel_requested": True, "note": "worker 下一個檢查點停；exec 型立即 kill"})


def cmd_resume(a):
    j = load(a.job)
    if j.get("type") != "agent":
        C.fail("BAD_INPUT", "只有 agent 型 job 可 resume", "exec 型請重新 exec")
    if j.get("state") == "running" and _alive(j.get("pid")):
        C.fail("BAD_INPUT", "job 還在跑", "先 cancel 或等它結束")
    (jdir(a.job) / "cancel").unlink(missing_ok=True)
    if a.extra_minutes:
        j["max_minutes"] = j["max_minutes"] + a.extra_minutes
    if a.extra_segments:
        j["max_segments"] = j["max_segments"] + a.extra_segments
    j.update(state="queued", error=None, resumed_at=C.now(), resume_count=j.get("resume_count", 0) + 1)
    j.pop("_started_ts", None)
    C.write_json(jdir(a.job) / "job.json", j)
    pid = detach(a.job)
    C.emit({"job_id": a.job, "resumed_from_segment": j.get("segment"), "worker_pid": pid, "max_minutes": j["max_minutes"], "max_segments": j["max_segments"]})


def cmd_inbox(a):
    """讀 / 確認終態通知。主 agent 每輪開頭跑一次（零等待的「拉」）；--ack 把 pending 標為已讀。"""
    import agent_notify as N
    path = N.INBOX_ROOT / f"{a.agent}.jsonl"
    rows = [C.json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []
    pending = [r for r in rows if not r.get("ack")]
    out = rows if a.all else pending
    if a.ack and pending:
        for r in rows:
            r["ack"] = True
        C.atomic_write(path, "".join(C.json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    C.emit({"agent": a.agent, "pending": len(pending), "notices": out, "acked": bool(a.ack and pending), "inbox": str(path)})


def cmd_result(a):
    j = load(a.job); d = jdir(a.job)
    res = d / "result.md"
    cp = j.get("last_checkpoint") or {}
    C.emit({"job_id": a.job, "state": j.get("state"), "result_md": str(res) if res.exists() else None, "summary": cp.get("summary") or cp.get("progress"),
            "reason": cp.get("reason") or j.get("error"), "segments": j.get("segment"), "artifacts": str(d / "artifacts"),
            "evidence": cp.get("evidence", []), "exec_log": str(d / "exec.log") if (d / "exec.log").exists() else None, "exit_code": j.get("exit_code")})


def cmd_roster(a):
    """列可派工名單（給 manager 看著選角）。腳本只出名單，不挑人。"""
    try:
        data = R.list_candidates(role=a.role)
    except R.RosterError as e:
        C.fail("BAD_INPUT", str(e), "設 env ARK_AGENTS_YAML，或在 workspace 根放 agents.yaml")
    C.emit({**data,
            "note": "manager 看 workers 選一個最適合的 → spawn --route agent:<name>；選不出就把這份名單給使用者挑。"
                    "ops（admin）是維運，需明確指定才派。"})


def main():
    ap = argparse.ArgumentParser(description="背景 sub-agent job 控制")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("spawn"); s.add_argument("--name", required=True); s.add_argument("--task", required=True)
    s.add_argument("--backend", default=C.DEFAULT_BACKEND); s.add_argument("--model"); s.add_argument("--agent"); s.add_argument("--cwd")
    s.add_argument("--max-minutes", type=int, default=90); s.add_argument("--max-segments", type=int, default=12)
    s.add_argument("--segment-minutes", type=int, default=8); s.add_argument("--segment-timeout", type=int, default=900); s.add_argument("--segment-gap", type=float, default=0)
    s.add_argument("--attach-exec"); s.add_argument("--notify-cmd")
    s.add_argument("--notify-agent", help="終態寫進哪個 agent 的 inbox（預設同 --agent）；inbox 永遠會寫")
    s.add_argument("--route", help="agent:<name>：讀 agents.yaml 驗證並自動填 --agent/--cwd")
    s.set_defaults(func=cmd_spawn)
    s = sub.add_parser("roster"); s.add_argument("--role", help="只列此 role（如 worker）"); s.set_defaults(func=cmd_roster)
    s = sub.add_parser("exec"); s.add_argument("--name", required=True); s.add_argument("--cmd", required=True); s.add_argument("--cwd")
    s.add_argument("--max-minutes", type=int, default=120); s.add_argument("--notify-cmd"); s.add_argument("--notify-agent"); s.set_defaults(func=cmd_exec)
    s = sub.add_parser("inbox", help="讀 / 確認終態通知（主 agent 每輪開頭跑一次，零等待）"); s.add_argument("--agent", default="default")
    s.add_argument("--ack", action="store_true"); s.add_argument("--all", action="store_true"); s.set_defaults(func=cmd_inbox)
    s = sub.add_parser("status"); s.add_argument("--job", required=True); s.set_defaults(func=cmd_status)
    s = sub.add_parser("list"); s.add_argument("--state"); s.add_argument("--limit", type=int, default=30); s.set_defaults(func=cmd_list)
    s = sub.add_parser("tail"); s.add_argument("--job", required=True); s.add_argument("-n", type=int, default=40); s.set_defaults(func=cmd_tail)
    s = sub.add_parser("wait"); s.add_argument("--job", required=True); s.add_argument("--timeout", type=int, default=600); s.add_argument("--poll", type=float, default=5); s.set_defaults(func=cmd_wait)
    s = sub.add_parser("cancel"); s.add_argument("--job", required=True); s.set_defaults(func=cmd_cancel)
    s = sub.add_parser("resume"); s.add_argument("--job", required=True); s.add_argument("--extra-minutes", type=int, default=0); s.add_argument("--extra-segments", type=int, default=0); s.set_defaults(func=cmd_resume)
    s = sub.add_parser("result"); s.add_argument("--job", required=True); s.set_defaults(func=cmd_result)
    a = ap.parse_args(); a.func(a)


if __name__ == "__main__":
    main()
