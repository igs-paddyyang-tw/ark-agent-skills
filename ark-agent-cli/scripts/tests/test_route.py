"""ark-agent-cli 選角路由：roster 列名單 / 分區 / resolve 驗證 / spawn --route 補 cwd。
用暫存 agents.yaml 隔離，不依賴 workspace 根的真檔；派工走 fake backend，不接真 CLI。"""
import json
import os
import pathlib
import subprocess
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import roster as R  # noqa: E402

SAMPLE_YAML = """\
default:
  dir: "."
  name: "Ark Agent"
  codename: "娜娜"
  dispatchable: false
manager:
  dir: "."
  codename: "娜娜"
  dispatchable: false
  role: manager
admin:
  dir: "agents/admin-agent"
  codename: "管家"
  desc: "系統管理、監控"
  dispatchable: true
  role: admin
leader:
  dir: "agents/leader-agent"
  codename: "隊長"
  desc: "任務規劃、協調派工"
  dispatchable: true
  role: leader
coder:
  dir: "agents/coder-agent"
  codename: "碼哥"
  desc: "寫程式的，前後端 API 都行"
  dispatchable: true
  role: worker
qa:
  dir: "agents/qa-agent"
  codename: "品管"
  desc: "測試把關、Code Review"
  dispatchable: true
  role: worker
offline:
  dir: "agents/offline-agent"
  codename: "停用"
  desc: "暫停"
  dispatchable: false
  role: worker
"""


@pytest.fixture
def yaml_file(tmp_path, monkeypatch):
    p = tmp_path / "agents.yaml"
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    monkeypatch.setenv("ARK_AGENTS_YAML", str(p))
    # 建出各 agent 目錄，讓 cwd 解析有實體（非必要，但貼近真實）
    for d in ("admin-agent", "leader-agent", "coder-agent", "qa-agent"):
        (tmp_path / "agents" / d).mkdir(parents=True, exist_ok=True)
    return tmp_path


# ---------------------------------------------------------------- roster 純函式


def test_list_candidates_partitions(yaml_file):
    r = R.list_candidates()
    wnames = {w["name"] for w in r["workers"]}
    onames = {o["name"] for o in r["ops"]}
    # leader + worker 進 workers；admin 進 ops；manager/default/不可派工 不出現
    assert wnames == {"leader", "coder", "qa"}
    assert onames == {"admin"}
    assert "manager" not in wnames and "default" not in wnames
    assert "offline" not in wnames  # dispatchable=false 不列


def test_list_candidates_role_filter(yaml_file):
    r = R.list_candidates(role="worker")
    assert {w["name"] for w in r["workers"]} == {"coder", "qa"}  # leader 被濾掉
    assert {o["name"] for o in r["ops"]} == {"admin"}  # ops 不受 role 過濾影響


def test_resolve_worker_fills_cwd(yaml_file):
    v = R.resolve("coder")
    assert v["name"] == "coder" and v["role"] == "worker"
    assert v["cwd"].replace("\\", "/").endswith("agents/coder-agent")


def test_resolve_admin_allowed_when_explicit(yaml_file):
    v = R.resolve("admin")  # allow_admin 預設 True（明確指定才會走到）
    assert v["name"] == "admin"
    with pytest.raises(R.RosterError):
        R.resolve("admin", allow_admin=False)


def test_resolve_rejects_manager_and_unknown_and_offline(yaml_file):
    with pytest.raises(R.RosterError):
        R.resolve("manager")   # 互動入口不可派
    with pytest.raises(R.RosterError):
        R.resolve("nobody")    # 不存在
    with pytest.raises(R.RosterError):
        R.resolve("offline")   # dispatchable=false


# ---------------------------------------------------------------- spawn --route 整合（fake backend）


def sp(*args, env, expect=None):
    r = subprocess.run([sys.executable, str(SCRIPTS / "agent_spawn.py"), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    j = json.loads(r.stdout.strip().splitlines()[-1])
    if expect is not None:
        assert r.returncode == expect, (r.returncode, j)
    return r.returncode, j


def test_spawn_route_fills_agent_and_cwd(yaml_file, monkeypatch):
    env = dict(os.environ)
    env["ARK_AGENTS_YAML"] = str(yaml_file / "agents.yaml")
    env["ARK_AGENT_JOBS_DIR"] = str(yaml_file / "jobs")
    task = yaml_file / "task.md"
    task.write_text("# 目標\n測試\n[[FAKE: segments=1]]\n", encoding="utf-8")
    _, j = sp("spawn", "--name", "t", "--task", str(task), "--backend", "fake",
              "--route", "agent:coder", env=env, expect=0)
    jid = j["data"]["job_id"]
    jj = json.loads((yaml_file / "jobs" / jid / "job.json").read_text(encoding="utf-8"))
    assert jj["agent"] == "coder"
    assert jj["cwd"].replace("\\", "/").endswith("agents/coder-agent")


def test_spawn_route_bad_name_fails(yaml_file):
    env = dict(os.environ)
    env["ARK_AGENTS_YAML"] = str(yaml_file / "agents.yaml")
    env["ARK_AGENT_JOBS_DIR"] = str(yaml_file / "jobs")
    task = yaml_file / "task.md"
    task.write_text("# 目標\n測試\n", encoding="utf-8")
    _, j = sp("spawn", "--name", "t", "--task", str(task), "--backend", "fake",
              "--route", "agent:nobody", env=env, expect=2)  # BAD_INPUT
    assert j["success"] is False and j["error"]["code"] == "BAD_INPUT"


def test_spawn_route_bad_format_fails(yaml_file):
    env = dict(os.environ)
    env["ARK_AGENTS_YAML"] = str(yaml_file / "agents.yaml")
    env["ARK_AGENT_JOBS_DIR"] = str(yaml_file / "jobs")
    task = yaml_file / "task.md"
    task.write_text("# 目標\n測試\n", encoding="utf-8")
    _, j = sp("spawn", "--name", "t", "--task", str(task), "--backend", "fake",
              "--route", "coder", env=env, expect=2)  # 缺 agent: 前綴
    assert j["success"] is False
