#!/usr/bin/env python3
"""run_plan.py — 依 tasks.json 的 DAG 執行任務：runner 實作 → ac_verify 驗收 → checkpoint

Usage:
    python run_plan.py <plan.md> --workspace <ws> [--runner dry|cmd|kiro|claude] [--exec "<cmd template>"]
                       [--milestone N] [--no-resume] [--max-retries 2] [--task-timeout 900] [--plan-timeout 3600]
                       [--strict-scope] [--verify-timeout 300]

runner：
    dry     不執行，只產每個任務的 prompt 到 data/tasks/<id>.prompt.md 並跑驗收（用來檢查 plan 可執行性）
    cmd     以 --exec 模板執行，佔位：{prompt_file} {cwd} {output_file} {task_id} {role}
    kiro    references/runners.yaml 的 kiro 模板（預設 kiro-cli chat）
    claude  references/runners.yaml 的 claude 模板（預設 claude -p）

穩定性設計：
    - 執行前 plan_parse 契約檢查，P0 即拒跑（fail-closed）
    - checkpoint data/<name>-progress.json 每完成一個任務即落盤；重跑預設 resume 跳過已 pass
    - 依賴任務 fail/blocked → 本任務 skipped（不執行、不重試）
    - role=human → blocked，列入報告等人工；不阻塞非依賴任務
    - 失敗重試 ≤ max-retries，每次把上輪驗收證據注入 prompt（LLM 看得到錯在哪）
    - 寫入範圍守衛：git repo 下比對變更檔 vs 任務 output_file，越界 → 警告；--strict-scope 則判 fail 並 git checkout 還原
    - 單任務 / 全 plan timeout；到時標 fail / 中止並保留 checkpoint

exit：0 全部 pass；1 有 fail/blocked/pending；2 契約違反或環境錯；3 plan timeout 中止
"""
import sys

if __name__ == "__main__" and ({"-h", "--help"} & set(sys.argv[1:]) or len(sys.argv) < 2):
    print(__doc__ or "")
    raise SystemExit(0)

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plan_parse import load_plan  # noqa: E402
from ac_verify import verify_task  # noqa: E402

