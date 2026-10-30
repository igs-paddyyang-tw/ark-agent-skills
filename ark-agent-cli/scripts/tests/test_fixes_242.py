"""2.4.2 修正（bot 接背景 job 實測，交接單 kiro-cli docs/plans/ark-agent-cli-2.4.1-fixes-plan.md U-1～U-5）。"""
import json
import os
import pathlib
import re
import subprocess
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import agent_cli as A  # noqa: E402
import agent_common as C  # noqa: E402
import agent_worker as W  # noqa: E402


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARK_AGENT_JOBS_DIR", str(tmp_path / "jobs")); monkeypatch.setenv("ARK_AGENT_INBOX_DIR", str(tmp_path / "inbox"))
    monkeypatch.setenv("ARK_FAKE_SLEEP", "0.05"); monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    return tmp_path


def sh(*args, expect=None):
    r = subprocess.run([sys.executable, str(SCRIPTS / "agent_spawn.py"), *map(str, args)], capture_output=True, text=True, encoding="utf-8", env=os.environ)
    j = json.loads(r.stdout.strip().splitlines()[-1])
    if expect is not None:
        assert r.returncode == expect, (r.returncode, j, r.stderr[-300:])
    return j


def spawn(tmp_path, fake, *extra):
    p = tmp_path / f"task-{abs(hash(fake))}.md"; p.write_text(f"# 目標\n測試\n[[FAKE: {fake}]]\n", encoding="utf-8")
    return sh("spawn", "--name", "g", "--task", p, "--backend", "fake", "--max-minutes", "5", "--max-segments", "6", *extra, expect=0)["data"]["job_id"]


def wait(job, expect):
    return sh("wait", "--job", job, "--timeout", "40", "--poll", "0.3", expect=expect)


# ── U-1：actions／evidence_new 是清單也不崩 ─────────────────────────

def test_u1_list_actions_do_not_crash_and_count_as_progress(tmp_path):
    """實測 job 20261030-094021-bot-coder-2d31ac：sub-agent 寫清單 → int(list) 崩 → failed。"""
    job = spawn(tmp_path, "segments=2 list_actions")
    assert wait(job, 0)["data"]["state"] == "done"


@pytest.mark.parametrize("v,n", [(3, 3), ("2", 2), (["a", "b"], 2), ({"x": 1}, 1), (None, 0), ("很多", 0), (True, 1)])
def test_u1_count_is_tolerant(v, n):
    assert W._count(v) == n


# ── U-2：worker 例外路徑也要 result.md＋inbox＋notify_cmd ──────────────

def test_u2_worker_exception_finalizes_with_result_inbox_and_notify(tmp_path):
    """task 檔被刪 → worker 讀不到拋 FileNotFoundError：仍須補 result.md、寫 inbox、跑 notify_cmd。"""
    done = spawn(tmp_path, "segments=1"); wait(done, 0)
    jobs = tmp_path / "jobs"
    jid = done + "-crash"
    (jobs / jid).mkdir()
    j = json.loads((jobs / done / "job.json").read_text(encoding="utf-8"))
    marker = tmp_path / "notified.txt"
    j.update(job_id=jid, state="queued", segment=0, last_checkpoint=None, task_file=str(tmp_path / "已被刪掉的task.md"),
             notify_cmd=f'"{sys.executable}" -c "open(r\'{marker}\',\'w\').write(\'x\')"')
    for k in ("finished_at", "started_at", "pid", "error"):
        j.pop(k, None)
    (jobs / jid / "job.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "agent_worker.py"), "--job", jid],
                       capture_output=True, text=True, encoding="utf-8", env=os.environ)
    assert r.returncode != 0 and "FileNotFoundError" in r.stderr
    after = json.loads((jobs / jid / "job.json").read_text(encoding="utf-8"))
    assert after["state"] == "failed" and "FileNotFoundError" in after["error"]
    assert (jobs / jid / "result.md").exists(), "例外路徑沒補 result.md"
    kinds = [json.loads(line)["kind"] for line in (jobs / jid / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {"finalized", "inbox", "notify"} <= set(kinds), kinds
    assert marker.exists(), "notify_cmd 沒執行"


# ── U-3：claude 背景 job 要 json，usage 才抽得到 ───────────────────────

def test_u3_worker_requests_json_for_claude_and_accumulates_usage(tmp_path, monkeypatch):
    """實測 job 20261030-094229-bot-coder-3f2b3b：llm_calls 1、tokens 0 —— worker 沒要 json。"""
    monkeypatch.setattr(C, "JOBS_ROOT", tmp_path / "jobs")
    seen = {}

    def fake_call_watch(backend, prompt, cp_path, **kw):
        seen.update(kw)
        out = json.dumps({"result": json.dumps({"status": "done", "progress": "ok", "summary": "s", "actions": 1}),
                          "usage": {"input_tokens": 1200, "output_tokens": 80}, "total_cost_usd": 0.0123})
        return A._finish(backend, out, "", 0, 0, kw.get("json_output"), None)

    monkeypatch.setattr(A, "call_watch", fake_call_watch)
    monkeypatch.setattr(W, "_notify", lambda j: None)
    task = tmp_path / "t.md"; task.write_text("# 目標\nx\n", encoding="utf-8")
    jid = "j-u3"; (tmp_path / "jobs" / jid).mkdir(parents=True)
    j = {"job_id": jid, "name": "u3", "backend": "claude", "task_file": str(task), "segment": 0, "max_segments": 3, "max_minutes": 5,
         "segment_minutes": 1, "segment_timeout_s": 30, "access": "read-only"}
    W.save_job(j)
    W.run_agent_job(j)
    assert seen.get("json_output") is True
    assert j["state"] == "done" and j["usage"]["input_tokens"] == 1200 and j["usage"]["cost_usd"] == 0.0123


def test_u3_kiro_stays_text():
    """kiro 沒有 json 輸出模式（BACKENDS json 為空）—— 維持文字。"""
    assert "kiro" not in W.JSON_USAGE_BACKENDS


# ── U-4：版號常數＝SKILL.md ───────────────────────────────────────────

def test_u4_skill_version_matches_skill_md():
    m = re.search(r'^  version: "([^"]+)"', (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8"), re.M)
    assert C.SKILL_VERSION == m.group(1), f"agent_common.SKILL_VERSION={C.SKILL_VERSION} ≠ SKILL.md {m.group(1)}"


# ── U-5：read-only 寫不了檔 → 協定明寫印 JSON，且 worker 收得到 ───────────

def test_u5_protocol_tells_subagent_to_print_json_when_cannot_write():
    """實測 job 20261030-102154-bot-qa-671b72：協定沒說可印 JSON → sub-agent 用文字請人代存 → no_checkpoint。"""
    p = W.protocol_text()
    assert "寫不了檔" in p and "JSON 物件**印在回覆最後" in p
    assert "都是**整數**" in p                                       # U-1 的協定說明


def test_u5_stdout_only_checkpoint_completes_job(tmp_path):
    job = spawn(tmp_path, "segments=2 stdout_only", "--access", "read-only")
    assert wait(job, 0)["data"]["state"] == "done"
    assert (tmp_path / "jobs" / job / "segments" / "001.checkpoint.json").exists(), "worker 應代存從輸出撈到的 checkpoint"
