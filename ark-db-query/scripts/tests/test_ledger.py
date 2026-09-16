"""W3 驗收 — ledger 並發、預算攔截、fail-closed（AC-11~14）。"""
from __future__ import annotations

import importlib
import multiprocessing as mp
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("ARK_DB_LEDGER_DIR", str(tmp_path / "ledger"))
    monkeypatch.delenv("ARK_DB_LEDGER_DISABLED", raising=False)
    import ledger as L
    importlib.reload(L)
    return L


# ── AC-14：9 並發各 append 100 行 = 900 無損 ──────────────────

def _worker(ledger_dir, n):
    os.environ["ARK_DB_LEDGER_DIR"] = ledger_dir
    import importlib
    import ledger as L
    importlib.reload(L)
    for i in range(n):
        L.append({"agent_id": f"w{os.getpid()}", "db_type": "sqlite",
                  "estimated_cost_usd": 0.0, "exit_code": 0, "seq": i})


def test_concurrent_appends_lose_no_lines(ledger, tmp_path):
    ldir = os.environ["ARK_DB_LEDGER_DIR"]
    procs = [mp.Process(target=_worker, args=(ldir, 100)) for _ in range(9)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    files = list(Path(ldir).glob("ledger-*.jsonl"))
    assert files, "沒有產生 ledger 檔"
    total = sum(len(f.read_text(encoding="utf-8").strip().splitlines()) for f in files)
    assert total == 900, f"並發 append 遺失了行：{total} != 900"


# ── AC-11：預算攔截 ────────────────────────────────────────────

def test_budget_exceeded_blocks_before_execution(ledger, monkeypatch):
    monkeypatch.setenv("ARK_BQ_DAILY_BUDGET_USD", "1.00")
    ledger.append({"agent_id": "a1", "estimated_cost_usd": 0.90})
    with pytest.raises(SystemExit) as ei:
        ledger.check_budget("a1", 0.20)   # 0.90 + 0.20 > 1.00
    assert ei.value.code == 4, "BUDGET_EXCEEDED 應 exit 4"


def test_budget_within_limit_passes(ledger, monkeypatch):
    monkeypatch.setenv("ARK_BQ_DAILY_BUDGET_USD", "1.00")
    ledger.append({"agent_id": "a1", "estimated_cost_usd": 0.50})
    ledger.check_budget("a1", 0.20)   # 0.70 < 1.00 → 不拋


# ── AC-13：ledger 目錄不可寫 → fail-closed（exit 2）───────────

def test_unwritable_ledger_dir_fails_closed(tmp_path, monkeypatch):
    bad = tmp_path / "nope"
    bad.write_text("i am a file not a dir", encoding="utf-8")  # 無法當目錄
    monkeypatch.setenv("ARK_DB_LEDGER_DIR", str(bad / "sub"))
    monkeypatch.delenv("ARK_DB_LEDGER_DISABLED", raising=False)
    import ledger as L
    importlib.reload(L)
    with pytest.raises(SystemExit) as ei:
        L.append({"agent_id": "a1", "estimated_cost_usd": 0.1})
    assert ei.value.code == 2, "ledger 不可寫應 fail-closed exit 2"


def test_disabled_ledger_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("ARK_DB_LEDGER_DISABLED", "1")
    monkeypatch.setenv("ARK_DB_LEDGER_DIR", str(tmp_path / "x"))
    import ledger as L
    importlib.reload(L)
    L.append({"agent_id": "a1", "estimated_cost_usd": 0.1})   # 不應建檔、不拋
    L.check_budget("a1", 999.0)                                # disabled 時不攔
    assert not (tmp_path / "x").exists() or not list((tmp_path / "x").glob("*.jsonl"))
