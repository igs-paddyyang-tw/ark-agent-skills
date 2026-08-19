#!/usr/bin/env python3
"""BigQuery 中繼資料 CLI — 取代 BQ MCP 的 list_datasets / list_tables / get_table_schema / preview。

四個子指令全部走 metadata API 或 list_rows，**零查詢費用**：
  datasets                          列出所有 dataset
  tables   --dataset DS             列出 dataset 下所有 table（含筆數/大小/分區）
  schema   --table DS.TBL           取 table 欄位結構
  preview  --table DS.TBL [--limit] 免費預覽資料（tabledata.list，不是 SELECT *）

用法:
  python bq_schema.py datasets --project my-proj
  python bq_schema.py schema --project my-proj --table analytics.daily_kpi
認證: GOOGLE_APPLICATION_CREDENTIALS
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_common as C  # noqa: E402
from bq_query import get_client  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="BigQuery metadata (MCP replacement, free)")
    ap.add_argument("command", choices=["datasets", "tables", "schema", "preview"])
    ap.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    ap.add_argument("--dataset", help="tables 指令用")
    ap.add_argument("--table", help="schema/preview 指令用，格式 dataset.table")
    ap.add_argument("--limit", type=int, default=10, help="preview 筆數")
    ap.add_argument("--location", default=os.getenv("ARK_BQ_LOCATION", None))
    ap.add_argument("--out", help="結果落盤路徑")
    ap.add_argument("--out-format", choices=["jsonl", "json", "csv"], default="json")
    ap.add_argument("--max-stdout-rows", type=int, default=100)
    return ap


def _fields_to_dicts(fields, prefix: str = "") -> list[dict]:
    out = []
    for f in fields:
        out.append({"name": prefix + f.name, "type": f.field_type,
                    "mode": f.mode, "description": f.description or ""})
        if f.field_type == "RECORD":
            out.extend(_fields_to_dicts(f.fields, prefix + f.name + "."))
    return out


def main() -> None:
    C.load_env()
    args = build_parser().parse_args()
    client = get_client(args.project, args.location)

    with C.Timer() as t:
        if args.command == "datasets":
            rows = [{"dataset_id": d.dataset_id} for d in client.list_datasets()]

        elif args.command == "tables":
            if not args.dataset:
                C.fail("BAD_INPUT", "tables 需要 --dataset", "")
            rows = []
            for item in client.list_tables(args.dataset):
                tbl = client.get_table(item.reference)
                rows.append({
                    "table_id": item.table_id,
                    "type": item.table_type,
                    "num_rows": tbl.num_rows,
                    "size_mb": round((tbl.num_bytes or 0) / 1048576, 2),
                    "partitioned_on": (tbl.time_partitioning.field
                                       if tbl.time_partitioning else None),
                    "clustered_on": list(tbl.clustering_fields or []) or None,
                })

        elif args.command == "schema":
            if not args.table or "." not in args.table:
                C.fail("BAD_INPUT", "schema 需要 --table dataset.table", "")
            tbl = client.get_table(f"{args.project}.{args.table}")
            rows = _fields_to_dicts(tbl.schema)

        else:  # preview — tabledata.list，免費且不掃描
            if not args.table or "." not in args.table:
                C.fail("BAD_INPUT", "preview 需要 --table dataset.table", "")
            tbl = client.get_table(f"{args.project}.{args.table}")
            rows = [dict(r) for r in client.list_rows(tbl, max_results=args.limit)]

    C.finalize_rows(rows, args,
                    {"db_type": "bigquery", "command": args.command,
                     "elapsed_ms": t.elapsed_ms, "bytes_processed": 0,
                     "estimated_cost_usd": 0.0})


if __name__ == "__main__":
    main()