PROMPT_TPL = HERE.parent / "references" / "task-prompt.md"
RUNNERS = HERE.parent / "references" / "runners.yaml"
DEFAULT_RUNNERS = {
    "kiro": 'kiro-cli chat --no-interactive --trust-all-tools "$(cat {prompt_file})"',
    "claude": 'claude -p --dangerously-skip-permissions "$(cat {prompt_file})"',
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def opt(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def load_runner_cmd(runner: str) -> str:
    if RUNNERS.exists():
        for line in RUNNERS.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{runner}:"):
                return line.split(":", 1)[1].strip().strip('"')
    return DEFAULT_RUNNERS.get(runner, "")


def build_prompt(task: dict, plan: dict, ws: Path, attempt: int, prev: dict | None) -> str:
    tpl = PROMPT_TPL.read_text(encoding="utf-8") if PROMPT_TPL.exists() else "{task_name}\n產出：{output_file}\nAC：{ac}\n{retry_context}"
    fm = plan.get("frontmatter", {})
    soul = ws / "agents" / f"{task['role']}-agent" / ".kiro" / "steering" / "SOUL.md"
    retry = ""
    if prev:
        retry = f"\n## 上輪驗收失敗（第 {attempt} 次重試）\n方法：{prev.get('method')}　指令：{prev.get('command')}\n證據：\n```\n{prev.get('evidence','')}\n```\n請針對上述失敗修正，不要重寫無關部分。\n"
    return (tpl.replace("{task_id}", task["id"]).replace("{task_name}", task["name"]).replace("{role}", task["role"])
            .replace("{output_file}", task["output_file"]).replace("{ac_id}", task.get("ac_id") or "—").replace("{ac}", task["ac"])
            .replace("{related_spec}", fm.get("related_spec", "")).replace("{related_design}", fm.get("related_design", ""))
            .replace("{plan_path}", plan["plan"]).replace("{soul_path}", str(soul) if soul.exists() else "（無 SOUL，使用預設人格）")
            .replace("{retry_context}", retry))


def changed_files(ws: Path) -> set[str] | None:
    if not (ws / ".git").exists():
        return None
    r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ws, capture_output=True, text=True)
    return {line[3:].strip() for line in r.stdout.splitlines() if line.strip()}


def scope_violations(before: set[str] | None, after: set[str] | None, allowed: str) -> list[str]:
    if before is None or after is None:
        return []
    new = after - before
    noise = ("__pycache__", ".pyc", ".pytest_cache", "data/")
    return sorted(f for f in new if not (f == allowed or f.startswith(allowed.rstrip("/") + "/")) and not any(n in f for n in noise))


def execute(task: dict, plan: dict, ws: Path, runner: str, exec_tpl: str, timeout: int, attempt: int, prev: dict | None) -> dict:
    pdir = ws / "data" / "tasks"; pdir.mkdir(parents=True, exist_ok=True)
    pfile = pdir / f"{task['id']}.attempt{attempt}.prompt.md"
    pfile.write_text(build_prompt(task, plan, ws, attempt, prev), encoding="utf-8")
    if runner == "dry":
        return {"exit": 0, "log": "(dry) prompt 已產出，未執行", "prompt_file": str(pfile)}
    tpl = exec_tpl if runner == "cmd" else load_runner_cmd(runner)
    if not tpl:
        return {"exit": 2, "log": f"runner '{runner}' 無指令模板（--exec 或 references/runners.yaml）", "prompt_file": str(pfile)}
    cmd = (tpl.replace("{prompt_file}", str(pfile)).replace("{cwd}", str(ws)).replace("{output_file}", task["output_file"])
              .replace("{task_id}", task["id"]).replace("{role}", task["role"]))
    try:
        r = subprocess.run(cmd, shell=True, cwd=ws, capture_output=True, text=True, timeout=timeout)
        log = (r.stdout + r.stderr)[-4000:]
        (pdir / f"{task['id']}.attempt{attempt}.log").write_text(log, encoding="utf-8")
        return {"exit": r.returncode, "log": log[-800:], "prompt_file": str(pfile), "command": cmd}
    except subprocess.TimeoutExpired:
        return {"exit": 124, "log": f"runner timeout {timeout}s", "prompt_file": str(pfile), "command": cmd}


def main() -> int:
    argv = sys.argv[1:]
    plan_path = Path(argv[0]).resolve()
    ws = Path(opt(argv, "--workspace", ".")).resolve()
    runner = opt(argv, "--runner", "dry")
    exec_tpl = opt(argv, "--exec", "")
    ms = opt(argv, "--milestone")
    resume = "--no-resume" not in argv
    max_retries = int(opt(argv, "--max-retries", 2))
    task_timeout = int(opt(argv, "--task-timeout", 900))
    plan_timeout = int(opt(argv, "--plan-timeout", 3600))
    verify_timeout = int(opt(argv, "--verify-timeout", 300))
    strict = "--strict-scope" in argv

    plan = load_plan(plan_path)
    if plan["errors"]:
        print("❌ plan 契約違反，拒跑（先 plan_lint.py）：")
        for e in plan["errors"]: print("   - " + e)
        return 2
    tasks = {t["id"]: t for t in plan["tasks"]}
    order = plan["order"]
    if ms:
        order = [i for i in order if tasks[i]["milestone"] == int(ms)]

    ckpt_p = ws / "data" / f"{plan_path.stem}-progress.json"
    ckpt = json.loads(ckpt_p.read_text(encoding="utf-8")) if resume and ckpt_p.exists() else {"plan": str(plan_path), "runner": runner, "started": now(), "tasks": {}}
    ckpt["runner"] = runner
    def save():
        ckpt["updated"] = now()
        ckpt_p.parent.mkdir(parents=True, exist_ok=True)
        tmp = ckpt_p.with_suffix(".tmp"); tmp.write_text(json.dumps(ckpt, ensure_ascii=False, indent=1), encoding="utf-8"); os.replace(tmp, ckpt_p)

    t_plan0 = time.time()
    print(f"▶ {plan_path.name}  runner={runner}  tasks={len(order)}  resume={'on' if resume else 'off'}")
    for tid in order:
        t = tasks[tid]
        rec = ckpt["tasks"].get(tid, {})
        if rec.get("status") == "pass":
            print(f"↷ {tid} 已通過（checkpoint）"); continue
        if time.time() - t_plan0 > plan_timeout:
            print(f"⏱ plan timeout {plan_timeout}s，中止；checkpoint 已保留"); save(); return 3
        bad = [d for d in t["deps"] if ckpt["tasks"].get(d, {}).get("status") in ("fail", "blocked", "skipped")]
        if bad:
            ckpt["tasks"][tid] = {"status": "skipped", "reason": f"依賴未完成：{bad}", "updated": now()}; save()
            print(f"⤼ {tid} skipped（依賴 {bad}）"); continue
        if t["role"] == "human":
            ckpt["tasks"][tid] = {"status": "blocked", "reason": "human 任務，等人工確認：" + t["ac"], "updated": now()}; save()
            print(f"⏸ {tid} blocked（human）"); continue

        prev = None
        for attempt in range(0, max_retries + 1):
            before = changed_files(ws)
            t0 = time.time()
            ex = execute(t, plan, ws, runner, exec_tpl, task_timeout, attempt, prev)
            v = verify_task(t, ws, verify_timeout)
            viol = scope_violations(before, changed_files(ws), t["output_file"])
            if viol:
                msg = f"越界寫入：{viol}"
                if strict:
                    subprocess.run(["git", "checkout", "--", *viol], cwd=ws, capture_output=True)
                    v = {**v, "status": "fail", "evidence": msg + "（--strict-scope 已還原）"}
                else:
                    print(f"   ⚠️ {tid} {msg}")
            status = v["status"] if ex["exit"] in (0, None) or runner == "dry" else "fail"
            rec = {"status": status, "attempts": attempt + 1, "runner_exit": ex["exit"], "verify": v, "prompt_file": ex.get("prompt_file"),
                   "duration_ms": int((time.time() - t0) * 1000), "scope_violations": viol, "updated": now()}
            ckpt["tasks"][tid] = rec; save()
            mark = {"pass": "✅", "fail": "❌", "pending": "⏸"}[status]
            print(f"{mark} {tid} {t['name'][:36]:<36} {v['method']:<7} attempt={attempt+1} {rec['duration_ms']}ms")
            if status in ("pass", "pending"):
                break
            prev = {**v, "runner_log": ex.get("log", "")}
    save()
    st = [r["status"] for r in ckpt["tasks"].values()]
    p = st.count("pass")
    print(f"\n完成：pass {p} / fail {st.count('fail')} / blocked {st.count('blocked')} / skipped {st.count('skipped')} / pending {st.count('pending')}  → {ckpt_p}")
    print("下一步：python scripts/report_gen.py " + str(plan_path) + f" --workspace {ws}")
    return 0 if p == len(order) else 1


if __name__ == "__main__":
    raise SystemExit(main())
