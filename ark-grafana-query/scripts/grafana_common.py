"""Grafana skill 共用模組 — 認證、HTTP、輸出契約、env 載入。"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT = 30
DEFAULT_STDOUT_ROWS = 50


# ─── env ────────────────────────────────────────────────────────────────────

def load_env() -> None:
    """載入 .env（如果存在），不覆蓋已設定的環境變數。"""
    for candidate in [Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"]:
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v
            break


# ─── 認證 ───────────────────────────────────────────────────────────────────

def get_grafana_config() -> dict[str, str]:
    """取得 Grafana 連線設定，回傳 {url, headers}。"""
    url = os.getenv("GRAFANA_URL", "").rstrip("/")
    if not url:
        fail("AUTH_FAILED", "未設定 GRAFANA_URL", "在 .env 設 GRAFANA_URL=http://host:3000")

    token = os.getenv("GRAFANA_TOKEN", "")
    user = os.getenv("GRAFANA_USER", "")
    password = os.getenv("GRAFANA_PASSWORD", "")

    headers: dict[str, str] = {"Accept": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif user and password:
        import base64
        cred = base64.b64encode(f"{user}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {cred}"
    else:
        fail("AUTH_FAILED", "未設定認證（需要 GRAFANA_TOKEN 或 GRAFANA_USER+GRAFANA_PASSWORD）",
             "在 .env 設 GRAFANA_TOKEN 或 GRAFANA_USER + GRAFANA_PASSWORD")

    return {"url": url, "headers": headers}


def grafana_get(path: str, params: dict | None = None, timeout: int = DEFAULT_TIMEOUT) -> Any:
    """GET Grafana API，回傳 parsed JSON。"""
    import requests

    cfg = get_grafana_config()
    full_url = f"{cfg['url']}{path}"

    try:
        resp = requests.get(full_url, headers=cfg["headers"], params=params, timeout=timeout)
    except requests.ConnectionError as e:
        fail("CONN_FAILED", f"連線失敗: {e}", f"確認 GRAFANA_URL ({cfg['url']}) 可達")
    except requests.Timeout:
        fail("CONN_FAILED", f"請求超時 ({timeout}s)", "加大 --timeout 或確認網路")

    if resp.status_code == 401:
        fail("AUTH_FAILED", "認證失敗 (401)", "確認 GRAFANA_TOKEN 或帳密正確")
    if resp.status_code == 403:
        fail("AUTH_FAILED", "權限不足 (403)", "確認 token/帳號有足夠權限")
    if resp.status_code == 404:
        fail("NOT_FOUND", f"資源不存在 (404): {path}", "確認 UID / Panel ID 正確")
    if resp.status_code >= 400:
        fail("QUERY_FAILED", f"HTTP {resp.status_code}: {resp.text[:200]}", "")

    return resp.json()


# ─── 輸出契約 ────────────────────────────────────────────────────────────────

class Timer:
    """簡單計時器。"""

    def __init__(self) -> None:
        self.start = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.elapsed_ms = round((time.perf_counter() - self.start) * 1000, 1)


def emit(data: dict, meta: dict) -> None:
    """輸出成功 JSON 到 stdout 並 exit 0。"""
    cfg = get_grafana_config()
    meta.setdefault("tool", "grafana")
    meta.setdefault("grafana_url", cfg["url"])
    print(json.dumps({"success": True, "data": data, "meta": meta}, ensure_ascii=False, default=str))
    sys.exit(0)


def fail(code: str, message: str, hint: str) -> None:
    """輸出失敗 JSON 到 stdout 並 exit 1。"""
    print(json.dumps({"success": False, "error": {"code": code, "message": message, "hint": hint}},
                     ensure_ascii=False))
    sys.exit(1)


def finalize_rows(rows: list[dict], args: Any, meta: dict) -> None:
    """統一處理 rows 輸出：截斷 + 落盤。"""
    max_stdout = getattr(args, "max_stdout_rows", DEFAULT_STDOUT_ROWS)
    out_file = getattr(args, "out", None)
    count = len(rows)
    truncated = count > max_stdout

    # 落盤
    if out_file:
        out_path = Path(out_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_format = getattr(args, "out_format", "json")
        if out_format == "jsonl":
            out_path.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows) + "\n",
                encoding="utf-8")
        else:
            out_path.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8")

    emit({"rows": rows[:max_stdout], "count": count,
          "truncated": truncated, "out_file": out_file}, meta)
