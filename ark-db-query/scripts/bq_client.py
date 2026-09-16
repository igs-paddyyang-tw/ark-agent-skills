"""BigQuery client 層 — 從 bq_query 抽出（ADR-001 L3 / ADR-002）。

集中處理：憑證檢查、dry-run、statement_type 判定（L3 伺服端守門）、
max_results 取筆數（不改寫 SQL，修 F-05/F-06）、逾時 cancel（修 F-07）、
named params（F-08）。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_common as C  # noqa: E402


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
        C.fail("CONN_FAILED", "未設定 GOOGLE_APPLICATION_CREDENTIALS",
               "在 .env 設服務帳號金鑰路徑；若用 ADC 請設 ARK_BQ_ADC_OK=1")
    return bigquery.Client(project=project, location=location)


def build_params(params_json: str | None, param_types: str | None):
    """named params：JSON dict → ScalarQueryParameter（型別由值推斷，可用 --param-types 覆寫）。"""
    if not params_json:
        return None
    from google.cloud import bigquery
    try:
        d = json.loads(params_json)
        if not isinstance(d, dict):
            raise ValueError
    except ValueError:
        C.fail("BAD_INPUT", "--params 必須是 JSON object（named @x）",
               '例: --params \'{"start":"2026-09-01"}\'')
        return None
    types = json.loads(param_types) if param_types else {}
    out = []
    for k, v in d.items():
        t = types.get(k) or _infer_type(v)
        out.append(bigquery.ScalarQueryParameter(k, t, v))
    return out


def _infer_type(v) -> str:
    if isinstance(v, bool):
        return "BOOL"
    if isinstance(v, int):
        return "INT64"
    if isinstance(v, float):
        return "FLOAT64"
    return "STRING"


def dry_run(client, sql, params):
    """回傳 (total_bytes, statement_type)。statement_type 供 L3 判定。"""
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    if params:
        cfg.query_parameters = params
    try:
        job = client.query(sql, job_config=cfg)
    except Exception as e:
        C.fail("QUERY_FAILED", f"dry-run 失敗（SQL 可能有誤）: {e}",
               "先用 bq_schema.py schema --table ds.tbl 核對欄位名")
    return (job.total_bytes_processed or 0), getattr(job, "statement_type", None)


def gate_l3(statement_type) -> None:
    """L3 伺服端守門：statement_type 非 SELECT 一律 GATE_BLOCKED。"""
    if statement_type is not None and statement_type != "SELECT":
        C.fail("GATE_BLOCKED",
               f"BQ 伺服端判定語句類型為 {statement_type}（非 SELECT，L3 攔截）",
               "只允許 SELECT 查詢；寫入請明示 --allow-write")


def execute(client, sql, params, *, max_bytes_billed, max_results, timeout):
    """執行查詢：不改寫 SQL，max_results 取筆數；逾時必 cancel（修 F-05/F-06/F-07）。"""
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(maximum_bytes_billed=max_bytes_billed)
    if params:
        cfg.query_parameters = params
    job = client.query(sql, job_config=cfg)
    try:
        result = job.result(timeout=timeout, max_results=max_results)
        rows = [dict(r) for r in result]
    except Exception as e:
        # 逾時或其他錯誤：先嘗試 cancel（修 F-07），再回報
        try:
            job.cancel()
        except Exception:
            pass
        etype = "TIMEOUT" if "timeout" in str(e).lower() else "QUERY_FAILED"
        code = etype
        C.fail(code, f"查詢{'逾時' if etype=='TIMEOUT' else '失敗'}（job 已嘗試 cancel）: {e}",
               "縮小掃描範圍或提高 --query-timeout" if etype == "TIMEOUT"
               else "先用 --dry-run 驗語法；權限查 gcloud auth application-default login")
    return rows, job
