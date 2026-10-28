#!/usr/bin/env python3
"""agent_worker — 背景 worker（由 agent_spawn 以 detached 進程啟動；也可手動 `--job <id>` 前景跑來除錯）。

agent 型 job：分段迴圈。每段 = 一次 CLI one-shot 呼叫（fresh context），prompt = 協定段 + task.md + 上一段 checkpoint；
sub-agent 必須在段尾寫 checkpoint.json（status: continue | done | blocked）。worker 負責：驗 checkpoint、nudge 一次、
預算（段數 / 分鐘 / 單段逾時）、心跳、cancel 旗標、done 時產 result.md。context 不會累積——狀態在 checkpoint 檔，不在對話裡。
exec 型 job：跑一條指令到結束，stdout / stderr 落檔，exit code 寫回 job.json。
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_cli as A  # noqa: E402
import agent_common as C  # noqa: E402

# Windows 預設 cp950/cp1252 stdout 會讓含非 ASCII 的輸出崩潰；worker 是 detached 進程，先固定 UTF-8
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

PROTOCOL_FILE = C.SKILL_ROOT / "references" / "subagent-protocol.md"
VALID = ("continue", "done", "blocked")


def job_dir(job_id: str) -> pathlib.Path:
    return C.JOBS_ROOT / job_id


def load_job(job_id: str) -> dict:
    j = C.read_json(job_dir(job_id) / "job.json")
    if not j:
        raise SystemExit(f"job 不存在: {job_id}")
    return j


def save_job(j: dict):
    j["updated_at"] = C.now()
    C.write_json(job_dir(j["job_id"]) / "job.json", j)


def event(j: dict, kind: str, **kw):
    C.append_jsonl(job_dir(j["job_id"]) / "events.jsonl", {"kind": kind, "segment": j.get("segment", 0), **kw})


def protocol_text() -> str:
    txt = PROTOCOL_FILE.read_text(encoding="utf-8") if PROTOCOL_FILE.exists() else ""
    m = re.search(r"<!-- protocol:start -->(.*?)<!-- protocol:end -->", txt, re.S)
    return (m.group(1) if m else txt).strip()


def render_prompt(j: dict, seg: int, last_cp: dict | None, nudge: bool) -> tuple[str, pathlib.Path]:
    d = job_dir(j["job_id"])
    cp_path = d / "segments" / f"{seg:03d}.checkpoint.json"
    task = pathlib.Path(j["task_file"]).read_text(encoding="utf-8")
    exec_block = ""
    if j.get("attached_exec"):
        ej = C.read_json(job_dir(j["attached_exec"]) / "job.json", {})
        exec_block = f"\n## 附掛的背景腳本 job\n- job_id: {j['attached_exec']}\n- state: {ej.get('state')}\n- log: {job_dir(j['attached_exec']) / 'exec.log'}\n- 它的產物目錄: {ej.get('cwd')}\n"
    remain_min = max(0, int(j["max_minutes"] - (time.time() - j["_started_ts"]) / 60))
    parts = [protocol_text(), "", "# 任務（task.md，由主 agent 指派，不可改寫目標）", "", task, exec_block,
             "", "# 本段執行資訊（worker 填）",
             f"- job_id: {j['job_id']}", f"- segment: {seg}（上限 {j['max_segments']}）",
             f"- 剩餘時間預算: {remain_min} 分鐘（整個 job 上限 {j['max_minutes']} 分鐘）",
             f"- 本段建議工作量: 約 {j['segment_minutes']} 分鐘，到了就收尾寫 checkpoint",
             f"- 工作目錄: {j.get('cwd') or os.getcwd()}", f"- 產物目錄（evidence 放這裡）: {d / 'artifacts'}",
             f"- checkpoint_path: {cp_path}", ""]
    if last_cp:
        parts += ["# 上一段 checkpoint（接著做，不要重做已完成的）", "", "```json", C.json.dumps(last_cp, ensure_ascii=False, indent=1), "```", ""]
    else:
        parts += ["# 上一段 checkpoint", "", "（這是第一段，從頭開始）", ""]
    if nudge:
        parts += ["# ⚠️ nudge", "", "你上一段結束時沒有寫 checkpoint 檔。這一段結束前務必把 JSON 寫到 checkpoint_path，否則整個 job 會中止。", ""]
    return "\n".join(parts), cp_path


def read_checkpoint(cp_path: pathlib.Path, text: str) -> dict | None:
    cp = C.read_json(cp_path)
    if not isinstance(cp, dict):
        j = C.extract_json(text)  # 退路：從 stdout 撈一個帶 status 的 JSON
        cp = j if isinstance(j, dict) and j.get("status") in VALID else None
        if cp:
            C.write_json(cp_path, cp)
    if not isinstance(cp, dict) or cp.get("status") not in VALID:
        return None
    return cp


def write_result(j: dict, cp: dict, state: str):
    d = job_dir(j["job_id"])
    cps = [C.read_json(p) for p in sorted((d / "segments").glob("*.checkpoint.json"))]
    ev = [e for c in cps if isinstance(c, dict) for e in (c.get("evidence") or [])]
    notes = [n for c in cps if isinstance(c, dict) for n in (c.get("notes") or [])]
    L = [f"# 結果 — {j['name']}（{j['job_id']}）", "",
         f"- state: **{state}** · segments: {j['segment']} · 耗時 {int((time.time() - j['_started_ts']) / 60)} 分鐘 · backend {j['backend']}",
         f"- 原因: {cp.get('reason') or '—'}" if state != "done" else "", "", "## 摘要", "", cp.get("summary") or cp.get("progress") or "（sub-agent 未提供摘要）", "",
         "## 逐段進度", ""] + [f"{i + 1}. [{c.get('status')}] {c.get('progress', '')}" for i, c in enumerate(cps) if isinstance(c, dict)] + \
        ["", "## 證據", ""] + ([f"- {e}" for e in ev] or ["- 無"]) + ["", "## 備註 / 異常", ""] + ([f"- {n}" for n in notes] or ["- 無"]) + \
        ["", f"## 產物目錄", "", f"`{d / 'artifacts'}`", ""]
    C.atomic_write(d / "result.md", "\n".join(x for x in L if x is not None))


def run_agent_job(j: dict):
    d = job_dir(j["job_id"])
    (d / "segments").mkdir(exist_ok=True); (d / "artifacts").mkdir(exist_ok=True)
    j.update(state="running", started_at=j.get("started_at") or C.now(), pid=os.getpid())
    j["_started_ts"] = j.get("_started_ts") or time.time()
    save_job(j); event(j, "start")
    last_cp = j.get("last_checkpoint")
    nudge = False
    while True:
        if (d / "cancel").exists():
            j["state"] = "cancelled"; save_job(j); event(j, "cancelled"); write_result(j, last_cp or {"reason": "cancelled"}, "cancelled"); return
        if j["segment"] >= j["max_segments"]:
            j["state"] = "timeout"; save_job(j); event(j, "budget", why="max_segments"); write_result(j, last_cp or {"reason": "段數用盡"}, "timeout"); return
        if (time.time() - j["_started_ts"]) / 60 >= j["max_minutes"]:
            j["state"] = "timeout"; save_job(j); event(j, "budget", why="max_minutes"); write_result(j, last_cp or {"reason": "時間用盡"}, "timeout"); return
        seg = j["segment"] + 1
        prompt, cp_path = render_prompt(j, seg, last_cp, nudge)
        C.atomic_write(d / "segments" / f"{seg:03d}.prompt.md", prompt)
        j["heartbeat_at"] = C.now(); save_job(j); event(j, "segment_start", seg=seg, nudge=nudge)
        r = A.call(j["backend"], prompt, j.get("model"), False, None, j.get("agent"), False, j.get("cwd"), j["segment_timeout_s"])
        C.atomic_write(d / "segments" / f"{seg:03d}.out.txt", (r.get("text") or "") + ("\n\n[stderr]\n" + r.get("raw_stderr", "") if r.get("raw_stderr") else ""))
        if r.get("driver_missing"):
            j["state"] = "failed"; j["error"] = r["raw_stderr"]; save_job(j); event(j, "failed", why="driver_missing"); write_result(j, {"reason": r["raw_stderr"]}, "failed"); return
        cp = read_checkpoint(cp_path, r.get("text") or "")
        if cp is None:
            if r.get("timed_out"):
                event(j, "segment_timeout", seg=seg)
            if not nudge:
                nudge = True; event(j, "nudge", seg=seg); continue  # 同一段重跑一次
            j["state"] = "failed"; j["error"] = "連續兩段未寫 checkpoint"; save_job(j); event(j, "failed", why="no_checkpoint")
            write_result(j, {"reason": j["error"]}, "failed"); return
        nudge = False
        j["segment"] = seg; j["last_checkpoint"] = cp; j["heartbeat_at"] = C.now()
        event(j, "checkpoint", seg=seg, status=cp["status"], progress=cp.get("progress", "")[:200], elapsed_ms=r.get("elapsed_ms"))
        if cp["status"] == "done":
            j["state"] = "done"; j["finished_at"] = C.now(); save_job(j); write_result(j, cp, "done"); event(j, "done"); _notify(j); return
        if cp["status"] == "blocked":
            j["state"] = "blocked"; j["finished_at"] = C.now(); save_job(j); write_result(j, cp, "blocked"); event(j, "blocked", reason=cp.get("reason")); _notify(j); return
        save_job(j)
        last_cp = cp
        time.sleep(float(j.get("segment_gap_s", 0)))


def run_exec_job(j: dict):
    d = job_dir(j["job_id"])
    j.update(state="running", started_at=C.now(), pid=os.getpid()); j["_started_ts"] = time.time(); save_job(j); event(j, "start")
    log = (d / "exec.log").open("a", encoding="utf-8")
    try:
        p = subprocess.Popen(j["command"], shell=True, cwd=j.get("cwd") or None, stdout=log, stderr=subprocess.STDOUT, text=True)
        j["child_pid"] = p.pid; save_job(j)
        t0 = time.time()
        while p.poll() is None:
            if (d / "cancel").exists():
                p.kill(); j["state"] = "cancelled"; save_job(j); event(j, "cancelled"); return
            if (time.time() - t0) / 60 > j["max_minutes"]:
                p.kill(); j["state"] = "timeout"; save_job(j); event(j, "budget", why="max_minutes"); return
            j["heartbeat_at"] = C.now(); save_job(j); time.sleep(2)
        j["exit_code"] = p.returncode; j["state"] = "done" if p.returncode == 0 else "failed"; j["finished_at"] = C.now(); save_job(j)
        event(j, j["state"], exit_code=p.returncode); _notify(j)
    finally:
        log.close()


def _notify(j: dict):
    cmd = j.get("notify_cmd")
    if not cmd:
        return
    try:
        subprocess.Popen(cmd.replace("{job_id}", j["job_id"]).replace("{state}", j["state"]).replace("{result}", str(job_dir(j["job_id"]) / "result.md")), shell=True)
        event(j, "notify", cmd=cmd)
    except Exception as e:  # noqa: BLE001
        event(j, "notify_failed", error=str(e))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--job", required=True); a = ap.parse_args()
    j = load_job(a.job)
    try:
        (run_exec_job if j.get("type") == "exec" else run_agent_job)(j)
    except Exception as e:  # noqa: BLE001
        # 以磁碟最新狀態為底，疊上記憶體中的 j（保留 exit_code 等終態欄位），再標 failed
        disk = load_job(a.job)
        disk.update({k: v for k, v in j.items() if not k.startswith("_")})
        disk["state"] = "failed"; disk["error"] = f"{type(e).__name__}: {e}"; save_job(disk); event(disk, "failed", why=disk["error"])
        raise


if __name__ == "__main__":
    main()
