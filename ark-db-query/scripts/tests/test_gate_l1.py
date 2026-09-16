"""W0 反證測試 — read-only 守門的漏洞（F-01 / F-02）。

🔴 這些測試在 v2.0 上**必須是紅的** —— 它們證明現有守門抓不到這些案例。
W1 守門下沉（gate.py allowlist + 剝註解）完成後才會轉綠。

v2.0 的 guard_read_only 用 `_WRITE_RE = ^\\s*(insert|update|delete|...)`：
只錨定「語句開頭第一個 token」，於是
- 前置註解（`-- x\\nDELETE`）→ 首 token 是 `--` → 不匹配 → 放行（F-01）
- 巢狀/腳本寫入（`BEGIN…END`、`EXECUTE IMMEDIATE`、`CALL`、`SELECT…INTO`）
  首 token 不在 denylist → 放行（F-02）

allowlist（語句首必須 ∈ 讀關鍵字）能封閉這兩類：不是 SELECT/WITH/… 開頭就拒絕。
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


def run(*args):
    return subprocess.run([sys.executable, str(DB_QUERY), *map(str, args)],
                          capture_output=True, text=True)


def _blocked(r) -> bool:
    """守門攔下 = 非 0 exit + GATE_BLOCKED。"""
    if r.returncode == 0:
        return False
    try:
        return json.loads(r.stdout).get("error", {}).get("code") == "GATE_BLOCKED"
    except (json.JSONDecodeError, AttributeError):
        return False


# ── F-01：前置註解繞過 ─────────────────────────────────────────

@pytest.mark.parametrize("sql", [
    "-- harmless note\nDELETE FROM players",
    "/* block comment */ DELETE FROM players",
    "  -- leading whitespace + comment\n  UPDATE players SET vip = 9",
    "\n\n-- newline first\nDROP TABLE players",
])
def test_leading_comment_cannot_bypass_gate(db, sql):
    """F-01：前置註解不得繞過 read-only 守門。"""
    r = run("--db-type", "sqlite", "--db-path", db, "--sql", sql)
    assert _blocked(r), f"守門放行了寫入（前置註解繞過）:\n{r.stdout}\n{r.stderr}"
    # 反證：資料真的沒被動到
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='players'").fetchall()
    remaining = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] if n else 0
    conn.close()
    assert n and remaining == 60, "資料被寫入語句改動了（守門形同虛設）"


# ── F-02：巢狀 / 腳本寫入入口 ───────────────────────────────────

@pytest.mark.parametrize("sql", [
    "BEGIN; DELETE FROM players; END",
    "CREATE TABLE t2 AS SELECT * FROM players",          # CTAS：寫入偽裝成 SELECT 尾巴
    "WITH x AS (SELECT 1) DELETE FROM players",          # CTE 開頭、寫入在後
    "INSERT INTO players SELECT * FROM players",         # INSERT…SELECT
])
def test_nested_write_entrypoints_blocked(db, sql):
    """F-02：巢狀 / 腳本語法的寫入入口必須被攔。"""
    r = run("--db-type", "sqlite", "--db-path", db, "--sql", sql)
    assert _blocked(r), f"守門放行了巢狀寫入:\n{r.stdout}\n{r.stderr}"


# ── AC-03：allowlist 封閉性 —— 非讀關鍵字開頭一律拒絕 ──────────

@pytest.mark.parametrize("sql", [
    "PRAGMA writable_schema = ON",   # PRAGMA 寫入態（sqlite 白名單子集之外）
    "VACUUM",                        # 不在讀 allowlist
])
def test_non_readonly_keyword_rejected(db, sql):
    """AC-03：語句首 keyword 不在讀 allowlist → 拒絕（封閉集合，預設拒絕）。"""
    r = run("--db-type", "sqlite", "--db-path", db, "--sql", sql)
    assert _blocked(r), f"非讀關鍵字未被 allowlist 擋下:\n{r.stdout}\n{r.stderr}"
