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


CONTRACT_VERSION = "1.1"

# exit code 分流（ADR-005/AC-16）—— 舊呼叫方若只判 != 0 不受影響
EXIT_CODES = {
    "BAD_INPUT": 2, "GATE_BLOCKED": 3, "BUDGET_EXCEEDED": 4,
    "CONN_FAILED": 5, "QUERY_FAILED": 6, "TIMEOUT": 7, "DRIVER_MISSING": 8,
}


def _skill_version() -> str:
    try:
        from __version__ import SKILL_VERSION
        return SKILL_VERSION
    except Exception:
        return "unknown"


def emit(data: dict, meta: dict) -> None:
    meta = {"skill_version": _skill_version(), **meta}
    print(json.dumps({"success": True, "contract": CONTRACT_VERSION,
                      "data": data, "meta": meta},
                     ensure_ascii=False, cls=_Encoder))
    sys.exit(0)


def fail(code: str, message: str, hint: str = "") -> None:
    print(json.dumps({"success": False, "contract": CONTRACT_VERSION,
                      "error": {"code": code, "message": message, "hint": hint}},
                     ensure_ascii=False))
    sys.exit(EXIT_CODES.get(code, 1))


def finalize_rows(rows: list[dict], args, meta: dict) -> None:
    """統一收尾：全量落盤（--out），stdout 回截斷樣本（筆數 + 位元組雙上限），保護 context。"""
    count = len(rows)
    out_file = getattr(args, "out", None)
    fmt = getattr(args, "out_format", None) or "jsonl"
    if out_file:
        write_rows(rows, out_file, fmt)
    max_stdout = getattr(args, "max_stdout_rows", None) or DEFAULT_STDOUT_ROWS
    sample = rows[:max_stdout]
    truncated_by = "rows" if count > max_stdout else None
    # bytes 截斷（AC-18）：單 cell > 2 KiB 截短，整體 > max_stdout_bytes 逐筆縮減
    max_bytes = getattr(args, "max_stdout_bytes", None) or int(
        os.getenv("ARK_DB_STDOUT_BYTES", str(64 * 1024)))
    sample, bytes_hit = _cap_bytes(sample, max_bytes)
    if bytes_hit:
        truncated_by = "bytes"
    emit(
        {"rows": sample, "count": count,
         "truncated": truncated_by is not None,
         "truncated_by": truncated_by, "out_file": out_file},
        meta,
    )


_CELL_MAX = 2 * 1024


def _cap_bytes(rows: list[dict], max_bytes: int):
    """單 cell > 2 KiB 截短；整體序列化 > max_bytes 時逐筆丟棄尾端。回 (rows, hit)。"""
    hit = False
    capped = []
    for r in rows:
        nr = {}
        for k, v in r.items():
            s = v if isinstance(v, str) else None
            if s is not None and len(s.encode("utf-8")) > _CELL_MAX:
                nr[k] = s[:_CELL_MAX] + f"…[truncated {len(s)} chars]"
                hit = True
            else:
                nr[k] = v
        capped.append(nr)
    # 整體位元組上限：逐筆丟棄尾端直到符合
    while capped and len(json.dumps(capped, ensure_ascii=False, cls=_Encoder).encode("utf-8")) > max_bytes:
        capped.pop()
        hit = True
    return capped, hit


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
    """Deterministic 守門（ADR-001 L1）：allowlist + 註解剝除，寫入需 --allow-write。

    v3.0 改為呼叫 gate.py 的 allowlist 機制（取代 v2.0 只錨語句開頭的 denylist 正則），
    封閉 F-01（前置註解繞過）/ F-02（巢狀/腳本寫入）。
    """
    import gate  # 同目錄
    allowed, layer, reason, token = gate.check(sql, allow_write)
    if not allowed:
        fail("GATE_BLOCKED",
             f"read-only 守門攔截（{layer}）: {reason}",
             "確認為刻意寫入後加 --allow-write 重跑；或用 --gate-explain 看細節")


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.elapsed_ms = round((time.perf_counter() - self.t0) * 1000, 1)
