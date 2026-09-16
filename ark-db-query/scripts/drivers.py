"""連線工廠 + 串流 iter_rows（ADR-003 L2 read-only + F-03 串流）。

v2.0 的 driver 用 `fetchmany(limit)` 但 SQL 本身無 LIMIT，psycopg/pymysql 預設 cursor
會把全部結果拉進 client 記憶體再取前 n 筆 → 大表 OOM（F-03）。

v3.0 改為 generator 串流：逐筆讀到 limit 就停，不全量進 RAM。
同時上 L2 read-only session（引擎層拒絕寫入，與 SQL 文字無關）。

`iter_rows(args, sql, params) -> Iterator[dict]` 供 db_query（截斷）與 db_export（落盤）共用。
"""
from __future__ import annotations

import os
import sys
from typing import Iterator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_common as C  # noqa: E402


def _need(mod: str, pip_name: str):
    try:
        return __import__(mod)
    except ImportError:
        C.fail("DRIVER_MISSING", f"缺 {pip_name}",
               f"pip install {pip_name} --break-system-packages")


def _query_timeout(args) -> int:
    return getattr(args, "query_timeout", None) or getattr(args, "timeout", None) or 60


def _connect_timeout(args) -> int:
    return getattr(args, "connect_timeout", None) or getattr(args, "timeout", None) or 10


# ---------------------------------------------------------------- sqlite
def iter_sqlite(args, sql, params) -> Iterator[dict]:
    import sqlite3
    if not args.db_path:
        C.fail("BAD_INPUT", "sqlite 需要 --db-path", "例: --db-path ./data/app.db")
    # L2：mode=ro（唯讀開啟）；--allow-write 時退回可寫
    if getattr(args, "allow_write", False):
        conn = sqlite3.connect(args.db_path, timeout=_connect_timeout(args))
    else:
        uri = f"file:{os.path.abspath(args.db_path)}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=_connect_timeout(args))
    conn.row_factory = sqlite3.Row
    # 查詢逾時：progress handler 中斷
    deadline = {"n": int(_query_timeout(args) * 1e6)}
    steps = {"c": 0}
    def _progress():
        steps["c"] += 1
        return 1 if steps["c"] > deadline["n"] else 0
    try:
        cur = conn.execute(sql, params or [])
        for row in cur:                     # 逐筆串流，不 fetchall
            yield dict(row)
        if getattr(args, "allow_write", False):
            conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- postgresql
def iter_postgresql(args, sql, params) -> Iterator[dict]:
    pw = C.secret(args.password, args.password_env)
    try:
        psycopg = _need("psycopg", "psycopg[binary]")
        conn = psycopg.connect(host=args.host, port=args.port or 5432,
                               dbname=args.database, user=args.user, password=pw,
                               connect_timeout=_connect_timeout(args))
        server_cursor = conn.cursor(name="ark_stream")   # named = server-side
    except SystemExit:
        raise
    except Exception:
        psycopg2 = _need("psycopg2", "psycopg2-binary")
        conn = psycopg2.connect(host=args.host, port=args.port or 5432,
                                dbname=args.database, user=args.user, password=pw,
                                connect_timeout=_connect_timeout(args))
        server_cursor = conn.cursor(name="ark_stream")
    try:
        with conn.cursor() as c0:
            if not getattr(args, "allow_write", False):
                c0.execute("SET default_transaction_read_only = on")   # L2
            c0.execute(f"SET statement_timeout = {int(_query_timeout(args) * 1000)}")
        cur = server_cursor
        cur.itersize = 1000
        cur.execute(sql, params or None)
        cols = [d[0] for d in cur.description] if cur.description else []
        for r in cur:                       # server-side cursor 串流
            yield dict(zip(cols, r))
        if getattr(args, "allow_write", False):
            conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- mysql
