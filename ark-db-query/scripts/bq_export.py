#!/usr/bin/env python3
"""BigQuery 大結果集匯出 — 分頁串流寫檔，stdout 只回摘要 + 樣本，絕不塞爆 context。

與 bq_query.py 的分工：
  bq_query.py  → 互動分析（預設 LIMIT 50，結果進 stdout）
  bq_export.py → 全量落盤（無 LIMIT，逐頁寫 jsonl/csv，stdout 回 count + 檔案路徑 + 前 5 筆樣本）

用法:
  python bq_export.py --project my-proj --sql-file q.sql --out data/kpi.jsonl
  python bq_export.py --project my-proj --table analytics.daily_kpi --out data/full.csv --out-format csv
（--table 走 list_rows 全表匯出，零查詢費用；--sql 走查詢，仍受 max-bytes-billed 守門）
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
from bq_query import get_client, estimate_cost_usd, DEFAULT_MAX_BYTES  # noqa: E402

PAGE_SIZE = int(os.getenv("ARK_BQ_EXPORT_PAGE_SIZE", "5000"))
SAMPLE_ROWS = 5


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="BigQuery bulk export")
    ap.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    ap.add_argument("--sql", help="SQL 字串")
    ap.add_argument("--sql-file", help="SQL 檔路徑")
    ap.add_argument("--table", help="全表匯出 dataset.table（免查詢費）")
    ap.add_argument("--out", required=True, help="輸出檔路徑（.jsonl / .csv）")
    ap.add_argument("--out-format", choices=["jsonl", "csv"], default=None,
                    help="預設依 --out 副檔名判斷")
    ap.add_argument("--max-bytes-billed", type=int, default=DEFAULT_MAX_BYTES)
    ap.add_argument("--max-rows", type=int, default=0, help="0 = 不限")
    ap.add_argument("--location", default=os.getenv("ARK_BQ_LOCATION", None))
    ap.add_argument("--allow-write", action="store_true")
    return ap


def main() -> None:
    C.load_env()
    args = build_parser().parse_args()
    client = get_client(args.project, args.location)  # 內含 DRIVER_MISSING/憑證檢查
    from google.cloud import bigquery

    fmt = args.out_format or ("csv" if args.out.endswith(".csv") else "jsonl")
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    meta: dict = {"db_type": "bigquery", "mode": "export"}
    with C.Timer() as t:
        if args.table:
            if "." not in args.table:
                C.fail("BAD_INPUT", "--table 格式為 dataset.table", "")
            tbl = client.get_table(f"{args.project}.{args.table}")
            iterator = client.list_rows(tbl, page_size=PAGE_SIZE)
            meta.update(bytes_processed=0, estimated_cost_usd=0.0, source="table")
        else:
            sql = C.read_sql(args)
            C.guard_read_only(sql, args.allow_write)
            dry = client.query(sql, job_config=bigquery.QueryJobConfig(
                dry_run=True, use_query_cache=False))
            tb = dry.total_bytes_processed or 0
            if tb > args.max_bytes_billed:
                C.fail("GATE_BLOCKED",
                       f"將掃描 {tb:,} bytes，超過上限 {args.max_bytes_billed:,}",
                       "加 partition/日期過濾，或調高 --max-bytes-billed")
            job = client.query(sql, job_config=bigquery.QueryJobConfig(
                maximum_bytes_billed=args.max_bytes_billed))
            iterator = job.result(page_size=PAGE_SIZE)
            meta.update(bytes_processed=tb, estimated_cost_usd=estimate_cost_usd(tb),
                        job_id=job.job_id, source="query")

        count, sample, writer, fh = 0, [], None, None
        try:
            fh = out_path.open("w", encoding="utf-8", newline="")
            for row in iterator:
                d = dict(row)
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
        finally:
            if fh:
                fh.close()

    meta["elapsed_ms"] = t.elapsed_ms
    C.emit({"rows": sample, "count": count, "truncated": count > SAMPLE_ROWS,
            "out_file": str(out_path)}, meta)


if __name__ == "__main__":
    main()
