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
    ap.add_argument("--allow-write", action="store_true")
    ap.add_argument("--out", help="全量結果落盤路徑")
    ap.add_argument("--out-format", choices=["jsonl", "json", "csv"], default="jsonl")
    ap.add_argument("--max-stdout-rows", type=int, default=C.DEFAULT_STDOUT_ROWS)
    ap.add_argument("--timeout", type=int, default=30)
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


def _need(mod: str, pip_name: str):
    try:
        return __import__(mod)
    except ImportError:
        C.fail("DRIVER_MISSING", f"缺 {pip_name}",
               f"pip install {pip_name} --break-system-packages")


# ---------------------------------------------------------------- drivers
def q_sqlite(args, sql, params):
    import sqlite3
    if not args.db_path:
        C.fail("BAD_INPUT", "sqlite 需要 --db-path", "")
    conn = sqlite3.connect(args.db_path, timeout=args.timeout)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchmany(args.limit)]
        if args.allow_write:
            conn.commit()
        return rows
    finally:
        conn.close()


def q_postgresql(args, sql, params):
    pw = C.secret(args.password, args.password_env)
    try:
        psycopg = _need("psycopg", "psycopg[binary]")
        conn = psycopg.connect(host=args.host, port=args.port or 5432,
                               dbname=args.database, user=args.user, password=pw,
                               connect_timeout=args.timeout)
    except SystemExit:
        psycopg2 = _need("psycopg2", "psycopg2-binary")  # fallback
        conn = psycopg2.connect(host=args.host, port=args.port or 5432,
                                dbname=args.database, user=args.user, password=pw,
                                connect_timeout=args.timeout)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or None)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = [dict(zip(cols, r)) for r in cur.fetchmany(args.limit)] if cols else []
        if args.allow_write:
            conn.commit()
        return rows
    finally:
        conn.close()


def q_mysql(args, sql, params):
    pymysql = _need("pymysql", "pymysql")
    pw = C.secret(args.password, args.password_env)
    conn = pymysql.connect(host=args.host, port=args.port or 3306, user=args.user,
                           password=pw, database=args.database,
                           connect_timeout=args.timeout,
                           cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or None)
            rows = list(cur.fetchmany(args.limit))
        if args.allow_write:
            conn.commit()
        return rows
    finally:
        conn.close()


def q_mssql(args, sql, params):
    pymssql = _need("pymssql", "pymssql")
    pw = C.secret(args.password, args.password_env)
    conn = pymssql.connect(server=args.host, port=args.port or 1433, user=args.user,
                           password=pw, database=args.database,
                           login_timeout=args.timeout)
    try:
        cur = conn.cursor(as_dict=True)
        cur.execute(sql, tuple(params) if params else None)
        rows = cur.fetchmany(args.limit) or []
        if args.allow_write:
            conn.commit()
        return rows
    finally:
        conn.close()


def q_mongodb(args):
    _need("pymongo", "pymongo")
    from pymongo import MongoClient
    if not args.collection:
        C.fail("BAD_INPUT", "mongodb 需要 --collection", "")
    if not args.database:
        C.fail("BAD_INPUT", "mongodb 需要 --database", "")
    try:
        flt = json.loads(args.filter or "{}")
        proj = json.loads(args.projection) if args.projection else None
        sort = json.loads(args.sort) if args.sort else None
    except json.JSONDecodeError as e:
        C.fail("BAD_INPUT", f"filter/projection/sort JSON 解析失敗: {e}", "")
        return []
    pw = C.secret(args.password, args.password_env)
    kw = dict(host=args.host, port=args.port or 27017,
              serverSelectionTimeoutMS=args.timeout * 1000)
    if args.user:
        kw.update(username=args.user, password=pw, authSource=args.auth_source)
    client = MongoClient(**kw)
    try:
        cur = client[args.database][args.collection].find(flt, proj)
        if sort:
            cur = cur.sort([tuple(s) for s in sort])
        cur = cur.limit(args.limit)
        return [{**doc, "_id": str(doc.get("_id"))} for doc in cur]
    except Exception as e:
        C.fail("QUERY_FAILED", f"MongoDB 查詢失敗: {e}", "")
        return []
    finally:
        client.close()


def main() -> None:
    C.load_env()
    args = build_parser().parse_args()

    if args.db_type == "bigquery":
        C.fail("BAD_INPUT", "BigQuery 請改用 bq_query.py",
               "python scripts/bq_query.py --project ... --sql-file q.sql（含 dry-run 成本守門）")

    if args.db_type == "mongodb":
        with C.Timer() as t:
            rows = q_mongodb(args)
        C.finalize_rows(rows, args, {"db_type": "mongodb", "elapsed_ms": t.elapsed_ms})
        return

    sql = C.read_sql(args)
    C.guard_read_only(sql, args.allow_write)
    params = _params(args)
    fn = {"sqlite": q_sqlite, "postgresql": q_postgresql,
          "mysql": q_mysql, "mssql": q_mssql}[args.db_type]
    with C.Timer() as t:
        try:
            rows = fn(args, sql, params)
        except SystemExit:
            raise
        except Exception as e:
            C.fail("CONN_FAILED" if "connect" in str(e).lower() else "QUERY_FAILED",
                   f"{args.db_type} 失敗: {e}",
                   "先跑 python scripts/db_health.py 檢查連線")
            return
    C.finalize_rows(rows, args, {"db_type": args.db_type, "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
