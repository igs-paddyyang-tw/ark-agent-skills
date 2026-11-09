"""ark-browser-tool 測試：純函式（不需瀏覽器）＋本機 HTML 端到端（需 playwright＋Chromium，缺就 skip）。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import browser_tool as bt  # noqa: E402

PAGE = """<!doctype html><html><body>
<div id="boot" data-state="loading">loading</div>
<span id="bal">1,000</span>
<input id="name"><button id="add" onclick="window.app.add()">+100</button>
<script>
window.app = { balance: 1000, add() { this.balance += 100; document.getElementById('bal').textContent = this.balance.toLocaleString('en'); } };
setTimeout(() => { document.getElementById('boot').dataset.state = 'playable'; }, 200);
</script></body></html>"""


# ---------------------------------------------------------------- 純函式
def test_interp_keeps_type_for_full_match():
    v = {"n": 5, "pt": {"x": 1, "y": 2}}
    assert bt.interp("${n}", v) == 5
    assert bt.interp("${pt}", v) == {"x": 1, "y": 2}
    assert bt.interp("/p?n=${n}", v) == "/p?n=5"
    assert bt.interp({"a": ["${n}"]}, v) == {"a": [5]}


@pytest.mark.parametrize(("actual", "spec", "ok"), [
    (5, {"gt": 3}, True), (5, {"lt": 3}, False), ("abc", {"contains": "b"}, True),
    (1, {"equals": 1}, True), (0, {}, False), ("x", {"gt": 1}, False),
])
def test_compare(actual, spec, ok):
    assert bt.compare(actual, spec)[0] is ok


def test_validate_rejects_two_actions(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"schema": bt.SCHEMA, "steps": [{"goto": "/", "click": "#a"}]}), encoding="utf-8")
    with pytest.raises(bt.ScenarioError):
        bt.load_scenario(p)


def test_validate_rejects_wrong_schema(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"schema": "x", "steps": [{"goto": "/"}]}), encoding="utf-8")
    with pytest.raises(bt.ScenarioError):
        bt.load_scenario(p)


# ---------------------------------------------------------------- 端到端（本機 HTML）
def _browser_ready() -> bool:
    if bt._import_playwright() is None:
        return False
    rep = asyncio.run(bt.cmd_doctor(None))
    return bool(rep.get("chromium"))


needs_browser = pytest.mark.skipif(not _browser_ready(), reason="需要 playwright＋Chromium")


def _scenario(page_url: str, steps: list, **kw) -> dict:
    return {"schema": bt.SCHEMA, "name": "t", "base_url": page_url, "steps": steps, **kw}


@pytest.fixture()
def page_url(tmp_path) -> str:
    f = tmp_path / "page.html"
    f.write_text(PAGE, encoding="utf-8")
    return f.as_uri()


@needs_browser
def test_run_pass_with_dom_and_js(page_url, tmp_path):
    sc = _scenario(page_url, [
        {"goto": page_url},
        {"wait_for": {"selector": '#boot[data-state="playable"]', "state": "attached"}},
        {"read": {"as": "b0", "js": "window.app.balance"}},
        {"click": "#add"},
        {"expect": {"js": "window.app.balance === v.b0 + 100", "equals": True}},
        {"expect_text": {"selector": "#bal", "equals": "1,100"}},
        {"read": {"as": "shown", "selector": "#bal", "number": True}},
        {"expect": {"value": "${shown}", "equals": 1100.0}},
        {"fill": {"selector": "#name", "value": "aiqa"}},
        {"repeat": {"times": 2, "steps": [{"click": "#add"}]}},
        {"expect": {"js": "window.app.balance", "equals": 1300}},
        {"shot": "done"},
    ])
    rep = asyncio.run(bt.run_scenario(sc, tmp_path / "out", None, False, False, True))
    assert rep["verdict"] == "PASS", rep
    assert (tmp_path / "out" / "report.md").exists()
    assert (tmp_path / "out" / "trace.zip").exists()


@needs_browser
def test_run_fail_stops_and_leaves_evidence(page_url, tmp_path):
    sc = _scenario(page_url, [
        {"goto": page_url},
        {"expect": {"js": "window.app.balance", "equals": 999}, "name": "錯誤期望"},
        {"click": "#add"},
    ])
    rep = asyncio.run(bt.run_scenario(sc, tmp_path / "out", None, False, False, False))
    assert rep["verdict"] == "FAIL"
    assert rep["steps_total"] == 2           # 失敗後停止
    assert rep["steps"][-1]["shot"].startswith("shots/")


@needs_browser
def test_page_error_fails_run(tmp_path):
    f = tmp_path / "err.html"
    f.write_text("<html><body><script>throw new Error('boom')</script></body></html>", encoding="utf-8")
    sc = _scenario(f.as_uri(), [{"goto": f.as_uri()}, {"sleep": 100}])
    rep = asyncio.run(bt.run_scenario(sc, tmp_path / "out", None, False, False, False))
    assert rep["verdict"] == "FAIL"
    assert rep["findings"][0]["check"] == "page_errors"


@needs_browser
def test_leaving_allowed_origin_blocks(page_url, tmp_path):
    sc = _scenario(page_url, [{"goto": page_url}, {"goto": "about:blank#elsewhere"}], allowed_origins=["file:"])
    rep = asyncio.run(bt.run_scenario(sc, tmp_path / "out", None, False, False, False))
    assert rep["verdict"] == "PASS"          # about: 一律允許
    sc2 = _scenario(page_url, [{"goto": page_url}, {"goto": "http://127.0.0.1:9/"}], allowed_origins=["file:"])
    rep2 = asyncio.run(bt.run_scenario(sc2, tmp_path / "out2", None, False, False, False))
    assert rep2["verdict"] in {"BLOCK", "FAIL"}   # 連不上時 goto 先失敗；連得上時被擋
