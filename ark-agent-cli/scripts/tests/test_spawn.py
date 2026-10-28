"""ark-agent-cli v2：fake backend 的 spawn 全鏈、nudge、blocked → resume、cancel、exec + attach、預算、one-shot、輸出清理。"""
import json
import os
import pathlib
import subprocess
import sys
import time

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import agent_common as C  # noqa: E402


@pytest.fixture(autouse=True)
def jobs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ARK_AGENT_JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("ARK_FAKE_SLEEP", "0.05")
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    return tmp_path / "jobs"


def sh(*args, expect=None):
    r = subprocess.run([sys.executable, str(SCRIPTS / "agent_spawn.py"), *map(str, args)], capture_output=True, text=True, encoding="utf-8", env=os.environ)
    j = json.loads(r.stdout.strip().splitlines()[-1])
    if expect is not None:
        assert r.returncode == expect, (r.returncode, j)
    return j


def task(tmp_path, fake: str) -> pathlib.Path:
    p = tmp_path / "task.md"; p.write_text(f"# 目標\n測試\n[[FAKE: {fake}]]\n", encoding="utf-8"); return p


def spawn(tmp_path, fake, **kw):
    args = ["spawn", "--name", "t", "--task", task(tmp_path, fake), "--backend", "fake", "--max-minutes", "5", "--max-segments", kw.get("max_segments", 10)]
    if kw.get("attach"):
        args += ["--attach-exec", kw["attach"]]
    return sh(*args, expect=0)["data"]["job_id"]


def wait(job, expect):
    return sh("wait", "--job", job, "--timeout", "30", "--poll", "0.3", expect=expect)


def test_three_segments_done(tmp_path, jobs_dir):
    job = spawn(tmp_path, "segments=3")
    d = wait(job, 0)["data"]
    assert d["state"] == "done" and d["segment"] == 3
    res = sh("result", "--job", job, expect=0)["data"]
    assert res["summary"] == "fake 任務完成摘要" and pathlib.Path(res["result_md"]).exists()
    prompts = sorted((jobs_dir / job / "segments").glob("*.prompt.md"))
    assert len(prompts) == 3 and "上一段 checkpoint" in prompts[1].read_text(encoding="utf-8") and "segment 1/3" in prompts[1].read_text(encoding="utf-8")
    assert "你是背景執行的 sub-agent" in prompts[0].read_text(encoding="utf-8")


def test_nudge_once_then_ok(tmp_path, jobs_dir):
    job = spawn(tmp_path, "segments=2 no_checkpoint")
    d = wait(job, 0)["data"]
    assert d["state"] == "done"
    ev = [json.loads(l) for l in (jobs_dir / job / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(e["kind"] == "nudge" for e in ev)


def test_blocked_then_resume(tmp_path, jobs_dir, monkeypatch):
    job = spawn(tmp_path, "blocked")
    j = wait(job, 3)
    assert j["success"] is False and j["data"]["state"] == "blocked" and "fake blocked reason" in j["error"]["message"]
    # 人處理完 → 改 task 行為（這裡用 env 覆蓋）→ resume
    monkeypatch.setenv("ARK_FAKE_SCRIPT", "segments=2")
    r = sh("resume", "--job", job, "--extra-segments", "2", expect=0)["data"]
    assert r["resumed_from_segment"] == 1
    d = wait(job, 0)["data"]
    assert d["state"] == "done" and d["resume_count"] == 1


def test_budget_max_segments(tmp_path):
    job = spawn(tmp_path, "segments=99", max_segments=2)
    j = wait(job, 7)
    assert j["data"]["state"] == "timeout" and j["data"]["segment"] == 2


def test_cancel(tmp_path, jobs_dir, monkeypatch):
    monkeypatch.setenv("ARK_FAKE_SLEEP", "0.6")
    job = spawn(tmp_path, "segments=50")
    time.sleep(0.8)
    sh("cancel", "--job", job, expect=0)
    j = wait(job, 6)
    assert j["data"]["state"] == "cancelled"


def test_exec_job_and_attach(tmp_path, jobs_dir):
    ej = sh("exec", "--name", "script", "--cmd", f"{sys.executable} -c \"print('hello'); import time; time.sleep(0.3)\"", "--max-minutes", "1", expect=0)["data"]["job_id"]
    job = spawn(tmp_path, "segments=1", attach=ej)
    wait(job, 0); d = wait(ej, 0)["data"]
    assert d["exit_code"] == 0 and "hello" in (jobs_dir / ej / "exec.log").read_text(encoding="utf-8")
    assert f"附掛的背景腳本 job" in (jobs_dir / job / "segments" / "001.prompt.md").read_text(encoding="utf-8")
    lst = sh("list", expect=0)["data"]["jobs"]
    assert {x["job_id"] for x in lst} >= {ej, job}


def test_exec_failure_exit_code(tmp_path):
    ej = sh("exec", "--name", "bad", "--cmd", f"{sys.executable} -c \"import sys; sys.exit(3)\"", expect=0)["data"]["job_id"]
    j = wait(ej, 6)
    assert j["data"]["state"] == "failed" and j["data"]["exit_code"] == 3


def test_crash_backend_fails_job(tmp_path):
    job = spawn(tmp_path, "crash")
    j = wait(job, 6)
    assert j["data"]["state"] == "failed"


def test_one_shot_cli_and_cleaning():
    r = subprocess.run([sys.executable, str(SCRIPTS / "agent_cli.py"), "-b", "fake", "checkpoint_path: /dev/null\nsegment: 2"], capture_output=True, text=True, encoding="utf-8", env=os.environ)
    j = json.loads(r.stdout)
    assert j["success"] and "\x1b" not in j["data"]["text"] and "▸ Time" not in j["data"]["text"] and j["data"]["text"].startswith("第 2 段完成")
    assert C.parse_model_spec("claude/haiku") == ("claude", "haiku")
    argv, stdin = C.build_argv("claude", "hi", model="haiku", json_output=True, lean=True)
    assert argv[-1] == "hi" and "--output-format" in argv and "--tools" in argv and stdin is None
    argv, stdin = C.build_argv("kiro", "hi", agent="admin", session="abc")
    assert "--agent" in argv and "--resume-id" in argv


def test_missing_driver_is_8(tmp_path, monkeypatch):
    monkeypatch.setenv("ARK_CLI_CLAUDE_CMD", "/nonexistent/claude")
    r = subprocess.run([sys.executable, str(SCRIPTS / "agent_cli.py"), "-b", "claude", "hi"], capture_output=True, text=True, encoding="utf-8", env=os.environ)
    assert r.returncode == 8 and json.loads(r.stdout)["error"]["code"] == "DRIVER_MISSING"
