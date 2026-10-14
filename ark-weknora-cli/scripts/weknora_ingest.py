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
  WEKNORA_API_URL   WeKnora REST base（必填，見 assets/.env.example）
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

_TIMEOUT_SEC = 60.0
# parse_status 終態：到達其一即停止輪詢
_TERMINAL = {"completed", "failed", "cancelled"}


def _api_url() -> str:
    url = os.getenv("WEKNORA_API_URL", "").rstrip("/")
    if not url:
        emit_error("BAD_INPUT", "未設定 WEKNORA_API_URL",
                   "於 .env 補上 WEKNORA_API_URL（見 assets/.env.example）")
    return url


def _resolve_kb(kb_arg: str) -> str:
    """--kb 未帶時回退到 WEKNORA_KB_ID；別名經 kb_registry 解析成 UUID；都沒有則報錯。"""
    kb = kb_arg or os.getenv("WEKNORA_KB_ID", "")
    if not kb:
        emit_error("BAD_INPUT", "未指定知識庫 ID",
                   "帶 --kb <id>，或於 .env 設定 WEKNORA_KB_ID")
    # 別名 → UUID（與 knowledge-chat 一致；非別名則原樣視為 UUID）
    try:
        from _weknora_chat import resolve_kb as _reg_resolve
        kb = _reg_resolve(kb)
    except Exception:  # noqa: BLE001 — registry 缺失或載入失敗時退回原值
        pass
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
    # P0：建庫時 model 必須在頂層欄位帶入 —— WeKnora 的 CreateKnowledgeBase 把 request body
    # 整個 bind 成 KnowledgeBase，而 UpdateKnowledgeBase 的 struct 不含這兩欄，事後 PUT 補不回來，
    # 只能刪庫重建。未帶時自動沿用租戶既有 KB 的 model id（唯讀 key 看不到 /models）。
    tmpl = _lookup_template_kb(args.from_template) if getattr(args, "from_template", "") else {}
    emb = args.embedding_model or tmpl.get("embedding_model_id") or _infer_model("embedding_model_id")
    summ = args.summary_model or tmpl.get("summary_model_id") or _infer_model("summary_model_id")
    if not emb:
        emit_error(
            "BAD_INPUT",
            "建庫缺 embedding model：未帶 --embedding-model 且租戶無既有 KB 可沿用",
            "帶 --embedding-model <id>（可用 model id 見 SKILL.md）；"
            "或先確認租戶已有至少一個綁好 model 的 KB 供沿用",
        )
    payload: dict = {"name": args.name, "embedding_model_id": emb}
    if summ:
        payload["summary_model_id"] = summ
    if args.desc:
        payload["description"] = args.desc
    body = _request("POST", "/knowledge-bases", json_body=payload, headers=_json_headers())
    kb = body.get("data") or body
    # P0 建完自檢：回應 embedding_model_id 若空 → 建出廢庫，必須報錯提示重建（不靜默成功）
    got_emb = (kb.get("embedding_model_id") if isinstance(kb, dict) else "") or ""
    if not got_emb:
        emit_error(
            "RUNTIME",
            f"建庫回應的 embedding_model_id 為空（kb_id={kb.get('id') if isinstance(kb, dict) else '?'}）"
            "：此庫無法向量化、上傳必失敗，且事後 PUT 補不回來",
            "刪掉此空殼庫後，帶明確的 --embedding-model 重建",
        )
    emit_success(
        {"knowledge_base": kb, "embedding_model_id": got_emb,
         "summary_model_id": (kb.get("summary_model_id") if isinstance(kb, dict) else "") or ""},
        {"elapsed_ms": elapsed_ms(t0), "model_source": _model_source(args, tmpl)},
    )


def _list_kbs() -> list:
    """GET /knowledge-bases → KB list（空/非 list 回 []）。"""
    body = _request("GET", "/knowledge-bases", headers=_headers())
    kbs = body.get("data") or []
    return kbs if isinstance(kbs, list) else []


def _infer_model(field: str) -> str:
    """從租戶既有 KB 沿用 model id：回第一個該欄位非空的值（唯讀 key 看不到 /models 時的來源）。"""
    try:
        for k in _list_kbs():
            v = (k.get(field) if isinstance(k, dict) else "") or ""
            if v:
                return v
    except RuntimeError:
        pass  # 列舉失敗（如無權限）→ 無法沿用，交由上層缺 model 的守門處理
    return ""


def _lookup_template_kb(alias_or_id: str) -> dict:
    """--from-template：以別名/UUID 定位既有 KB，回其完整設定 dict（找不到回 {}）。"""
    target = _resolve_kb(alias_or_id)
    try:
        for k in _list_kbs():
            if isinstance(k, dict) and k.get("id") == target:
                return k
    except RuntimeError:
        pass
    return {}


