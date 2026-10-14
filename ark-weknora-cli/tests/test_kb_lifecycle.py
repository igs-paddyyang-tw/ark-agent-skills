#!/usr/bin/env python3
"""test_kb_lifecycle.py — ark-weknora-cli KB 生命週期優化的反證測試。

不連 WeKnora：import weknora_ingest，monkeypatch 模組級 _request 攔截所有 REST，
回放可控 response。涵蓋 P0（kb-create 帶 model + 建完自檢）、P1（wait --until 分流）、
P2（kb-delete fail-safe 二次確認、kb-verify 名實比對）。

每條守門都做兩個方向：違規必紅（emit_error → exit 1）、合規必綠（emit_success → exit 0）。

執行：pytest .kiro/skills/ark-weknora-cli/tests/test_kb_lifecycle.py
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import weknora_ingest as wi  # noqa: E402


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """備齊必要 env，讓 _api_url / _headers 不先報錯。"""
    monkeypatch.setenv("WEKNORA_API_URL", "http://fake-weknora:8080/api/v1")
    monkeypatch.setenv("WEKNORA_KB_API_KEY", "fake-editor-key")
    monkeypatch.delenv("WEKNORA_KB_ID", raising=False)


def _args(**kw):
    return types.SimpleNamespace(**kw)


def _run(fn, args, monkeypatch, responses):
    """以假 _request 執行一個 cmd_*，回傳 (exit_code, envelope_dict, sent_requests)。

    responses：callable(method, path, **kw) -> dict，模擬 WeKnora 回應（或 raise RuntimeError）。
    """
    sent = []

    def fake_request(method, path, **kw):
        sent.append({"method": method, "path": path, **kw})
        return responses(method, path, **kw)

    monkeypatch.setattr(wi, "_request", fake_request)
    out = {}
    code = None
    import io
    import contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            fn(args)
    except SystemExit as e:
        code = e.code
    line = buf.getvalue().strip().splitlines()
    if line:
        out = json.loads(line[-1])
    return code, out, sent


# ── P0：kb-create 帶 model + 建完自檢 ──────────────────────────────────

def test_kb_create_without_model_and_no_existing_kb_rejects(monkeypatch):
    """反證：不帶 --embedding-model 且租戶無既有 KB 可沿用 → BAD_INPUT（exit 1），不送 POST。"""
    def resp(method, path, **kw):
        if method == "GET" and path == "/knowledge-bases":
            return {"data": []}  # 無既有 KB
        raise AssertionError(f"不應送出 {method} {path}")
    code, out, sent = _run(wi.cmd_kb_create, _args(
        name="新庫", desc="", embedding_model="", summary_model="", from_template=""),
        monkeypatch, resp)
    assert code == 1, f"缺 model 應 exit 1，實際 {code}：{out}"
    assert out["error"]["code"] == "BAD_INPUT"
    assert not any(s["method"] == "POST" for s in sent), "缺 model 時不應送出建庫 POST"


def test_kb_create_with_explicit_model_sends_toplevel_field(monkeypatch):
    """合規：帶 --embedding-model → payload 頂層含 embedding_model_id，且 POST 建庫。"""
    def resp(method, path, **kw):
        if method == "GET" and path == "/knowledge-bases":
            return {"data": []}  # summary 未帶 → 嘗試沿用，無既有則留空
        if method == "POST":
            body = kw["json_body"]
            assert body.get("embedding_model_id") == "emb-x", f"payload 應帶頂層 model：{body}"
            return {"data": {"id": "kb-1", "name": body["name"], "embedding_model_id": "emb-x"}}
        raise AssertionError(f"未預期 {method} {path}")
    code, out, sent = _run(wi.cmd_kb_create, _args(
        name="市場專家", desc="", embedding_model="emb-x", summary_model="", from_template=""),
        monkeypatch, resp)
    assert code == 0, f"帶 model 應成功，實際 {code}：{out}"
    assert out["data"]["embedding_model_id"] == "emb-x"
    assert out["meta"]["model_source"] == "explicit"


def test_kb_create_selfcheck_empty_model_in_response_fails(monkeypatch):
    """反證：建庫回應的 embedding_model_id 為空 → 自檢 RUNTIME（exit 1），不靜默成功。"""
    def resp(method, path, **kw):
        if method == "GET" and path == "/knowledge-bases":
            return {"data": []}
        if method == "POST":
            return {"data": {"id": "kb-ghost", "name": "空殼", "embedding_model_id": ""}}
        raise AssertionError
    code, out, _ = _run(wi.cmd_kb_create, _args(
        name="空殼", desc="", embedding_model="emb-x", summary_model="", from_template=""),
        monkeypatch, resp)
    assert code == 1, f"建完 model 空應 exit 1，實際 {code}：{out}"
    assert out["error"]["code"] == "RUNTIME"
    assert "空" in out["error"]["message"]


def test_kb_create_inherits_model_from_existing_kb(monkeypatch):
    """合規：未帶 model 但租戶有既有 KB → 沿用其 model（inherited_from_tenant）。"""
    def resp(method, path, **kw):
        if method == "GET" and path == "/knowledge-bases":
            return {"data": [{"id": "kb-old", "embedding_model_id": "emb-inherited",
                              "summary_model_id": "sum-inherited"}]}
        if method == "POST":
            assert kw["json_body"]["embedding_model_id"] == "emb-inherited"
            return {"data": {"id": "kb-2", "name": "新庫", "embedding_model_id": "emb-inherited"}}
        raise AssertionError
    code, out, _ = _run(wi.cmd_kb_create, _args(
        name="新庫", desc="", embedding_model="", summary_model="", from_template=""),
        monkeypatch, resp)
    assert code == 0, f"沿用既有 model 應成功：{out}"
    assert out["meta"]["model_source"] == "inherited_from_tenant"


# ── P1：wait --until 分流 ──────────────────────────────────────────────

def test_wait_until_enabled_returns_on_enable_status(monkeypatch):
    """合規：--until enabled → enable_status=enabled 即終態 completed=true。"""
    def resp(method, path, **kw):
        # finalizing（parse 未 completed）但 enable 已 enabled → enabled 模式應判成功
        return {"data": {"parse_status": "finalizing", "enable_status": "enabled"}}
    code, out, _ = _run(wi.cmd_wait, _args(id="k1", timeout=5, interval=0, until="enabled"),
                        monkeypatch, resp)
    assert code == 0 and out["data"]["completed"] is True, f"enabled 應判成功：{out}"
    assert out["data"]["enable_status"] == "enabled"


def test_wait_until_completed_ignores_enable_status(monkeypatch):
    """反證：--until completed → 只看 parse_status；enable 雖 enabled 但 parse=completed 才終態。"""
    def resp(method, path, **kw):
        return {"data": {"parse_status": "completed", "enable_status": "enabled"}}
    code, out, _ = _run(wi.cmd_wait, _args(id="k1", timeout=5, interval=0, until="completed"),
                        monkeypatch, resp)
    assert code == 0 and out["data"]["parse_status"] == "completed", out
    assert out["data"]["until"] == "completed"


# ── P2：kb-delete fail-safe 二次確認 ───────────────────────────────────

def _delete_resp(method, path, **kw):
    if method == "GET":
        return {"data": {"id": "kb-del", "name": "市場專家"}}
    if method == "DELETE":
        return {"data": {"deleted": True}}
    raise AssertionError(f"未預期 {method} {path}")


def test_kb_delete_without_confirm_refuses(monkeypatch):
    """反證（守門一，隔離）：expect_name 正確但無 --confirm → 仍須被守門一擋下，不送 DELETE。

    expect_name 給正確名是刻意的：讓守門二不會先擋，才能獨立證明「守門一自己」有效。
    """
    code, out, sent = _run(wi.cmd_kb_delete,
                           _args(kb="kb-del", confirm=False, expect_name="市場專家"),
                           monkeypatch, _delete_resp)
    assert code == 1 and out["error"]["code"] == "BAD_INPUT", out
    assert "confirm" in out["error"]["message"], f"應是守門一（缺 confirm）：{out['error']}"
    assert not any(s["method"] == "DELETE" for s in sent), "無 confirm 絕不可送 DELETE"


def test_kb_delete_wrong_name_refuses(monkeypatch):
    """反證（守門二）：有 --confirm 但 --expect-name 與實際不符 → 拒絕，不送 DELETE。"""
    code, out, sent = _run(wi.cmd_kb_delete,
                           _args(kb="kb-del", confirm=True, expect_name="打錯的名字"),
                           monkeypatch, _delete_resp)
    assert code == 1 and out["error"]["code"] == "BAD_INPUT", out
    assert not any(s["method"] == "DELETE" for s in sent), "名稱不符絕不可送 DELETE"


def test_kb_delete_confirmed_and_name_match_proceeds(monkeypatch):
    """合規：--confirm + --expect-name 與實際完全相符 → 才送 DELETE。"""
    code, out, sent = _run(wi.cmd_kb_delete,
                           _args(kb="kb-del", confirm=True, expect_name="市場專家"),
                           monkeypatch, _delete_resp)
    assert code == 0 and out["data"]["deleted"] is True, out
    assert any(s["method"] == "DELETE" for s in sent), "兩道守門過才送 DELETE"


# ── P2：kb-verify 名實比對 ─────────────────────────────────────────────

def test_kb_verify_reports_not_found(monkeypatch):
    """合規：registry 別名的 UUID 不在實際 KB 清單 → 標記 not_found。"""
    def resp(method, path, **kw):
        return {"data": [{"id": "uuid-real", "name": "真的庫"}]}
    monkeypatch.setattr(wi, "_load_registry",
                        lambda: {"_note": "x", "good": "uuid-real", "stale": "uuid-gone"})
    code, out, _ = _run(wi.cmd_kb_verify, _args(), monkeypatch, resp)
    assert code == 0, out
    by_alias = {c["alias"]: c for c in out["data"]["checks"]}
    assert by_alias["good"]["status"] == "ok"
    assert by_alias["stale"]["status"] == "not_found"
    assert out["data"]["not_found"] == 1
