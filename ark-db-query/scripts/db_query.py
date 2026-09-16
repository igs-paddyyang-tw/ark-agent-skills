#!/usr/bin/env python3
"""多資料庫查詢統一入口 — agent 直接以 bash 呼叫，回傳統一 JSON 契約。

支援: sqlite / postgresql / mysql / mssql / mongodb
（bigquery 請直接用 bq_query.py，功能更完整：dry-run、成本守門）

用法:
  python db_query.py --db-type sqlite --db-path ./data/app.db --sql "SELECT ..."
  python db_query.py --db-type postgresql --host H --database D --user U --password-env PG_PASS --sql-file q.sql
  python db_query.py --db-type mongodb --host H --port 27017 --database db \
      --collection player_profiles --filter '{"vip_level":{"$gte":5}}' --limit 20
  echo "SELECT 1" | python db_query.py --db-type sqlite --db-path app.db

參數化查詢（防 SQL injection）:
  --sql "SELECT * FROM t WHERE id = ?" --params '[123]'          # sqlite / mssql(%s轉換)
  --sql "SELECT * FROM t WHERE id = %s" --params '[123]'         # postgresql / mysql
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_common as C  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Unified DB query CLI")
    ap.add_argument("--db-type", required=True,
                    choices=["sqlite", "postgresql", "mysql", "mssql", "mongodb", "bigquery"])
    ap.add_argument("--db-path", help="SQLite 檔案路徑")
    ap.add_argument("--host", default=os.getenv("ARK_DB_HOST", "localhost"))
    ap.add_argument("--port", type=int)
    ap.add_argument("--database", default=os.getenv("ARK_DB_NAME", ""))
    ap.add_argument("--user", default=os.getenv("ARK_DB_USER", ""))
    ap.add_argument("--password", help="不建議明文；優先用 --password-env")
    ap.add_argument("--password-env", help="讀此環境變數作為密碼（建議）")
    ap.add_argument("--sql", help="SQL 字串")
    ap.add_argument("--sql-file", help="SQL 檔路徑（建議）")
    ap.add_argument("--params", help='參數化查詢的 JSON array，如 \'[123, "abc"]\'')
    # MongoDB
    ap.add_argument("--collection")
    ap.add_argument("--filter", default="{}", help="MongoDB filter JSON")
    ap.add_argument("--projection", default="", help="MongoDB projection JSON")
    ap.add_argument("--sort", default="", help='如 \'[["ltv.total_spend", -1]]\'')
    ap.add_argument("--auth-source", default="admin")
    # 共通
    ap.add_argument("--limit", type=int, default=C.DEFAULT_LIMIT)
    ap.add_argument("--no-limit", action="store_true", help="取消 limit（配合 --out）")
    ap.add_argument("--allow-write", action="store_true")
    ap.add_argument("--out", help="全量結果落盤路徑")
    ap.add_argument("--out-format", choices=["jsonl", "json", "csv"], default="jsonl")
    ap.add_argument("--max-stdout-rows", type=int, default=C.DEFAULT_STDOUT_ROWS)
    ap.add_argument("--max-stdout-bytes", type=int, default=None,
                    help="stdout 位元組上限（預設 64 KiB，ARK_DB_STDOUT_BYTES）")
    ap.add_argument("--timeout", type=int, default=30, help="（相容別名）連線+查詢逾時")
    ap.add_argument("--connect-timeout", type=int, default=None, help="連線逾時秒（預設 10）")
    ap.add_argument("--query-timeout", type=int, default=None, help="查詢執行逾時秒（預設 60）")
    ap.add_argument("--agent-id", default=os.getenv("ARK_AGENT_ID"), help="稽核用 agent 識別")
    ap.add_argument("--gate-explain", action="store_true", help="回報守門判定細節")
    return ap


def _params(args) -> list:
    if not args.params:
        return []
    try:
        p = json.loads(args.params)
        if not isinstance(p, list):
            raise ValueError
        return p
    except ValueError:
        C.fail("BAD_INPUT", "--params 必須是 JSON array", '例: --params \'[123]\'')
        return []


def main() -> None:
    C.load_env()
    args = build_parser().parse_args()
    if getattr(args, "password", None):
        print("⚠️ --password 明文已 deprecated（會出現在 ps/history），請改用 --password-env",
              file=sys.stderr)

    if args.db_type == "bigquery":
        C.fail("BAD_INPUT", "BigQuery 請改用 bq_query.py",
               "python scripts/bq_query.py --project ... --sql-file q.sql（含 dry-run 成本守門）")

    import itertools
    import drivers as D  # 同目錄

    if args.db_type == "mongodb":
        with C.Timer() as t:
            try:
                rows = list(itertools.islice(D.iter_mongodb(args), args.limit))
            except SystemExit:
                raise
            except Exception as e:
                C.fail("QUERY_FAILED", f"MongoDB 查詢失敗: {e}",
                       "確認 --auth-source 與 --database 是否為同一個庫")
                return
        C.finalize_rows(rows, args, {"db_type": "mongodb", "elapsed_ms": t.elapsed_ms})
        return

    sql = C.read_sql(args)
    C.guard_read_only(sql, args.allow_write)   # L1 allowlist
    params = _params(args)
    limit = None if getattr(args, "no_limit", False) else args.limit
    with C.Timer() as t:
        try:
            it = D.iter_rows(args, sql, params)
            rows = list(it if limit is None else itertools.islice(it, limit))
        except SystemExit:
            raise
        except Exception as e:
            msg = str(e).lower()
            code = ("TIMEOUT" if "timeout" in msg or "statement timeout" in msg
                    else "CONN_FAILED" if "connect" in msg else "QUERY_FAILED")
            C.fail(code, f"{args.db_type} 失敗: {e}",
                   "先跑 python scripts/db_health.py 檢查連線")
            return
    C.finalize_rows(rows, args, {"db_type": args.db_type, "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