def _model_source(args, tmpl: dict) -> str:
    if args.embedding_model:
        return "explicit"
    if tmpl:
        return "from_template"
    return "inherited_from_tenant"


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
    until = getattr(args, "until", "enabled")
    last = ""
    while True:
        try:
            data = _fetch_status(args.id)
        except RuntimeError as e:
            emit_error("FETCH_FAILED", str(e), "確認 knowledge_id / 服務")
        parse_status = str(data.get("parse_status", ""))
        enable_status = str(data.get("enable_status", ""))
        if until == "enabled":
            # P1：預設看 enable_status=enabled —— 向量索引就緒即可檢索，不必等 summary 的
            # finalizing 完成（卡 finalizing 會讓舊的 parse_status=completed 判定誤判逾時）。
            # 解析失敗（parse_status=failed）仍是終態，據實回報 completed=false。
            last = enable_status or parse_status
            if enable_status == "enabled" or parse_status == "failed":
                ok = enable_status == "enabled"
                emit_success(
                    {"knowledge_id": args.id, "until": until, "reached_terminal": True,
                     "completed": ok, "parse_status": parse_status, "enable_status": enable_status,
                     "error_message": data.get("error_message", "")},
                    {"elapsed_ms": elapsed_ms(t0)},
                )
        else:  # until == "completed"（舊行為：等 parse_status 終態）
            last = parse_status
            if parse_status in _TERMINAL:
                ok = parse_status == "completed"
                emit_success(
                    {"knowledge_id": args.id, "until": until, "parse_status": parse_status,
                     "reached_terminal": True, "completed": ok,
                     "enable_status": enable_status, "error_message": data.get("error_message", "")},
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


def cmd_ingest_dir(args) -> None:
    """P2：批次上傳一個目錄下的檔案，逐檔 add-file → 等 enabled，最後匯總。"""
    import glob as _glob
    t0 = timer()
    kb = _resolve_kb(args.kb)
    root = Path(args.dir)
    if not root.is_dir():
        emit_error("BAD_INPUT", f"目錄不存在：{args.dir}", "確認路徑")
    pats = [p.strip() for p in (args.pattern or "").split(",") if p.strip()] or ["*"]
    paths: list[Path] = []
    for pat in pats:
        paths += [Path(p) for p in _glob.glob(str(root / ("**/" + pat if args.recursive else pat)),
                                              recursive=args.recursive)]
    files = sorted({p for p in paths if p.is_file()})
    if not files:
        emit_error("BAD_INPUT", f"目錄無符合檔案（pattern={pats}）", "調整 --pattern / --recursive")
    results = []
    for fp in files:
        try:
            with fp.open("rb") as fh:
                body = _request("POST", f"/knowledge-bases/{kb}/knowledge/file",
                                files={"file": (fp.name, fh)}, headers=_headers())
            kid = (body.get("data") or {}).get("id")
            status = "uploaded"
            if kid and not args.no_wait:
                # 逐檔等 enabled（P1 的判定）
                deadline = time.monotonic() + args.timeout
                status = "waiting"
                while time.monotonic() < deadline:
                    d = _fetch_status(kid)
                    if str(d.get("enable_status", "")) == "enabled":
                        status = "enabled"
                        break
                    if str(d.get("parse_status", "")) == "failed":
                        status = "failed"
                        break
                    time.sleep(args.interval)
            results.append({"file": fp.name, "knowledge_id": kid, "status": status})
        except RuntimeError as e:
            msg = str(e)
            # 同 hash 檔 409 視為已存在，不中斷整批
            results.append({"file": fp.name, "status": "exists" if "已存在" in msg else "error",
                            "error": msg})
    ok = sum(1 for r in results if r["status"] in ("enabled", "uploaded"))
    emit_success(
        {"kb": kb, "total": len(results), "ok": ok, "items": results},
        {"elapsed_ms": elapsed_ms(t0)},
    )


def cmd_kb_verify(args) -> None:
    """P2：比對 kb_registry 別名 ↔ 實際 KB 名，報出名實不符 / 找不到的別名。"""
    t0 = timer()
    kbs = _list_kbs()
    by_id = {k.get("id"): k.get("name", "") for k in kbs if isinstance(k, dict)}
    reg = _load_registry()
    checks = []
    for alias, uuid in reg.items():
        if alias.startswith("_"):
            continue
        if not isinstance(uuid, str) or uuid.startswith("REPLACE_"):
            checks.append({"alias": alias, "status": "placeholder", "kb_name": None})
            continue
        if uuid in by_id:
            checks.append({"alias": alias, "uuid": uuid, "kb_name": by_id[uuid], "status": "ok"})
        else:
            checks.append({"alias": alias, "uuid": uuid, "kb_name": None,
                           "status": "not_found"})
    bad = [c for c in checks if c["status"] == "not_found"]
    emit_success(
        {"registry_entries": len(checks), "ok": sum(1 for c in checks if c["status"] == "ok"),
         "not_found": len(bad), "checks": checks},
        {"elapsed_ms": elapsed_ms(t0)},
    )


def _load_registry() -> dict:
    """讀 kb_registry.json（與 _resolve_kb 的來源一致）；失敗回 {}。"""
    try:
        from _weknora_chat import _registry_path  # type: ignore
        p = Path(_registry_path())
    except Exception:  # noqa: BLE001
        p = Path(__file__).resolve().parent.parent / "kb_registry.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def cmd_kb_delete(args) -> None:
    """P2：刪除 KB —— 破壞性操作，執行期 fail-safe 二次確認守門。

    保護（預設安全，絕不自動刪）：
      1. 必須帶 --confirm（純旗標不足以執行，只是表示「我知道這會刪」）。
      2. 必須帶 --expect-name，且其值要與伺服器上該 KB 的實際名稱**完全相符**才執行。
    缺任一、或名稱對不上，一律拒絕（exit 1），不送出 DELETE。
    """
    t0 = timer()
    kb = _resolve_kb(args.kb)
    # 先取實際 KB 名供核對（也確認 KB 真的存在）
    try:
        info = _request("GET", f"/knowledge-bases/{kb}", headers=_headers())
        actual = (info.get("data") or info).get("name", "") if isinstance(info, dict) else ""
    except RuntimeError as e:
        emit_error("FETCH_FAILED", f"無法取得 KB 資訊：{e}", "確認 --kb 的別名/UUID 正確且 KB 存在")
    # 守門一：必須明示 --confirm
    if not args.confirm:
        emit_error(
            "BAD_INPUT",
            f"kb-delete 是破壞性操作，拒絕執行：缺 --confirm（目標 KB「{actual}」/ {kb}）",
            f"確認要刪除請加：--confirm --expect-name \"{actual}\"",
        )
    # 守門二：必須打出與實際完全相符的 KB 名核對
    if (args.expect_name or "") != actual:
        emit_error(
            "BAD_INPUT",
            f"kb-delete 名稱核對不符，拒絕執行：--expect-name=「{args.expect_name}」"
            f"，但目標 KB 實際名稱為「{actual}」",
            f"若確定要刪，--expect-name 必須與實際名稱完全一致：--expect-name \"{actual}\"",
        )
    # 兩道守門都通過才送出 DELETE
    _request("DELETE", f"/knowledge-bases/{kb}", headers=_headers())
    emit_success(
        {"deleted": True, "kb_id": kb, "kb_name": actual},
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
    sp.add_argument("--embedding-model", default="",
                    help="embedding model id（必要；未帶則沿用租戶既有 KB 的 model）")
    sp.add_argument("--summary-model", default="",
                    help="summary model id（選用；未帶則沿用既有/範本）")
    sp.add_argument("--from-template", default="",
                    help="以既有 KB（別名或 UUID）的設定為範本建新庫")

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
    sp.add_argument("--until", default="enabled", choices=["enabled", "completed"],
                    help="終態判定：enabled=看 enable_status（預設，索引就緒即可）；"
                         "completed=看 parse_status（含 summary finalizing）")

    sp = sub.add_parser("search")
    sp.add_argument("--keyword", required=True)
    sp.add_argument("--file-types", default="")
    sp.add_argument("--limit", type=int, default=20)

    sp = sub.add_parser("ingest-dir", help="批次上傳目錄下檔案，逐檔等 enabled")
    sp.add_argument("--kb", default="", help="知識庫 ID；省略時用 WEKNORA_KB_ID")
    sp.add_argument("--dir", required=True, help="來源目錄")
    sp.add_argument("--pattern", default="*", help="檔名樣式，逗號分隔（如 *.md,*.pdf）")
    sp.add_argument("--recursive", action="store_true", help="遞迴子目錄")
    sp.add_argument("--no-wait", action="store_true", help="只上傳不等 enabled")
    sp.add_argument("--timeout", type=int, default=300, help="每檔等 enabled 的逾時秒數")
    sp.add_argument("--interval", type=int, default=3)

    sub.add_parser("kb-verify", help="比對 kb_registry 別名 ↔ 實際 KB 名")

    sp = sub.add_parser("kb-delete", help="刪除 KB（破壞性！需 --confirm + --expect-name 核對）")
    sp.add_argument("--kb", default="", help="要刪的知識庫（別名或 UUID）；省略時用 WEKNORA_KB_ID")
    sp.add_argument("--confirm", action="store_true",
                    help="明示確認要刪除（缺此旗標一律拒絕執行）")
    sp.add_argument("--expect-name", default="",
                    help="打出該 KB 的實際名稱核對；與伺服器實際名稱完全相符才執行")

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
    "ingest-dir": cmd_ingest_dir,
    "kb-verify": cmd_kb_verify,
    "kb-delete": cmd_kb_delete,
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