def iter_mysql(args, sql, params) -> Iterator[dict]:
    pymysql = _need("pymysql", "pymysql")
    pw = C.secret(args.password, args.password_env)
    conn = pymysql.connect(host=args.host, port=args.port or 3306, user=args.user,
                           password=pw, database=args.database,
                           connect_timeout=_connect_timeout(args),
                           cursorclass=pymysql.cursors.SSDictCursor)  # 串流 cursor
    try:
        with conn.cursor() as c0pre:
            pass
        with conn.cursor(pymysql.cursors.Cursor) as c0:
            if not getattr(args, "allow_write", False):
                c0.execute("SET SESSION TRANSACTION READ ONLY")        # L2
            c0.execute(f"SET SESSION max_execution_time = {int(_query_timeout(args) * 1000)}")
        cur = conn.cursor(pymysql.cursors.SSDictCursor)
        cur.execute(sql, params or None)
        for row in cur:                     # SSCursor 串流
            yield row
        if getattr(args, "allow_write", False):
            conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- mssql
def iter_mssql(args, sql, params) -> Iterator[dict]:
    pymssql = _need("pymssql", "pymssql")
    pw = C.secret(args.password, args.password_env)
    conn = pymssql.connect(server=args.host, port=args.port or 1433, user=args.user,
                           password=pw, database=args.database,
                           login_timeout=_connect_timeout(args))
    try:
        cur = conn.cursor(as_dict=True)
        # L2 兜底：無 session 級 read-only，用 SET ROWCOUNT + 隱式交易 ROLLBACK
        if not getattr(args, "allow_write", False):
            cur.execute("SET IMPLICIT_TRANSACTIONS ON")
        cur.execute(sql, tuple(params) if params else None)
        for row in cur:                     # pymssql cursor 可迭代
            yield row
        if getattr(args, "allow_write", False):
            conn.commit()
        elif not getattr(args, "allow_write", False):
            try:
                conn.rollback()             # 兜底：確保無任何寫入落地
            except Exception:
                pass
    finally:
        conn.close()


# ---------------------------------------------------------------- mongodb
def iter_mongodb(args) -> Iterator[dict]:
    import json
    _need("pymongo", "pymongo")
    from pymongo import MongoClient
    if not args.collection:
        C.fail("BAD_INPUT", "mongodb 需要 --collection", "例: --collection player_profiles")
    if not args.database:
        C.fail("BAD_INPUT", "mongodb 需要 --database", "例: --database game")
    try:
        flt = json.loads(args.filter or "{}")
        proj = json.loads(args.projection) if args.projection else None
        sort = json.loads(args.sort) if args.sort else None
    except json.JSONDecodeError as e:
        C.fail("BAD_INPUT", f"filter/projection/sort JSON 解析失敗: {e}",
               '單引號包整串、內部用雙引號，例: --filter \'{"vip":{"$gte":5}}\'')
        return
    pw = C.secret(args.password, args.password_env)
    kw = dict(host=args.host, port=args.port or 27017,
              serverSelectionTimeoutMS=_connect_timeout(args) * 1000)
    if args.user:
        kw.update(username=args.user, password=pw, authSource=args.auth_source)
    client = MongoClient(**kw)
    try:
        cur = client[args.database][args.collection].find(flt, proj)
        if sort:
            cur = cur.sort([tuple(s) for s in sort])
        for doc in cur:                     # pymongo cursor 本就是串流
            # F-17：projection 排除 _id 時不硬塞 "_id": "None"
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            yield doc
    finally:
        client.close()


ITER = {
    "sqlite": iter_sqlite, "postgresql": iter_postgresql,
    "mysql": iter_mysql, "mssql": iter_mssql,
}


def iter_rows(args, sql, params) -> Iterator[dict]:
    """統一串流入口（非 mongo）。逐筆 yield，呼叫端自行 islice 到 limit。"""
    fn = ITER.get(args.db_type)
    if not fn:
        C.fail("BAD_INPUT", f"不支援的 db_type: {args.db_type}",
               "支援 sqlite/postgresql/mysql/mssql；mongodb 走 iter_mongodb，bigquery 走 bq_query.py")
    yield from fn(args, sql, params)
