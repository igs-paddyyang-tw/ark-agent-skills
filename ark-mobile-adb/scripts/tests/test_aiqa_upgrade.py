#!/usr/bin/env python3
"""test_aiqa_upgrade — v2.3 兩功能反證測試：read.stabilize 穩定讀數 + testgen refine 人工回饋迴圈。

不需 WeKnora / BlueStacks：
- stabilize：monkeypatch aiqa_device.read_roi 餵可控讀數序列，用 FakeDevice 推進假時間，驗「連兩次相同才收、不穩收 None」。
- refine：純函式，直接餵帶 review 欄的 checklist，驗各指令套用 + 未填保留 + 自由文字進待人工。

執行：pytest .kiro/skills/ark-mobile-adb/scripts/tests/test_aiqa_upgrade.py
"""
from __future__ import annotations

import pathlib
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import aiqa_device as D  # noqa: E402
import aiqa_run as R  # noqa: E402
import aiqa_testgen as T  # noqa: E402


# ── read.stabilize ────────────────────────────────────────────────────

def _make_executor(tmp_path):
    import aiqa_common as C
    pack = C.load_pack("demo-slot")
    trace = D.Trace(tmp_path / "trace.jsonl")
    dev = D.FakeDevice(trace)
    return R.Executor(dev, pack, tmp_path / "ex", reader="fake", visual="fake", llm=None, timeout_s=60)


def _feed_reads(monkeypatch, values):
    """讓 D.read_roi 依序回傳 values 裡的值（用完停在最後一個）。"""
    seq = list(values)
    state = {"i": 0}

    def fake_read_roi(dev, pack, roi, img, d, reader, oracle, llm):
        i = min(state["i"], len(seq) - 1)
        state["i"] += 1
        return {"value": seq[i], "engine": "fake", "confidence": 1.0, "crop": str(img)}

    monkeypatch.setattr(D, "read_roi", fake_read_roi)


def test_stabilize_same_twice_settles_when_stable(tmp_path, monkeypatch):
    """合規：連兩次讀數相同 → 收該值（stable）。"""
    _feed_reads(monkeypatch, [500, 500])  # 首讀 500，複讀 500 → 穩
    ex = _make_executor(tmp_path)
    ex.a_read({"name": "金幣", "roi": "roi_credit", "oracle": "ocr_number",
               "stabilize": {"mode": "same_twice", "interval_ms": 1, "timeout_s": 5}})
    assert ex.obs["金幣"][-1] == 500, ex.obs
    assert ex.evidence[-1]["stabilized"] is True


def test_stabilize_countup_never_settles_records_none(tmp_path, monkeypatch):
    """反證（頭號誤判）：count-up 一路遞增、連兩次都不同 → 逾時不穩 → 收 None（→ oracle 判 NEEDS_HUMAN）。"""
    _feed_reads(monkeypatch, [100, 200, 300, 400, 500, 600, 700, 800])  # 永遠在跳
    ex = _make_executor(tmp_path)
    ex.a_read({"name": "金幣", "roi": "roi_credit", "oracle": "ocr_number",
               "stabilize": {"mode": "same_twice", "interval_ms": 1, "timeout_s": 2}})
    assert ex.obs["金幣"][-1] is None, f"count-up 不穩必須收 None，實際 {ex.obs['金幣']}"
    assert ex.evidence[-1]["stabilized"] is False


def test_stabilize_none_leads_to_needs_human():
    """反證接力：stabilize 收 None → oracle 的 ocr_number expr 判 NEEDS_HUMAN（不誤 PASS）。"""
    import aiqa_oracle as O
    res = O.evaluate([{"id": "A", "oracle": "ocr_number", "expr": "金幣 >= 0", "expect": "金幣可讀"}],
                     {"金幣": [None]})
    assert res[0]["result"] == "NEEDS_HUMAN", res


def test_stabilize_two_sources_consistent(tmp_path, monkeypatch):
    """合規：two_sources roi 與 roi2 讀數一致 → 收該值。"""
    _feed_reads(monkeypatch, [777, 777])  # roi 首讀 777、roi2 讀 777 → 一致
    ex = _make_executor(tmp_path)
    ex.a_read({"name": "寶石", "roi": "roi_credit", "oracle": "ocr_number",
               "stabilize": {"mode": "two_sources", "roi2": "roi_bet", "interval_ms": 1, "timeout_s": 5}})
    assert ex.obs["寶石"][-1] == 777 and ex.evidence[-1]["stabilized"] is True, ex.obs


# ── testgen refine ────────────────────────────────────────────────────

def _doc(items):
    return {"contract": "1", "game": "demo-slot", "items": items}


def test_refine_delete_removes_item():
    doc, changes, pending = T.refine(_doc([
        {"id": "X-1", "title": "多餘項", "review": "刪除"},
        {"id": "X-2", "title": "保留項"},
    ]))
    ids = [i["id"] for i in doc["items"]]
    assert ids == ["X-2"], ids
    assert any(c["result"] == "deleted" and c["id"] == "X-1" for c in changes)


def test_refine_change_fields():
    doc, changes, _ = T.refine(_doc([
        {"id": "X-1", "title": "舊目的", "manual_steps": ["舊步"],
         "assertions": [{"id": "A1", "oracle": "ocr_number", "expect": "舊預期"}],
         "review": "改目的:新目的\n改步驟:進遊戲;觀察\n改預期:新預期\n備註:必測"},
    ]))
    it = doc["items"][0]
    assert it["title"] == "新目的"
    assert it["manual_steps"] == ["進遊戲", "觀察"]
    assert it["assertions"][0]["expect"] == "新預期"
    assert it["note"] == "必測"
    assert "review" not in it, "套用後 review 應清空"


def test_refine_append_to_last_expect():
    """補: → 末條 assertion 的 expect 追加（補 [待補] 數值常用）。"""
    doc, _, _ = T.refine(_doc([
        {"id": "X-1", "title": "t", "assertions": [{"id": "A1", "oracle": "ocr_number", "expect": "SC 分數"}],
         "review": "補:8/18/38"},
    ]))
    assert doc["items"][0]["assertions"][0]["expect"] == "SC 分數；8/18/38"


def test_refine_unreviewed_untouched():
    """反證：未填 review 的 item 原樣保留、不列入變更。"""
    original = {"id": "X-1", "title": "沒意見", "assertions": [{"id": "A1", "oracle": "visual", "expect": "x"}]}
    doc, changes, pending = T.refine(_doc([dict(original)]))
    assert doc["items"][0] == original, "未填 review 不應被改動"
    assert changes == [] and pending == []


def test_refine_freeform_goes_pending():
    """反證：自由文字（非協定指令）不自動套用，列入待人工。"""
    doc, changes, pending = T.refine(_doc([
        {"id": "X-1", "title": "t", "review": "這條要跟 PM 確認賠率"},
    ]))
    assert len(pending) == 1 and pending[0]["id"] == "X-1"
    assert "PM" in pending[0]["text"]
    # 自由文字未改任何欄位，但 review 會被清空（已轉入報告）
    assert "review" not in doc["items"][0]
