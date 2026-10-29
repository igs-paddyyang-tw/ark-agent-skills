"""2.4.0 治理：stdin / prompt 檔、access 映射、handoff grace kill、空轉熔斷、用量、finalize 孤兒、gc、watchdog、exec 守門、task frontmatter access。"""
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


def task(tmp_path, fake, front=""):
    p = tmp_path / "task.md"; p.write_text(f"{front}# 目標\n測試\n[[FAKE: {fake}]]\n", encoding="utf-8"); return p


def spawn(tmp_path, fake, *extra, front=""):
    return sh("spawn", "--name", "g", "--task", task(tmp_path, fake, front), "--backend", "fake", "--max-minutes", "5", "--max-segments", "12", *extra, expect=0)["data"]["job_id"]


def wait(job, expect):
    return sh("wait", "--job", job, "--timeout", "40", "--poll", "0.3", expect=expect)


def test_prompt_never_in_argv_for_long_prompt(tmp_path):
    big = "x" * 60000
    for b in ("claude", "codex", "gemini"):
        argv, stdin, pf = C.build_argv(b, big)
        assert stdin == big and len(" ".join(argv)) < 2000
    argv, stdin, pf = C.build_argv("kiro", big, prompt_file=tmp_path / "p.md")
    assert stdin is None and pf.read_text(encoding="utf-8") == big and len(" ".join(argv)) < 2000 and str(pf) in argv[-1]
    assert C.build_argv("codex", "q")[0][-1] == "-"   # codex stdin marker


def test_access_mapping_snapshot():
    want = {("kiro", "read-only"): "--trust-tools=fs_read", ("kiro", "full"): "--trust-all-tools", ("claude", "read-only"): "Read,Grep,Glob,LS",
            ("claude", "full"): "--dangerously-skip-permissions", ("codex", "read-only"): "read-only", ("codex", "workspace"): "workspace-write",
            ("codex", "full"): "danger-full-access", ("gemini", "full"): "yolo"}
    for (b, acc), token in want.items():
        argv, _, pf = C.build_argv(b, "p", access=acc, prompt_file=None if b != "kiro" else pathlib.Path("/tmp/_k.md"))
        assert token in argv, (b, acc, argv)
    argv, _, _ = C.build_argv("claude", "p", access="workspace", allow_tools=["Read", "Bash"])
    assert "Read,Bash" in argv
    with pytest.raises(ValueError):
        C.build_argv("claude", "p", access="root")


def test_handoff_grace_kills_lingering_cli(tmp_path):
    t0 = time.time()
    job = spawn(tmp_path, "segments=1 linger=8", "--handoff-grace", "1")
    d = wait(job, 0)["data"]
    assert d["state"] == "done" and time.time() - t0 < 7
    ev = [json.loads(l) for l in (tmp_path / "jobs" / job / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(e["kind"] == "killed" and e.get("why") == "handoff_grace" for e in ev)


def test_idle_circuit_breaker(tmp_path):
    job = spawn(tmp_path, "segments=99 idle_from=3", "--idle-segments", "3")
    j = wait(job, 3)
    assert j["data"]["state"] == "blocked" and "空轉" in j["data"]["last_checkpoint"]["reason"] and j["data"]["segment"] == 6  # 段 3 的 progress 文字變化算進展；4,5,6 無進展


def test_metrics_change_is_progress(tmp_path):
    job = spawn(tmp_path, "segments=4", "--idle-segments", "2")   # 每段 actions=3 → 不熔斷
    assert wait(job, 0)["data"]["state"] == "done"


def test_usage_accumulates(tmp_path):
    job = spawn(tmp_path, "segments=3 usage")
    d = wait(job, 0)["data"]
    assert d["usage"]["input_tokens"] == 6000 and d["usage"]["output_tokens"] == 150 and d["usage"]["llm_calls"] == 3
    assert (tmp_path / "jobs" / job / "segments" / "002.usage.json").exists()
    assert sh("list", expect=0)["data"]["jobs"][0]["tokens"] == 6150


def test_finalize_orphan_and_auto(tmp_path, monkeypatch):
    monkeypatch.setenv("ARK_FAKE_SLEEP", "3")
    job = spawn(tmp_path, "segments=5")
    time.sleep(0.8)
    pid = sh("status", "--job", job, expect=0)["data"]["pid"]
    os.kill(pid, 9); time.sleep(0.5)
    d = sh("status", "--job", job, expect=0)["data"]           # 孤兒自動收尾
    assert d["state"] == "failed" and "worker_died" in d["error"]
    assert (tmp_path / "jobs" / job / "result.md").exists()
    assert sh("inbox", "--agent", "default", expect=0)["data"]["pending"] == 1
    assert sh("finalize", "--job", job, expect=2)["error"]["code"] == "BAD_INPUT"   # 已非孤兒


def test_gc(tmp_path):
    for fake in ("segments=1", "blocked"):
        job = spawn(tmp_path, fake); wait(job, 0 if fake == "segments=1" else 3)
    for p in (tmp_path / "jobs").glob("*/job.json"):
        os.utime(p, (time.time() - 10 * 86400,) * 2)
    r = sh("gc", "--days", "7", "--dry-run", expect=0)["data"]
    assert len(r["removed"]) == 1 and r["kept"] == 1                # blocked 預設保留
    sh("gc", "--days", "7", expect=0)
    assert len(list((tmp_path / "jobs").glob("*/job.json"))) == 1


def test_watchdog_blocks(tmp_path):
    flag = tmp_path / "wd"; flag.write_text("0")
    wd = f"{sys.executable} -c \"import sys,pathlib; p=pathlib.Path(r'{flag}'); n=int(p.read_text())+1; p.write_text(str(n)); sys.exit(0 if n<2 else 1)\""
    job = spawn(tmp_path, "segments=9", "--watchdog-cmd", wd, "--watchdog-fail", "2", "--max-minutes", "1")
    j = sh("wait", "--job", job, "--timeout", "90", "--poll", "0.5", expect=3)
    assert "watchdog" in j["data"]["last_checkpoint"]["reason"]


def test_exec_shell_gate():
    assert sh("exec", "--name", "x", "--cmd", "python a.py; rm -rf /", expect=2)["error"]["code"] == "BAD_INPUT"
    j = sh("exec", "--name", "x", "--cmd", f"{sys.executable} --version", expect=0)
    sh("wait", "--job", j["data"]["job_id"], "--timeout", "20", "--poll", "0.3", expect=0)


def test_task_frontmatter_access_stricter_wins(tmp_path):
    job = spawn(tmp_path, "segments=1", "--access", "full", front="---\naccess: read-only\n---\n")
    assert sh("status", "--job", job, expect=0)["data"]["access"] == "read-only"
    job2 = spawn(tmp_path, "segments=1", "--access", "read-only", front="---\naccess: full\n---\n")
    assert sh("status", "--job", job2, expect=0)["data"]["access"] == "read-only"
    wait(job, 0); wait(job2, 0)
