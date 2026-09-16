"""多 agent 成本治理 — 檔案鎖 ledger（ADR-004 / F-10 / F-11）。

短命進程無共享狀態，用本機 append-only jsonl + fcntl.flock 實現：
- 每次執行前讀當日累計，dry-run 估算後檢查是否超預算 → BUDGET_EXCEEDED（exit 4）
- 每次執行後（成功/失敗皆）追加一行稽核紀錄
- ledger 目錄不可寫 → fail-closed（exit 2，守門不可靜默失效）
- ARK_DB_LEDGER_DISABLED=1 明示關閉

路徑：${ARK_DB_LEDGER_DIR:-~/.ark/db-query}/ledger-YYYY-MM-DD.jsonl
只存 sql_sha256（不存 SQL 原文，避免 ledger 成敏感資料外洩點）。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_common as C  # noqa: E402

try:
    import fcntl
    _HAS_FLOCK = True
except ImportError:  # Windows
    _HAS_FLOCK = False


def disabled() -> bool:
    return os.getenv("ARK_DB_LEDGER_DISABLED") == "1"


def ledger_dir() -> pathlib.Path:
    return pathlib.Path(os.getenv("ARK_DB_LEDGER_DIR",
                                  str(pathlib.Path.home() / ".ark" / "db-query")))


def _today_path() -> pathlib.Path:
    d = _dt.date.today().isoformat()
    return ledger_dir() / f"ledger-{d}.jsonl"


def agent_id(args=None) -> tuple[str, str]:
    """回 (agent_id, source)。ARK_AGENT_ID 優先，否則 basename(cwd)。"""
    aid = os.getenv("ARK_AGENT_ID") or (getattr(args, "agent_id", None) if args else None)
    if aid:
        return aid, "explicit"
    return pathlib.Path.cwd().name, "cwd-fallback"


def sql_sha256(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def _ensure_writable() -> pathlib.Path:
    """確保 ledger 目錄可寫，否則 fail-closed（exit 2）。回傳當日檔路徑。"""
    d = ledger_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / f".write-probe.{os.getpid()}"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        C.fail("BAD_INPUT", f"ledger 目錄不可寫: {d}（{e}）",
               "設 ARK_DB_LEDGER_DIR 到可寫路徑，或 ARK_DB_LEDGER_DISABLED=1 明示關閉")
    return _today_path()


def today_cost(aid: str) -> tuple[float, float]:
    """回 (該 agent 當日累計成本, 全體當日累計成本)。ledger 不存在回 (0,0)。"""
    p = _today_path()
    if not p.exists():
        return 0.0, 0.0
    agent_sum, team_sum = 0.0, 0.0
    with p.open("r", encoding="utf-8") as f:
        if _HAS_FLOCK:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cost = rec.get("estimated_cost_usd", 0) or 0
                team_sum += cost
                if rec.get("agent_id") == aid:
                    agent_sum += cost
        finally:
            if _HAS_FLOCK:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return agent_sum, team_sum


def check_budget(aid: str, estimate_usd: float) -> None:
    """dry-run 後檢查：當日累計 + 本次估算 > 預算 → BUDGET_EXCEEDED（exit 4）。"""
    if disabled():
        return
    agent_budget = os.getenv("ARK_BQ_DAILY_BUDGET_USD")
    team_budget = os.getenv("ARK_BQ_TEAM_DAILY_BUDGET_USD")
    if not agent_budget and not team_budget:
        return
    agent_sum, team_sum = today_cost(aid)
    if agent_budget and (agent_sum + estimate_usd) > float(agent_budget):
        C.fail("BUDGET_EXCEEDED",
               f"agent {aid} 當日累計 ${agent_sum:.4f} + 本次 ${estimate_usd:.4f} "
               f"超過每日預算 ${float(agent_budget):.2f}",
               "停止並回報使用者；或調高 ARK_BQ_DAILY_BUDGET_USD")
    if team_budget and (team_sum + estimate_usd) > float(team_budget):
        C.fail("BUDGET_EXCEEDED",
               f"團隊當日累計 ${team_sum:.4f} + 本次 ${estimate_usd:.4f} "
               f"超過團隊每日預算 ${float(team_budget):.2f}",
               "停止並回報使用者；或調高 ARK_BQ_TEAM_DAILY_BUDGET_USD")


def budget_remaining(aid: str) -> float | None:
    b = os.getenv("ARK_BQ_DAILY_BUDGET_USD")
    if not b or disabled():
        return None
    agent_sum, _ = today_cost(aid)
    return round(float(b) - agent_sum, 6)


def append(rec: dict) -> None:
    """追加一行稽核紀錄（帶 flock 獨佔鎖，並發安全）。"""
    if disabled():
        return
    p = _ensure_writable()
    rec = {"ts": _dt.datetime.now().isoformat(timespec="seconds"), **rec}
    line = json.dumps(rec, ensure_ascii=False)
    with p.open("a", encoding="utf-8") as f:
        if _HAS_FLOCK:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            if _HAS_FLOCK:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
