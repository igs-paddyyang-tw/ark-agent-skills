#!/usr/bin/env python3
"""連線健檢 — agent 遇到 CONN_FAILED 時的第一步診斷。

用法:
  python db_health.py --db-type sqlite --db-path ./data/app.db
  python db_health.py --db-type bigquery --project my-proj
  python db_health.py --db-type postgresql --host H --database D --user U --password-env PG_PASS

回傳: {"success": true, "data": {"rows": [{"check": ..., "ok": ..., "detail": ...}], ...}}
逐項檢查: 驅動已安裝 → 憑證環境變數存在 → 連線可建立 → 最小查詢可執行
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_common as C  # noqa: E402

DRIVERS = {
    "sqlite": ("sqlite3", "內建"),
    "postgresql": ("psycopg", "psycopg[binary]"),
    "mysql": ("pymysql", "pymysql"),
    "mssql": ("pymssql", "pymssql"),
    "mongodb": ("pymongo", "pymongo"),
    "bigquery": ("google.cloud.bigquery", "google-cloud-bigquery"),
}


def check(name: str, fn) -> dict:
    try:
        detail = fn()
        return {"check": name, "ok": True, "detail": detail or ""}
    except Exception as e:
        return {"check": name, "ok": False, "detail": str(e)}


def main() -> None:
    C.load_env()
    ap = argparse.ArgumentParser(description="DB connectivity health check")
    ap.add_argument("--db-type", required=True, choices=list(DRIVERS))
    ap.add_argument("--db-path")
    ap.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    ap.add_argument("--host", default=os.getenv("ARK_DB_HOST", "localhost"))
    ap.add_argument("--port", type=int)
    ap.add_argument("--database", default=os.getenv("ARK_DB_NAME", ""))
    ap.add_argument("--user", default=os.getenv("ARK_DB_USER", ""))
    ap.add_argument("--password-env")
    ap.add_argument("--timeout", type=int, default=10)
    args = ap.parse_args()

    results = []
    mod, pip_name = DRIVERS[args.db_type]

    def _import():
        parts = mod.split(".")
        m = __import__(mod)
        return f"{pip_name} 可用"
    results.append(check("driver_installed", _import))
    if not results[-1]["ok"]:
        results[-1]["detail"] += f"（pip install {pip_name} --break-system-packages）"

    if args.db_type == "bigquery":
        results.append(check("credentials_env", lambda: (
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            else (_ for _ in ()).throw(KeyError("GOOGLE_APPLICATION_CREDENTIALS 未設定"))
        )))

    if all(r["ok"] for r in results):
        def _connect_and_ping():
            with C.Timer() as t:
                if args.db_type == "sqlite":
                    import sqlite3
                    conn = sqlite3.connect(args.db_path or ":memory:", timeout=args.timeout)
                    conn.execute("SELECT 1").fetchone()
                    conn.close()
                elif args.db_type == "bigquery":
                    from google.cloud import bigquery
                    client = bigquery.Client(project=args.project)
                    list(client.list_datasets(max_results=1))
                elif args.db_type == "mongodb":
                    from pymongo import MongoClient
                    kw = dict(host=args.host, port=args.port or 27017,
                              serverSelectionTimeoutMS=args.timeout * 1000)
                    pw = C.secret(None, args.password_env)
                    if args.user:
                        kw.update(username=args.user, password=pw)
                    MongoClient(**kw).admin.command("ping")
                else:
                    import json as _j  # noqa
                    sys_argv_bak = sys.argv
                    # 重用 db_query 的驅動函式跑 SELECT 1
                    import db_query as DQ
                    class A:  # 最小參數物件
                        pass
                    a = A()
                    for k in ("host", "port", "database", "user",
                              "password_env", "timeout", "db_path"):
                        setattr(a, k, getattr(args, k, None))
                    a.password, a.limit, a.allow_write = None, 1, False
                    fn = {"postgresql": DQ.q_postgresql, "mysql": DQ.q_mysql,
                          "mssql": DQ.q_mssql}[args.db_type]
                    fn(a, "SELECT 1 AS ok", [])
                    sys.argv = sys_argv_bak
            return f"連線 + 最小查詢 OK（{t.elapsed_ms} ms）"
        results.append(check("connect_and_ping", _connect_and_ping))

    ok = all(r["ok"] for r in results)
    C.emit({"rows": results, "count": len(results),
            "truncated": False, "out_file": None},
           {"db_type": args.db_type, "healthy": ok})


if __name__ == "__main__":
    main()
