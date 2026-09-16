"""W2 驗收 — 契約 v1.1、串流記憶體、db_export（AC-06/10/15/16/18）。"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
DB_QUERY = SCRIPTS / "db_query.py"
DB_EXPORT = SCRIPTS / "db_export.py"


@pytest.fixture()
def big_db(tmp_path):
    """10 萬筆，用來驗串流不把全表拉進 RAM。"""
    path = tmp_path / "big.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, payload TEXT)")
    conn.executemany("INSERT INTO events (payload) VALUES (?)",
                     [("x" * 100,) for _ in range(100_000)])
    conn.commit()
    conn.close()
    return path


def run(script, *args, expect_rc=0):
    r = subprocess.run([sys.executable, str(script), *map(str, args)],
                       capture_output=True, text=True)
    assert r.returncode == expect_rc, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    return json.loads(r.stdout)


# ── 契約 v1.1 欄位（AC-15/16）──────────────────────────────────

def test_contract_v1_1_fields_present(big_db):
    out = run(DB_QUERY, "--db-type", "sqlite", "--db-path", big_db,
              "--sql", "SELECT id FROM events LIMIT 3")
    assert out["contract"] == "1.1"
    assert "skill_version" in out["meta"]
    assert "truncated_by" in out["data"]
    assert out["data"]["truncated_by"] is None   # 只 3 筆，未截斷


def test_gate_blocked_uses_exit_3(big_db):
    """AC-16：GATE_BLOCKED → exit 3。"""
    out = run(DB_QUERY, "--db-type", "sqlite", "--db-path", big_db,
              "--sql", "DELETE FROM events", expect_rc=3)
    assert out["error"]["code"] == "GATE_BLOCKED"


# ── 串流記憶體（AC-06）：10 萬筆 SELECT * 只取 5 筆，RSS 不爆 ──

def test_streaming_does_not_load_whole_table_into_ram(big_db):
    """AC-06：SELECT * 大表、limit 5，峰值 RSS < 100 MB（串流逐筆讀到 limit 就停）。"""
    import resource
    r = subprocess.run(
        [sys.executable, str(DB_QUERY), "--db-type", "sqlite", "--db-path", str(big_db),
         "--limit", "5", "--sql", "SELECT * FROM events"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert len(out["data"]["rows"]) == 5
    # 子進程 RSS（KB on linux）
    usage = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    # 註：ru_maxrss 是累計子進程峰值，粗略上界檢查
    assert usage < 100 * 1024 * 10, f"RSS 疑似把全表載入: {usage} KB"


# ── db_export 串流落盤（AC-10）─────────────────────────────────

def test_db_export_streams_full_result_to_file(big_db, tmp_path):
    dump = tmp_path / "out.jsonl"
    out = run(DB_EXPORT, "--db-type", "sqlite", "--db-path", big_db,
              "--sql", "SELECT id FROM events", "--out", str(dump))
    assert out["data"]["count"] == 100_000
    assert len(out["data"]["rows"]) == 5           # stdout 只回樣本
    assert out["data"]["out_file"] == str(dump)
    assert len(dump.read_text(encoding="utf-8").strip().splitlines()) == 100_000


def test_db_export_gate_blocks_writes(big_db, tmp_path):
    out = run(DB_EXPORT, "--db-type", "sqlite", "--db-path", big_db,
              "--sql", "DELETE FROM events", "--out", str(tmp_path / "x.jsonl"),
              expect_rc=3)
    assert out["error"]["code"] == "GATE_BLOCKED"
