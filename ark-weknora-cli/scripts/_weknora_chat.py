#!/usr/bin/env python3
"""_weknora_chat.py — ark-weknora-kb 問答共用工具（session + SSE + 別名解析 + envelope）。

被 weknora_agent_chat.py（/agent-chat）與 weknora_kb_chat.py（/knowledge-chat）共用。
skill 自足：不依賴專案根 scripts._common，自帶 envelope；stdlib + httpx，UTF-8。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

# 載入專案根 .env（IDE 直接跑；服務由 systemd 注入，override=False 無害）
try:
    from dotenv import load_dotenv

    for _p in Path(__file__).resolve().parents:
        _env = _p / ".env"
        if _env.exists():
            load_dotenv(_env, override=False)
            break
except Exception:  # noqa: BLE001
    pass

DEFAULT_API_URL = "http://192.168.5.120:8080/api/v1"
DEFAULT_TIMEOUT = float(os.getenv("ARK_WEKNORA_TIMEOUT", "180"))
_KB_REGISTRY = Path(__file__).resolve().parent.parent / "kb_registry.json"


class WeKnoraError(Exception):
    pass


# ── envelope ──────────────────────────────────────────────────────────────
def emit_success(data: dict, meta: dict | None = None) -> None:
    print(json.dumps({"success": True, "data": data, "meta": meta or {}}, ensure_ascii=False))
    sys.exit(0)


def emit_error(code: str, message: str, hint: str = "") -> None:
    print(json.dumps(
        {"success": False, "error": {"code": code, "message": message, "hint": hint}},
        ensure_ascii=False))
    sys.exit(1)


def api_url() -> str:
    return os.getenv("WEKNORA_API_URL", DEFAULT_API_URL).rstrip("/")


def api_key() -> str:
    return os.getenv("WEKNORA_API_KEY", "")


def headers() -> dict:
    return {"X-API-Key": api_key(), "Content-Type": "application/json"}


# ── KB 別名對照表（A + fallback）────────────────────────────────────────────
def load_kb_registry() -> dict:
    try:
        if _KB_REGISTRY.exists():
            data = json.loads(_KB_REGISTRY.read_text(encoding="utf-8"))
            # 過濾以 _ 開頭的註解鍵
            return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception:  # noqa: BLE001
        pass
    return {}


def resolve_kb(token: str) -> str:
    """把 --kb-id 的輸入解析成 UUID：別名 → 查表；否則原樣（fallback，視為 UUID）。"""
    reg = load_kb_registry()
    return reg.get(token, token)


# ── SSE 收流 ────────────────────────────────────────────────────────────────
def parse_sse(resp, collect_refs: bool):
    """從 httpx stream 逐行解析，回傳 (answer, references)。error 事件 raise WeKnoraError。"""
    chunks: list[str] = []
    refs: list[dict] = []
    seen = set()
    for line in resp.iter_lines():
        line = line.strip() if isinstance(line, str) else line.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        try:
            d = json.loads(line[5:])
        except json.JSONDecodeError:
            continue
        rt = d.get("response_type")
        if rt == "error":
            err = (d.get("data") or {}).get("error") or d.get("content") or "unknown"
            raise WeKnoraError(err)
        if rt == "answer":
            chunks.append(d.get("content", ""))
        if collect_refs and rt == "references":
            for r in (d.get("knowledge_references") or []):
                key = (r.get("knowledge_id"), r.get("chunk_index"))
                if key in seen:
                    continue
                seen.add(key)
                refs.append({
                    "knowledge_title": r.get("knowledge_title"),
                    "knowledge_id": r.get("knowledge_id"),
                    "score": r.get("score"),
                    "chunk_index": r.get("chunk_index"),
                })
    return "".join(chunks), refs


def create_session(client) -> str:
    resp = client.post(f"{api_url()}/sessions", headers=headers(), json={})
    resp.raise_for_status()
    return resp.json()["data"]["id"]


def chat(endpoint_path: str, payload: dict, session_id: str | None,
         collect_refs: bool = True, timeout: float = DEFAULT_TIMEOUT):
    """通用 chat：建/續 session → 打 endpoint SSE → 回 (answer, refs, session_id, elapsed_ms)。

    endpoint_path 例：'agent-chat' / 'knowledge-chat'。
    """
    if not api_key():
        emit_error("BAD_INPUT", "未設定 WEKNORA_API_KEY", "於 .env 補上 WEKNORA_API_KEY")
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=timeout) as client:
            sid = session_id or create_session(client)
            with client.stream("POST", f"{api_url()}/{endpoint_path}/{sid}",
                               headers=headers(), json=payload) as resp:
                resp.raise_for_status()
                answer, refs = parse_sse(resp, collect_refs)
    except httpx.ConnectError:
        emit_error("FETCH_FAILED", "無法連線 WeKnora", "確認服務與網段")
    except httpx.TimeoutException:
        emit_error("FETCH_FAILED", f"WeKnora 逾時（>{timeout:.0f}s）", "")
    except WeKnoraError as e:
        emit_error("RUNTIME", f"WeKnora 錯誤：{e}", "")
    except httpx.HTTPError as e:
        emit_error("FETCH_FAILED", f"HTTP 錯誤：{e}", "")
    elapsed = int((time.monotonic() - t0) * 1000)
    return answer, refs, sid, elapsed
