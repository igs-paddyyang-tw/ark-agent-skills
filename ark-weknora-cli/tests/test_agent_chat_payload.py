#!/usr/bin/env python3
"""test_agent_chat_payload.py — agent-chat payload 建構回歸。

🔴 服務端 wiki_search 在缺 knowledge_base_ids 欄位時會踩 regex bug（實測：不帶掛、帶 [] 正常）。
本測試鎖定「payload 一定帶 knowledge_base_ids」這條不變量 —— 拿掉 default [] 就會紅。

不連 WeKnora：monkeypatch _weknora_chat.chat 攔截 payload。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture()
def capture(monkeypatch):
    """攔 chat()，記下 payload，回一個成功的假答案讓 main 走完。"""
    seen = {}

    def _fake_chat(endpoint, payload, session_id, collect_refs=True, timeout=180):
        seen["endpoint"] = endpoint
        seen["payload"] = payload
        return "假答案", [], "sess-1", 5

    import _weknora_chat
    monkeypatch.setattr(_weknora_chat, "chat", _fake_chat)
    # weknora_agent_chat 直接 from _weknora_chat import chat → 也要 patch 它的引用
    import importlib
    import weknora_agent_chat as WAC
    importlib.reload(WAC)
    monkeypatch.setattr(WAC, "chat", _fake_chat)
    monkeypatch.setenv("WEKNORA_AGENT_ID", "0d9333e6-fake")
    return seen, WAC


def _run(WAC, argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["weknora_agent_chat.py", *argv])
    with pytest.raises(SystemExit) as ei:
        WAC.main()
    return ei.value.code


def test_payload_always_carries_empty_kb_ids(capture, monkeypatch):
    """🔴 不帶 --kb-id 時，payload 仍必須有 knowledge_base_ids: []（繞過服務端 regex bug）。"""
    seen, WAC = capture
    rc = _run(WAC, ["--query", "研七營收口徑"], monkeypatch)
    assert rc == 0, f"預期成功 exit 0，實際 {rc}"
    assert "knowledge_base_ids" in seen["payload"], \
        f"payload 缺 knowledge_base_ids → 會踩服務端 wiki_search regex bug：{seen['payload']}"
    assert seen["payload"]["knowledge_base_ids"] == [], \
        f"預設應為空陣列 []：{seen['payload']['knowledge_base_ids']}"
    assert seen["endpoint"] == "agent-chat"


def test_kb_id_overrides_the_empty_default(capture, monkeypatch):
    """帶 --kb-id 時覆蓋為指定範圍（別名解析後）。"""
    seen, WAC = capture
    rc = _run(WAC, ["--query", "q", "--kb-id", "some-uuid"], monkeypatch)
    assert rc == 0
    assert seen["payload"]["knowledge_base_ids"] == ["some-uuid"], \
        f"--kb-id 應覆蓋預設 []：{seen['payload']['knowledge_base_ids']}"
