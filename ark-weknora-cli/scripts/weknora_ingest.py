#!/usr/bin/env python3
"""weknora_ingest.py — WeKnora 知識寫入 / 更新客戶端（REST API 封裝）。

與 weknora_sql_query.py（查詢/口徑）分離：本腳本專責「把資料放上 WeKnora」與
「更新既有知識」，直接打 WeKnora 的 knowledge-bases / knowledge REST endpoint。
stdlib + httpx，輸出統一 JSON envelope（對齊 scripts/_common.py 契約），UTF-8。

本腳本永不執行 BigQuery（D-1 / D-7），也不提供「清空知識庫 / 批次刪除」等破壞性
操作——那類 owner-only 高風險動作請人工直接呼叫 API，避免腳本誤觸。

子指令：
  kb-list                                   列出知識庫（拿 kb_id）
  kb-create   --name <n> [--desc ...]        建立知識庫
  add-manual  --kb <id> --title <t> --content <@file|-|字面> [--tag ...] [--status published]
                                            新增手工 Markdown 知識（口徑首選）
  add-file    --kb <id> --file <path> [--tag ...] [--multimodel] [--file-name ...]
                                            上傳檔案建立知識
  add-url     --kb <id> --url <u> [--title ...] [--tag ...] [--multimodel]
                                            從 URL 建立知識（網頁抓取 / 遠端檔案）
  update-manual --id <kid> [--title ...] [--content <@file|-|字面>]
                                            更新手工 Markdown 知識內容
  update-meta   --id <kid> [--title ...] [--desc ...]
                                            更新知識標題 / 描述（未傳欄位不變）
  reparse     --id <kid>                     重新解析知識（配置變更 / 失敗重試）
  status      --id <kid>                     取知識詳情（含 parse_status）
  wait        --id <kid> [--timeout 300] [--interval 3]
                                            輪詢直到 parse_status 到終態
  search      --keyword <k> [--file-types txt,pdf] [--limit 20]
                                            跨知識庫搜尋，驗證新知識可檢索

環境變數：
  WEKNORA_API_URL   WeKnora REST base（預設 http://192.168.5.120:8080/api/v1）
  WEKNORA_API_KEY   API Key（必填；於 .env 設定）

Exit code：成功 0；失敗 1（envelope 內 error.code 承載細分原因）。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

# ── 輸出一律 UTF-8 ────────────────────────────────────────────────────────
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

# ── 載入專案根 .env（IDE 直接跑需要；服務環境由 systemd 注入，override=False 無害）──
try:
    from dotenv import load_dotenv

    for _p in Path(__file__).resolve().parents:
        _env = _p / ".env"
        if _env.exists():
            load_dotenv(_env, override=False)
            break
except Exception:  # noqa: BLE001
    pass


# ── JSON envelope（skill 自足，對齊 scripts/_common.py 契約，不依賴專案根 import）──
def emit_success(data: dict, meta: dict | None = None) -> None:
    print(json.dumps({"success": True, "data": data, "meta": meta or {}}, ensure_ascii=False))
    sys.exit(0)


def emit_error(code: str, message: str, hint: str = "") -> None:
    print(json.dumps(
        {"success": False, "error": {"code": code, "message": message, "hint": hint}},
        ensure_ascii=False))
    sys.exit(1)


def read_input_text(value: str) -> str:
    """讀取文字輸入：@file 讀檔、- 讀 stdin、其餘視為字面值。"""
    if value == "-":
        return sys.stdin.read()
    if value.startswith("@"):
        return Path(value[1:]).read_text(encoding="utf-8")
    return value


def timer() -> float:
    return time.monotonic()


def elapsed_ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)

_DEFAULT_API_URL = "http://192.168.5.120:8080/api/v1"
_TIMEOUT_SEC = 60.0
# parse_status 終態：到達其一即停止輪詢
_TERMINAL = {"completed", "failed", "cancelled"}


def _api_url() -> str:
    return os.getenv("WEKNORA_API_URL", _DEFAULT_API_URL).rstrip("/")


def _resolve_kb(kb_arg: str) -> str:
    """--kb 未帶時回退到 WEKNORA_KB_ID；都沒有則報錯。"""
    kb = kb_arg or os.getenv("WEKNORA_KB_ID", "")
    if not kb:
        emit_error("BAD_INPUT", "未指定知識庫 ID",
                   "帶 --kb <id>，或於 .env 設定 WEKNORA_KB_ID")
    return kb


def _headers() -> dict | None:
    # 知識庫讀寫需 editor scope，優先用 WEKNORA_KB_API_KEY；未設才回退唯讀 key
    key = os.getenv("WEKNORA_KB_API_KEY", "") or os.getenv("WEKNORA_API_KEY", "")
    if not key:
        return None
    return {"X-API-Key": key}


def _json_headers() -> dict:
    h = _headers() or {}
    h["Content-Type"] = "application/json"
    return h


def _request(method: str, path: str, *, json_body=None, data=None, files=None,
             params=None, headers=None, timeout: float = _TIMEOUT_SEC) -> dict:
    """打一次 WeKnora REST，回傳解析後的 JSON dict；HTTP/連線錯誤 raise RuntimeError。"""
    url = f"{_api_url()}{path}"
    try:
        resp = httpx.request(
            method, url, headers=headers, json=json_body, data=data,
            files=files, params=params, timeout=timeout,
        )
    except httpx.ConnectError as e:
        raise RuntimeError(f"無法連線 WeKnora（{e}）") from e
    except httpx.TimeoutException as e:
        raise RuntimeError(f"WeKnora 逾時（>{timeout:.0f}s）") from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"HTTP 錯誤：{e}") from e

    if resp.status_code == 409:
        raise RuntimeError("知識已存在（檔案去重 409）")
    if resp.status_code >= 400:
        raise RuntimeError(f"WeKnora 回應 {resp.status_code}：{resp.text[:300]}")
    try:
        return resp.json()
    except ValueError as e:
        raise RuntimeError(f"回應非 JSON：{resp.text[:300]}") from e


# ── 子指令實作 ────────────────────────────────────────────────────────────

def cmd_kb_list(args) -> None:
    t0 = timer()
    body = _request("GET", "/knowledge-bases", headers=_headers())
    kbs = body.get("data") or []
    items = [{"id": k.get("id"), "name": k.get("name"), "description": k.get("description", "")}
             for k in kbs] if isinstance(kbs, list) else kbs
    emit_success({"count": len(items) if isinstance(items, list) else 0, "knowledge_bases": items},
                 {"elapsed_ms": elapsed_ms(t0)})


def cmd_kb_create(args) -> None:
    t0 = timer()
    payload = {"name": args.name}
    if args.desc:
        payload["description"] = args.desc
    body = _request("POST", "/knowledge-bases", json_body=payload, headers=_json_headers())
    emit_success({"knowledge_base": body.get("data") or body}, {"elapsed_ms": elapsed_ms(t0)})


def cmd_add_manual(args) -> None:
    t0 = timer()
    kb = _resolve_kb(args.kb)
    content = read_input_text(args.content)
    payload = {"title": args.title, "content": content, "status": args.status}
    if args.tag:
        payload["tag_id"] = args.tag
    body = _request("POST", f"/knowledge-bases/{kb}/knowledge/manual",
                    json_body=payload, headers=_json_headers())
    data = body.get("data") or {}
    emit_success(
        {"knowledge_id": data.get("id"), "parse_status": data.get("parse_status"),
         "type": data.get("type"), "knowledge": data},
        {"elapsed_ms": elapsed_ms(t0), "next": "用 wait --id <knowledge_id> 輪詢到 completed"},
    )


def cmd_add_file(args) -> None:
    t0 = timer()
    kb = _resolve_kb(args.kb)
    fp = Path(args.file)
    if not fp.exists():
        emit_error("BAD_INPUT", f"檔案不存在：{args.file}", "確認路徑")
    form: dict = {}
    if args.tag:
        form["tag_id"] = args.tag
    if args.multimodel:
        form["enable_multimodel"] = "true"
    if args.file_name:
        form["fileName"] = args.file_name
    try:
        with fp.open("rb") as fh:
            files = {"file": (fp.name, fh)}
            body = _request("POST", f"/knowledge-bases/{kb}/knowledge/file",
                            data=form or None, files=files, headers=_headers())
    except RuntimeError:
        raise
    data = body.get("data") or {}
    emit_success(
        {"knowledge_id": data.get("id"), "parse_status": data.get("parse_status"),
         "file_name": data.get("file_name"), "knowledge": data},
        {"elapsed_ms": elapsed_ms(t0), "next": "用 wait --id <knowledge_id> 輪詢到 completed"},
    )


def cmd_add_url(args) -> None:
    t0 = timer()
    kb = _resolve_kb(args.kb)
    payload: dict = {"url": args.url}
    if args.title:
        payload["title"] = args.title
    if args.tag:
        payload["tag_id"] = args.tag
    if args.multimodel:
        payload["enable_multimodel"] = True
    if args.file_name:
        payload["file_name"] = args.file_name
    if args.file_type:
        payload["file_type"] = args.file_type
    body = _request("POST", f"/knowledge-bases/{kb}/knowledge/url",
                    json_body=payload, headers=_json_headers())
    data = body.get("data") or {}
    emit_success(
        {"knowledge_id": data.get("id"), "parse_status": data.get("parse_status"),
         "source": data.get("source"), "knowledge": data},
        {"elapsed_ms": elapsed_ms(t0), "next": "用 wait --id <knowledge_id> 輪詢到 completed"},
    )


def cmd_update_manual(args) -> None:
    t0 = timer()
    payload: dict = {}
    if args.title is not None:
        payload["title"] = args.title
    if args.content is not None:
        payload["content"] = read_input_text(args.content)
    if not payload:
        emit_error("BAD_INPUT", "update-manual 需至少一個 --title / --content", "")
    body = _request("PUT", f"/knowledge/manual/{args.id}",
                    json_body=payload, headers=_json_headers())
    data = body.get("data") or {}
    emit_success(
        {"knowledge_id": data.get("id") or args.id, "parse_status": data.get("parse_status"),
         "knowledge": data},
        {"elapsed_ms": elapsed_ms(t0), "next": "改內容會重新解析，用 wait 輪詢到 completed"},
    )


def cmd_update_meta(args) -> None:
    t0 = timer()
    payload: dict = {}
    if args.title is not None:
        payload["title"] = args.title
    if args.desc is not None:
        payload["description"] = args.desc
    if not payload:
        emit_error("BAD_INPUT", "update-meta 需至少一個 --title / --desc", "")
    body = _request("PUT", f"/knowledge/{args.id}",
                    json_body=payload, headers=_json_headers())
    emit_success({"knowledge_id": args.id, "result": body.get("data") or body},
                 {"elapsed_ms": elapsed_ms(t0)})


def cmd_reparse(args) -> None:
    t0 = timer()
    body = _request("POST", f"/knowledge/{args.id}/reparse", headers=_headers())
    data = body.get("data") or {}
    emit_success(
        {"knowledge_id": args.id, "parse_status": data.get("parse_status")},
        {"elapsed_ms": elapsed_ms(t0), "next": "用 wait 輪詢到 completed"},
    )


def _fetch_status(kid: str) -> dict:
    body = _request("GET", f"/knowledge/{kid}", headers=_headers())
    return body.get("data") or {}


def cmd_status(args) -> None:
    t0 = timer()
    data = _fetch_status(args.id)
    emit_success(
        {"knowledge_id": args.id, "parse_status": data.get("parse_status"),
         "enable_status": data.get("enable_status"), "title": data.get("title"),
         "error_message": data.get("error_message", ""), "knowledge": data},
        {"elapsed_ms": elapsed_ms(t0)},
    )


def cmd_wait(args) -> None:
    t0 = timer()
    deadline = time.monotonic() + args.timeout
    last = ""
    while True:
        try:
            data = _fetch_status(args.id)
        except RuntimeError as e:
            emit_error("FETCH_FAILED", str(e), "確認 knowledge_id / 服務")
        last = str(data.get("parse_status", ""))
        if last in _TERMINAL:
            ok = last == "completed"
            # 到終態即視為輪詢成功完成；實際解析結果由 completed 布林承載
            emit_success(
                {"knowledge_id": args.id, "parse_status": last, "reached_terminal": True,
                 "completed": ok, "enable_status": data.get("enable_status"),
                 "error_message": data.get("error_message", "")},
                {"elapsed_ms": elapsed_ms(t0)},
            )
        if time.monotonic() >= deadline:
            emit_error(
                "RUNTIME",
                f"輪詢逾時（>{args.timeout}s），最後狀態 {last or 'unknown'}",
                "加大 --timeout 或稍後用 status 再查",
            )
        time.sleep(args.interval)


def cmd_search(args) -> None:
    t0 = timer()
    params = {"keyword": args.keyword, "offset": 0, "limit": args.limit}
    if args.file_types:
        params["file_types"] = args.file_types
    body = _request("GET", "/knowledge/search", params=params, headers=_headers())
    # 此 endpoint 的 data 是陣列，has_more 與 data 同級
    items = body.get("data") or []
    slim = [{"id": it.get("id"), "title": it.get("title"), "type": it.get("type"),
             "parse_status": it.get("parse_status"), "enable_status": it.get("enable_status")}
            for it in items] if isinstance(items, list) else items
    emit_success(
        {"count": len(slim) if isinstance(slim, list) else 0, "has_more": body.get("has_more", False),
         "results": slim},
        {"elapsed_ms": elapsed_ms(t0)},
    )


# ── argparse ──────────────────────────────────────────────────────────────

def build_parser():
    import argparse

    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("kb-list")

    sp = sub.add_parser("kb-create")
    sp.add_argument("--name", required=True)
    sp.add_argument("--desc", default="")

    sp = sub.add_parser("add-manual")
    sp.add_argument("--kb", default="", help="知識庫 ID；省略時用 WEKNORA_KB_ID")
    sp.add_argument("--title", required=True)
    sp.add_argument("--content", required=True, help="Markdown 正文；@file 讀檔、- 讀 stdin")
    sp.add_argument("--tag", default="")
    sp.add_argument("--status", default="publish", choices=["publish", "draft"],
                    help="publish 觸發解析入檢索；draft 僅存不解析")

    sp = sub.add_parser("add-file")
    sp.add_argument("--kb", default="", help="知識庫 ID；省略時用 WEKNORA_KB_ID")
    sp.add_argument("--file", required=True)
    sp.add_argument("--tag", default="")
    sp.add_argument("--multimodel", action="store_true")
    sp.add_argument("--file-name", default="", help="保留相對路徑用（如 docs/intro.md）")

    sp = sub.add_parser("add-url")
    sp.add_argument("--kb", default="", help="知識庫 ID；省略時用 WEKNORA_KB_ID")
    sp.add_argument("--url", required=True)
    sp.add_argument("--title", default="")
    sp.add_argument("--tag", default="")
    sp.add_argument("--multimodel", action="store_true")
    sp.add_argument("--file-name", default="", help="顯式檔名→強制走遠端檔案下載模式")
    sp.add_argument("--file-type", default="", help="顯式檔案類型（pdf/docx…）")

    sp = sub.add_parser("update-manual")
    sp.add_argument("--id", required=True)
    sp.add_argument("--title", default=None)
    sp.add_argument("--content", default=None, help="@file 讀檔、- 讀 stdin")

    sp = sub.add_parser("update-meta")
    sp.add_argument("--id", required=True)
    sp.add_argument("--title", default=None)
    sp.add_argument("--desc", default=None)

    sp = sub.add_parser("reparse")
    sp.add_argument("--id", required=True)

    sp = sub.add_parser("status")
    sp.add_argument("--id", required=True)

    sp = sub.add_parser("wait")
    sp.add_argument("--id", required=True)
    sp.add_argument("--timeout", type=int, default=300)
    sp.add_argument("--interval", type=int, default=3)

    sp = sub.add_parser("search")
    sp.add_argument("--keyword", required=True)
    sp.add_argument("--file-types", default="")
    sp.add_argument("--limit", type=int, default=20)

    return p


_DISPATCH = {
    "kb-list": cmd_kb_list,
    "kb-create": cmd_kb_create,
    "add-manual": cmd_add_manual,
    "add-file": cmd_add_file,
    "add-url": cmd_add_url,
    "update-manual": cmd_update_manual,
    "update-meta": cmd_update_meta,
    "reparse": cmd_reparse,
    "status": cmd_status,
    "wait": cmd_wait,
    "search": cmd_search,
}


def main() -> None:
    args = build_parser().parse_args()
    if _headers() is None:
        emit_error("BAD_INPUT", "未設定 WeKnora API Key",
                   "於 .env 設定 WEKNORA_KB_API_KEY（讀寫用）或 WEKNORA_API_KEY")
    try:
        _DISPATCH[args.cmd](args)
    except RuntimeError as e:
        emit_error("FETCH_FAILED", str(e), "確認 WeKnora 服務 / API Key / 網段")


if __name__ == "__main__":
    main()
