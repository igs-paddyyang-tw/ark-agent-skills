"""sched_gate.py：有變化才叫 LLM —— 每條規則都測「該觸發會觸發、不該觸發會跳過」（反證），送出用假 daemon 收。"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sched_gate as sg  # noqa: E402


@pytest.fixture
def daemon():
    got = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            got.append({"auth": self.headers.get("Authorization"), **body})
            self.send_response(200); self.end_headers(); self.wfile.write(b"{}")

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1], got
    srv.shutdown()


def _home(tmp: Path, jobs: dict, port: int) -> Path:
    (tmp / "team.yaml").write_text(
        f"health_port: {port}\ninstances:\n  boss: {{working_directory: .}}\n"
        "  a1: {working_directory: agents/a1}\n  a2: {working_directory: agents/a2}\n", encoding="utf-8")
    (tmp / "state").mkdir()
    (tmp / "state" / "api_token").write_text("tok123")
    (tmp / "config").mkdir()
    (tmp / "config" / "gated_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    return tmp


def _board(home: Path, tasks: list[dict]) -> None:
    (home / "tasks").mkdir(exist_ok=True)
    (home / "tasks" / "board.json").write_text(json.dumps({"tasks": tasks}), encoding="utf-8")


def test_tasks_open_fires_only_with_open_tasks(tmp_path, daemon):
    port, got = daemon
    h = _home(tmp_path, {"progress": {"target": "boss", "rule": "tasks_open", "prompt": "看任務板 {date}"}}, port)
    _board(h, [{"id": 1, "status": "done"}])
    assert "跳過" in sg.run(h, "progress") and got == []          # 反證：全部完成 → 不叫
    _board(h, [{"id": 1, "status": "done"}, {"id": 2, "status": "in_progress"}])
    assert "已觸發" in sg.run(h, "progress")
    assert got[0]["instance"] == "boss" and got[0]["auth"] == "Bearer tok123" and got[0]["expect_reply"] is False
    assert "{date}" not in got[0]["message"] and got[0]["source"] == "system:schedule-gate:progress"


def test_new_files_since_last_trigger(tmp_path, daemon):
    port, got = daemon
    h = _home(tmp_path, {"ingest": {"target": "boss", "rule": "new_files", "globs": ["knowledge/raw/**/*.md"], "prompt": "ingest"}}, port)
    raw = h / "knowledge" / "raw"; raw.mkdir(parents=True)
    assert "跳過" in sg.run(h, "ingest")                            # 沒有檔案
    (raw / "a.md").write_text("x")
    assert "已觸發" in sg.run(h, "ingest") and len(got) == 1
    assert "跳過" in sg.run(h, "ingest") and len(got) == 1          # 反證：沒有新檔 → 不重複叫
    time.sleep(0.02); (raw / "b.md").write_text("y")
    assert "已觸發" in sg.run(h, "ingest") and len(got) == 2


def test_new_daily_fanout_only_wakes_agents_with_new_daily(tmp_path, daemon):
    port, got = daemon
    h = _home(tmp_path, {"distill": {"target": "@new_daily", "rule": "new_files", "globs": ["**/memory/daily/*.md"], "prompt": "蒸餾"}}, port)
    for wd in ["memory", "agents/a1/memory", "agents/a2/memory"]:
        (h / wd / "daily").mkdir(parents=True)
    (h / "agents/a1/memory/daily/2026-11-18.md").write_text("x")
    out = sg.run(h, "distill")
    assert [g["instance"] for g in got] == ["a1"], out             # boss、a2 沒新 daily → 不叫（取代 broadcast_all）


def test_fingerprint_skip_when_unchanged(tmp_path, daemon):
    port, got = daemon
    h = _home(tmp_path, {"fp": {"target": "boss", "rule": "fingerprint", "prompt": "p"}}, port)
    _board(h, [{"id": 1, "status": "todo"}])
    assert "已觸發" in sg.run(h, "fp")
    assert "跳過" in sg.run(h, "fp")                               # 反證：沒變 → 跳過
    _board(h, [{"id": 1, "status": "done"}])
    assert "已觸發" in sg.run(h, "fp") and len(got) == 2


def test_max_skip_days_floor(tmp_path, daemon):
    port, got = daemon
    h = _home(tmp_path, {"p": {"target": "boss", "rule": "tasks_open", "prompt": "p", "max_skip_days": 7}}, port)
    _board(h, [])
    st = h / "state" / "gate"; st.mkdir(parents=True)
    (st / "p.json").write_text(json.dumps({"last_trigger": time.time() - 3 * 86400}))
    assert "跳過" in sg.run(h, "p")
    (st / "p.json").write_text(json.dumps({"last_trigger": time.time() - 8 * 86400}))
    assert "保底" in sg.run(h, "p") and len(got) == 1


def test_dry_sends_nothing_and_keeps_no_state(tmp_path, daemon):
    port, got = daemon
    h = _home(tmp_path, {"p": {"target": "boss", "rule": "tasks_open", "prompt": "p"}}, port)
    _board(h, [{"id": 1, "status": "todo"}])
    assert "[DRY]" in sg.run(h, "p", dry=True)
    assert got == [] and not (h / "state" / "gate" / "p.json").exists()


def test_api_failure_is_error_and_state_not_written(tmp_path):
    h = _home(tmp_path, {"p": {"target": "boss", "rule": "tasks_open", "prompt": "p"}}, 1)   # port 1：連不上
    _board(h, [{"id": 1, "status": "todo"}])
    assert sg.main(["p", "--home", str(h)]) == 1
    assert not (h / "state" / "gate" / "p.json").exists()          # 沒送出就不能記成已觸發


def test_check_reports_bad_config(tmp_path, daemon):
    port, _ = daemon
    h = _home(tmp_path, {"x": {"target": "ghost", "rule": "nope"}, "y": {"target": "boss", "rule": "git_paths", "prompt": "p"}}, port)
    probs = sg.check(h)
    assert any("ghost" in p for p in probs) and any("nope" in p for p in probs) and any("缺參數" in p for p in probs)
    (tmp_path / "ok").mkdir()
    ok = _home(tmp_path / "ok", {"a": {"target": "@new_daily", "rule": "new_files", "globs": ["x"], "prompt": "p"}}, port)
    assert sg.check(ok) == []
    empty = tmp_path / "e"; empty.mkdir(); _home(empty, {}, port)
    assert any("範圍是空的" in p for p in sg.check(empty))


def test_port_from_env_wins(tmp_path):
    (tmp_path / "team.yaml").write_text("health_port: 1111\ninstances: {}\n")
    assert sg.daemon_port(tmp_path) == 1111
    (tmp_path / ".env").write_text("TEAM_AGENT_PORT=23030\n")
    assert sg.daemon_port(tmp_path) == 23030
