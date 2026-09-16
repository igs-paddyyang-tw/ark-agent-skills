#!/usr/bin/env python3
"""非 BQ 資料庫大結果集匯出 — 串流寫檔，stdout 只回摘要 + 樣本（ADR-003 / F-09）。

與 db_query.py 的分工：
  db_query.py  → 互動分析（預設 LIMIT 50，結果進 stdout）
  db_export.py → 全量落盤（串流逐筆寫 jsonl/csv，stdout 回 count + 檔案路徑 + 前 5 筆樣本）

補齊 SKILL.md 決策樹「結果集大」分支對 pg/mysql/sqlite/mssql 的空缺。
契約與 bq_export.py 對齊。

用法:
  python db_export.py --db-type postgresql --host H --database D --user U \
      --password-env PG_PASS --sql-file q.sql --out data/out.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_common as C  # noqa: E402
import drivers as D  # noqa: E402

SAMPLE_ROWS = 5


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Non-BQ bulk export（串流）")
    ap.add_argument("--db-type", required=True,
                    choices=["sqlite", "postgresql", "mysql", "mssql", "mongodb"])
    ap.add_argument("--db-path")
    ap.add_argument("--host", default=os.getenv("ARK_DB_HOST", "localhost"))
    ap.add_argument("--port", type=int)
    ap.add_argument("--database", default=os.getenv("ARK_DB_NAME", ""))
    ap.add_argument("--user", default=os.getenv("ARK_DB_USER", ""))
    ap.add_argument("--password", help="不建議明文；優先用 --password-env")
    ap.add_argument("--password-env")
    ap.add_argument("--sql")
    ap.add_argument("--sql-file")
    ap.add_argument("--params")
    # mongo
    ap.add_argument("--collection")
    ap.add_argument("--filter", default="{}")
    ap.add_argument("--projection", default="")
    ap.add_argument("--sort", default="")
    ap.add_argument("--auth-source", default="admin")
    # 匯出
    ap.add_argument("--out", required=True, help="輸出檔路徑（.jsonl / .csv）")
    ap.add_argument("--out-format", choices=["jsonl", "csv"], default=None)
    ap.add_argument("--max-rows", type=int, default=0, help="0 = 不限")
    ap.add_argument("--allow-write", action="store_true")
    ap.add_argument("--connect-timeout", type=int, default=None)
    ap.add_argument("--query-timeout", type=int, default=None)
    ap.add_argument("--timeout", type=int, default=60)
    return ap


def _params(args):
    if not args.params:
        return []
    try:
        p = json.loads(args.params)
        if not isinstance(p, list):
            raise ValueError
        return p
    except ValueError:
        C.fail("BAD_INPUT", "--params 必須是 JSON array", "例: --params '[123]'")
        return []


def main() -> None:
    C.load_env()
    args = build_parser().parse_args()
    if getattr(args, "password", None):
        print("⚠️ --password 明文已 deprecated，請改用 --password-env", file=sys.stderr)

    fmt = args.out_format or ("csv" if args.out.endswith(".csv") else "jsonl")
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.db_type == "mongodb":
        row_iter = D.iter_mongodb(args)
    else:
        sql = C.read_sql(args)
        C.guard_read_only(sql, args.allow_write)   # L1
        row_iter = D.iter_rows(args, sql, _params(args))

    count, sample, writer, fh = 0, [], None, None
    with C.Timer() as t:
        try:
            fh = out_path.open("w", encoding="utf-8", newline="")
            for d in row_iter:
                if count < SAMPLE_ROWS:
                    sample.append(d)
                if fmt == "jsonl":
                    fh.write(json.dumps(d, ensure_ascii=False, cls=C._Encoder) + "\n")
                else:
                    if writer is None:
                        writer = csv.DictWriter(fh, fieldnames=list(d.keys()))
                        writer.writeheader()
                    writer.writerow({k: C._cell(v) for k, v in d.items()})
                count += 1
                if args.max_rows and count >= args.max_rows:
                    break
        except SystemExit:
            raise
        except Exception as e:
            msg = str(e).lower()
            code = ("TIMEOUT" if "timeout" in msg
                    else "CONN_FAILED" if "connect" in msg else "QUERY_FAILED")
            C.fail(code, f"{args.db_type} 匯出失敗: {e}", "先跑 db_health.py 檢查連線")
            return
        finally:
            if fh:
                fh.close()

    C.emit({"rows": sample, "count": count, "truncated": count > SAMPLE_ROWS,
            "truncated_by": "rows" if count > SAMPLE_ROWS else None,
            "out_file": str(out_path)},
           {"db_type": args.db_type, "mode": "export", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
