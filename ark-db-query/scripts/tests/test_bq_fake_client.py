"""W0 反證測試 — BQ 執行層的漏洞（F-05 / F-07）。

🔴 這些在 v2.0 上**必須是紅的**。用 fake bigquery.Client，不需要真 GCP 憑證。

- F-05：`"limit" not in sql.lower().split()[-2:]` 是脆弱啟發式。
  `SELECT … LIMIT 10 OFFSET 5` 末兩 token 是 `offset 5` → 判定「沒有 LIMIT」
  → 重複補 `LIMIT`，產生 `… LIMIT 10 OFFSET 5\\nLIMIT 50`（BQ 語法錯）。
  v3.0（ADR-002）改用 max_results，根本不改寫 SQL。
- F-07：`job.result(timeout=)` 逾時拋錯後，v2.0 直接 fail，**沒有 job.cancel()**
  → BQ 端繼續跑且照常計費。v3.0 逾時必 cancel。
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))


class FakeQueryJob:
    """記錄被送進來的 SQL；可設定 result() 逾時。"""
    def __init__(self, sql, *, dry_run, total_bytes=1000, raise_timeout=False):
        self.sql = sql
        self._dry_run = dry_run
        self.total_bytes_processed = total_bytes
        self.job_id = "fake-job-1"
        self.cache_hit = False
        self.cancelled = False
        self._raise_timeout = raise_timeout
        self.statement_type = "SELECT"

    def result(self, timeout=None):
        if self._raise_timeout:
            raise TimeoutError("job exceeded timeout")
        return []

    def cancel(self):
        self.cancelled = True


class FakeClient:
    def __init__(self, **kw):
        self.queries = []          # 所有被送出的 SQL（dry-run + 執行）
        self.jobs = []
        self._raise_timeout_on_exec = False

    def query(self, sql, job_config=None):
        dry = bool(getattr(job_config, "dry_run", False))
        job = FakeQueryJob(sql, dry_run=dry,
                           raise_timeout=(not dry and self._raise_timeout_on_exec))
        self.queries.append(sql)
        self.jobs.append(job)
        return job


@pytest.fixture()
def bq(monkeypatch):
    """裝一個假的 google.cloud.bigquery，讓 bq_query 跑得起來、不碰真 GCP。"""
    fake_bq = types.ModuleType("bigquery")

    def _job_config(**kw):
        cfg = types.SimpleNamespace(**kw)
        return cfg
    fake_bq.QueryJobConfig = _job_config
    fake_bq.Client = FakeClient

    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    cloud.bigquery = fake_bq
    google.cloud = cloud
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", fake_bq)
    monkeypatch.setenv("ARK_BQ_ADC_OK", "1")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "fake-proj")

    import importlib
    import bq_query
    importlib.reload(bq_query)
    return bq_query


def _run_main(bq_query, argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["bq_query.py", *argv])
    try:
        bq_query.main()
    except SystemExit:
        pass


# ── F-05：OFFSET 尾巴導致重複補 LIMIT ──────────────────────────

def test_offset_tail_does_not_get_a_duplicate_limit(bq, monkeypatch):
    """F-05：`LIMIT 10 OFFSET 5` 已有 LIMIT，不該再被補一個 LIMIT。"""
    holder = {}

    def _patched_get_client(project, location):
        c = FakeClient()
        holder["client"] = c
        return c
    monkeypatch.setattr(bq, "get_client", _patched_get_client)
    _run_main(bq, ["--sql", "SELECT id FROM t LIMIT 10 OFFSET 5"], monkeypatch)
    exec_sql = holder["client"].queries[-1]   # 最後一次 = 實際執行
    assert exec_sql.lower().count("limit") == 1, \
        f"OFFSET 尾巴被誤判成沒 LIMIT → 重複補：\n{exec_sql!r}"


# ── F-07：逾時後必須 cancel job ────────────────────────────────

def test_timeout_cancels_the_bq_job(bq, monkeypatch):
    """F-07：job.result 逾時後，必須呼叫 job.cancel()，否則 BQ 端繼續計費。"""
    holder = {}

    def _patched_get_client(project, location):
        c = FakeClient()
        c._raise_timeout_on_exec = True
        holder["client"] = c
        return c
    monkeypatch.setattr(bq, "get_client", _patched_get_client)
    _run_main(bq, ["--sql", "SELECT id FROM t", "--timeout", "1"], monkeypatch)
    exec_job = holder["client"].jobs[-1]
    assert exec_job.cancelled, "逾時後沒有 cancel job → BQ 端繼續跑且計費"
