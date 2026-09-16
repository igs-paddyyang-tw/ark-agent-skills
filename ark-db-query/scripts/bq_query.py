#!/usr/bin/env python3
"""BigQuery 查詢 CLI — 取代 BQ MCP 的 execute_query。

特性（皆為 deterministic 守門，非 LLM 判斷）:
  1. --dry-run          只估算不執行，回傳 bytes_processed 與估算成本
  2. maximum_bytes_billed 強制上限（預設 1 GiB，環境變數 ARK_BQ_MAX_BYTES_BILLED 可調），
     超限 BigQuery 端直接拒絕，不產生費用
  3. read-only 預設      DML/DDL 需 --allow-write
  4. stdout 截斷 + --out 全量落盤，保護 agent context

用法:
  python bq_query.py --project my-proj --sql "SELECT ..." [--dry-run]
  python bq_query.py --project my-proj --sql-file q.sql --out result.jsonl
認證: GOOGLE_APPLICATION_CREDENTIALS 環境變數（服務帳號金鑰路徑）
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_common as C  # noqa: E402

PRICE_PER_TIB = float(os.getenv("ARK_BQ_PRICE_PER_TIB_USD", "6.25"))
DEFAULT_MAX_BYTES = int(os.getenv("ARK_BQ_MAX_BYTES_BILLED", str(1 << 30)))  # 1 GiB


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="BigQuery query (MCP replacement)")
    ap.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
                    help="GCP project id（或設 GOOGLE_CLOUD_PROJECT）")
    ap.add_argument("--sql", help="SQL 字串")
    ap.add_argument("--sql-file", help="SQL 檔路徑（建議，避開 shell 轉義）")
    ap.add_argument("--location", default=os.getenv("ARK_BQ_LOCATION", None))
    ap.add_argument("--dry-run", action="store_true", help="只估算 bytes / 成本，不執行")
    ap.add_argument("--max-bytes-billed", type=int, default=DEFAULT_MAX_BYTES,
                    help=f"計費位元組上限（預設 {DEFAULT_MAX_BYTES}）")
    ap.add_argument("--limit", type=int, default=C.DEFAULT_LIMIT, help="回傳筆數上限")
    ap.add_argument("--no-limit", action="store_true", help="取消 limit（配合 --out）")
    ap.add_argument("--allow-write", action="store_true", help="放行 DML/DDL")
    ap.add_argument("--out", help="全量結果落盤路徑")
    ap.add_argument("--out-format", choices=["jsonl", "json", "csv"], default="jsonl")
    ap.add_argument("--max-stdout-rows", type=int, default=C.DEFAULT_STDOUT_ROWS)
    ap.add_argument("--timeout", type=int, default=int(os.getenv("ARK_BQ_TIMEOUT_S", "120")),
                    help="（相容別名）等同 --query-timeout")
    ap.add_argument("--query-timeout", type=int, default=None,
                    help="查詢執行逾時秒數；逾時後 job 會被 cancel")
    ap.add_argument("--params", help='named params JSON object，如 \'{"start":"2026-09-01"}\'（對應 @start）')
    ap.add_argument("--param-types", help='覆寫 param 型別 JSON，如 \'{"start":"DATE"}\'')
    return ap


def get_client(project: str, location: str | None):
    try:
        from google.cloud import bigquery  # noqa: F401
    except ImportError:
        C.fail("DRIVER_MISSING", "缺 google-cloud-bigquery",
               "pip install google-cloud-bigquery --break-system-packages")
    from google.cloud import bigquery
    if not project:
        C.fail("BAD_INPUT", "缺 project id", "--project 或設 GOOGLE_CLOUD_PROJECT")
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and not os.getenv("ARK_BQ_ADC_OK"):
        # 允許 ADC / metadata server 場景以 ARK_BQ_ADC_OK=1 跳過此檢查
        C.fail("CONN_FAILED", "未設定 GOOGLE_APPLICATION_CREDENTIALS",
               "在 .env 設服務帳號金鑰路徑；若用 ADC 請設 ARK_BQ_ADC_OK=1")
    return bigquery.Client(project=project, location=location)


def estimate_cost_usd(total_bytes: int) -> float:
    return round(total_bytes / (1 << 40) * PRICE_PER_TIB, 6)


def main() -> None:
    C.load_env()
    args = build_parser().parse_args()
    sql = C.read_sql(args)
    C.guard_read_only(sql, args.allow_write)  # L1 allowlist

    import bq_client as BC  # 同目錄
    client = get_client(args.project, args.location)
    params = BC.build_params(getattr(args, "params", None), getattr(args, "param_types", None))

    # --- 第一步永遠 dry-run：拿 bytes 估算 + statement_type（L3） ---
    with C.Timer() as t_dry:
        total_bytes, stmt_type = BC.dry_run(client, sql, params)
    if not args.allow_write:
        BC.gate_l3(stmt_type)  # L3 伺服端守門
    est = {"bytes_processed": total_bytes,
           "estimated_cost_usd": estimate_cost_usd(total_bytes),
           "price_per_tib_usd": PRICE_PER_TIB}

    if args.dry_run:
        C.emit({"rows": [], "count": 0, "truncated": False, "out_file": None},
               {"db_type": "bigquery", "mode": "dry_run",
                "elapsed_ms": t_dry.elapsed_ms, **est,
                "statement_type": stmt_type,
                "would_exceed_cap": total_bytes > args.max_bytes_billed,
                "max_bytes_billed": args.max_bytes_billed})

    if total_bytes > args.max_bytes_billed:
        C.fail("GATE_BLOCKED",
               f"查詢將掃描 {total_bytes:,} bytes，超過上限 {args.max_bytes_billed:,}",
               "縮小掃描範圍（partition/日期過濾/指定欄位），或明確調高 --max-bytes-billed")

    # --- 真正執行：不改寫 SQL，max_results 取筆數（修 F-05/F-06），逾時 cancel（修 F-07） ---
    max_results = None if args.no_limit else args.limit
    query_timeout = getattr(args, "query_timeout", None) or args.timeout
    with C.Timer() as t:
        rows, job = BC.execute(client, sql, params,
                               max_bytes_billed=args.max_bytes_billed,
                               max_results=max_results, timeout=query_timeout)
    meta = {"db_type": "bigquery", "elapsed_ms": t.elapsed_ms,
            "job_id": job.job_id, "cache_hit": bool(job.cache_hit),
            "bytes_processed": job.total_bytes_processed, **est}
    C.finalize_rows(rows, args, meta)


if __name__ == "__main__":
    main()
