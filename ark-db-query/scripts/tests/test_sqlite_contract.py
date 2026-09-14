"""db-query 端到端守門 —— 用真的 SQLite 跑，驗 JSON 契約與兩道守門。

## 為什麼需要這支

本 skill 是 **executor**：agent 直接以 bash 呼叫、拿 stdout 當資料。
它的契約（`success` / `data.rows` / `count` / `truncated` / `out_file` / `meta`）
與兩道 deterministic 守門（read-only 預設、stdout 截斷保護 context window）
**在加這支之前沒有任何東西在跑**。

SQLite 不需要外部服務，所以這條路徑可以真的端到端驗；
其他 driver（pg / mysql / mssql / mongo）共用同一組 `db_common` 收尾與守門，
在這裡驗到的就是它們共用的那一段。

> 🔴 守門的反證比守門本身重要：`test_read_only_gate_blocks_writes` 若拿掉
> `--allow-write` 仍能寫入，那道 GATE_BLOCKED 就是裝飾品。
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
DB_QUERY = SCRIPTS / "db_query.py"


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "app.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, name TEXT, vip INTEGER)")
    conn.executemany("INSERT INTO players (name, vip) VALUES (?, ?)",
                     [(f"p{i}", i % 7) for i in range(1, 61)])
    conn.commit()
    conn.close()
    return path


def run(*args, expect_rc=0) -> dict:
    r = subprocess.run([sys.executable, str(DB_QUERY), *map(str, args)],
                       capture_output=True, text=True)
    assert r.returncode == expect_rc, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    return json.loads(r.stdout)


# ── 契約：成功回傳的形狀 ───────────────────────────────────────

def test_select_returns_the_documented_contract(db):
    out = run("--db-type", "sqlite", "--db-path", db,
              "--sql", "SELECT id, name FROM players ORDER BY id LIMIT 3")
    assert out["success"] is True
    data = out["data"]
    assert set(data) >= {"rows", "count", "truncated", "out_file"}
    assert data["count"] == 3
    assert data["rows"][0] == {"id": 1, "name": "p1"}
    assert data["truncated"] is False
    assert data["out_file"] is None
    assert "meta" in out


def test_parameterized_query_binds_instead_of_interpolating(db):
    """參數化是防注入的實作方式 —— 要驗它真的有綁上去"""
    out = run("--db-type", "sqlite", "--db-path", db,
              "--sql", "SELECT name FROM players WHERE id = ?", "--params", "[7]")
    assert [r["name"] for r in out["data"]["rows"]] == ["p7"]


# ── 守門一：read-only 是預設 ───────────────────────────────────

@pytest.mark.parametrize("sql", [
    "DELETE FROM players",
    "UPDATE players SET vip = 9",
    "DROP TABLE players",
    "INSERT INTO players (name, vip) VALUES ('x', 1)",
])
def test_read_only_gate_blocks_writes(db, sql):
    out = run("--db-type", "sqlite", "--db-path", db, "--sql", sql, expect_rc=1)
    assert out["success"] is False
    assert out["error"]["code"] == "GATE_BLOCKED"

    # 反證：資料真的沒被動到（不是只印了錯誤訊息）
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 60
    conn.close()


def test_allow_write_actually_lets_the_write_through(db):
    """反證上一條：加了 --allow-write 就要真的寫得進去，否則那道門是壞的不是嚴的"""
    run("--db-type", "sqlite", "--db-path", db, "--allow-write",
        "--sql", "DELETE FROM players WHERE id > 50")
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 50
    conn.close()


# ── 守門二：stdout 截斷（保護 agent 的 context window）──────────

def test_stdout_is_truncated_and_says_so(db):
    out = run("--db-type", "sqlite", "--db-path", db, "--limit", "60",
              "--max-stdout-rows", "5",
              "--sql", "SELECT * FROM players ORDER BY id")
    assert out["data"]["count"] == 60
    assert len(out["data"]["rows"]) == 5
    assert out["data"]["truncated"] is True, "截斷了卻沒說 → agent 會以為只有 5 筆"


def test_out_file_gets_the_full_result_not_the_sample(db, tmp_path):
    dump = tmp_path / "full.jsonl"
    out = run("--db-type", "sqlite", "--db-path", db, "--limit", "60",
              "--max-stdout-rows", "5", "--out", str(dump),
              "--sql", "SELECT * FROM players ORDER BY id")
    assert out["data"]["out_file"] == str(dump)
    assert len(dump.read_text(encoding="utf-8").strip().splitlines()) == 60


# ── 失敗路徑也要是契約，不是 traceback ──────────────────────────

@pytest.mark.parametrize("args,code", [
    (("--db-type", "sqlite", "--sql", "SELECT 1"), "BAD_INPUT"),          # 缺 --db-path
    (("--db-type", "sqlite", "--db-path", "X", "--sql", "SELECT 1",
      "--params", "{}"), "BAD_INPUT"),                                     # params 非 array
])
def test_input_errors_come_back_as_json_not_traceback(db, args, code):
    args = tuple(str(db) if a == "X" else a for a in args)
    out = run(*args, expect_rc=1)
    assert out["success"] is False and out["error"]["code"] == code
    assert out["error"]["hint"], "錯誤要帶 hint —— agent 靠它自我修正"
