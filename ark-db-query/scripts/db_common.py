"""ark-db-query 共用基礎：輸出契約、.env 載入、SQL 輸入、結果落盤與 stdout 截斷。

所有腳本共用的輸出契約（stdout 永遠是單一 JSON object）：

成功:
{
  "success": true,
  "data": {"rows": [...], "count": N, "truncated": bool, "out_file": "path|null"},
  "meta": {"db_type": "...", "elapsed_ms": N, ...}
}

失敗（exit code 1）:
{
  "success": false,
  "error": {"code": "DRIVER_MISSING|CONN_FAILED|QUERY_FAILED|GATE_BLOCKED|BAD_INPUT",
            "message": "...", "hint": "給 agent 的下一步建議"}
}
"""
from __future__ import annotations

import csv
import datetime as _dt
import decimal
import json
import os
import pathlib
import re
import sys
import time

DEFAULT_STDOUT_ROWS = int(os.getenv("ARK_DB_STDOUT_ROWS", "20"))
DEFAULT_LIMIT = int(os.getenv("ARK_DB_DEFAULT_LIMIT", "50"))

_WRITE_RE = re.compile(
    r"^\s*(insert|update|delete|merge|drop|create|alter|truncate|grant|revoke|replace)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------- env / auth
def load_env(path: str = ".env") -> None:
    """輕量 .env 載入（不依賴 python-dotenv）。已存在的環境變數不覆寫。"""
    p = pathlib.Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def secret(args_value: str | None, env_name: str | None, default: str = "") -> str:
    """取憑證：CLI 明文值優先（不建議），否則讀 --xxx-env 指到的環境變數。"""
    if args_value:
        return args_value
    if env_name:
        return os.getenv(env_name, default)
    return default


# ---------------------------------------------------------------- output
class _Encoder(json.JSONEncoder):
    def default(self, o):  # noqa: D102
        if isinstance(o, (_dt.datetime, _dt.date, _dt.time)):
            return o.isoformat()
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, bytes):
            return o.decode("utf-8", errors="replace")
        try:  # bson.ObjectId 等
            return str(o)
        except Exception:  # pragma: no cover
            return repr(o)


def emit(data: dict, meta: dict) -> None:
    print(json.dumps({"success": True, "data": data, "meta": meta},
                     ensure_ascii=False, cls=_Encoder))
    sys.exit(0)


def fail(code: str, message: str, hint: str = "") -> None:
    print(json.dumps({"success": False,
                      "error": {"code": code, "message": message, "hint": hint}},
                     ensure_ascii=False))
    sys.exit(1)


def finalize_rows(rows: list[dict], args, meta: dict) -> None:
    """統一收尾：全量落盤（--out），stdout 只回截斷樣本，保護 agent context window。"""
    count = len(rows)
    out_file = getattr(args, "out", None)
    fmt = getattr(args, "out_format", None) or "jsonl"
    if out_file:
        write_rows(rows, out_file, fmt)
    max_stdout = getattr(args, "max_stdout_rows", None) or DEFAULT_STDOUT_ROWS
    truncated = count > max_stdout
    emit(
        {"rows": rows[:max_stdout], "count": count,
         "truncated": truncated, "out_file": out_file},
        meta,
    )


def write_rows(rows: list[dict], path: str, fmt: str = "jsonl") -> None:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "jsonl":
        with p.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, cls=_Encoder) + "\n")
    elif fmt == "json":
        p.write_text(json.dumps(rows, ensure_ascii=False, cls=_Encoder), encoding="utf-8")
    elif fmt == "csv":
        keys: list[str] = []
        for r in rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow({k: _cell(r.get(k)) for k in keys})
    else:
        fail("BAD_INPUT", f"不支援的輸出格式: {fmt}", "使用 jsonl / json / csv")


def _cell(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, cls=_Encoder)
    return v


# ---------------------------------------------------------------- SQL input
def read_sql(args) -> str:
    """SQL 輸入三通道：--sql、--sql-file、stdin。建議 agent 用 --sql-file 避開 shell 轉義。"""
    sql = getattr(args, "sql", None)
    sql_file = getattr(args, "sql_file", None)
    if sql and sql_file:
        fail("BAD_INPUT", "--sql 與 --sql-file 只能擇一", "")
    if sql_file:
        p = pathlib.Path(sql_file)
        if not p.exists():
            fail("BAD_INPUT", f"SQL 檔不存在: {sql_file}", "")
        return p.read_text(encoding="utf-8").strip()
    if sql:
        return sql.strip()
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            return piped
    fail("BAD_INPUT", "缺少 SQL", "用 --sql、--sql-file 或 stdin 傳入")
    return ""  # unreachable


def guard_read_only(sql: str, allow_write: bool) -> None:
    """Deterministic 守門：預設只放行讀查詢，寫入需明示 --allow-write。"""
    if allow_write:
        return
    for stmt in filter(None, (s.strip() for s in sql.split(";"))):
        if _WRITE_RE.match(stmt):
            fail("GATE_BLOCKED",
                 f"偵測到寫入語句（預設 read-only）: {stmt[:60]}...",
                 "確認為刻意寫入後加 --allow-write 重跑")


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.elapsed_ms = round((time.perf_counter() - self.t0) * 1000, 1)
