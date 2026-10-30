"""ark-telegram-sender 行為測試：逸出判準、長度裁切、目標解析、Bot API 錯誤語意。

不打網路 —— `urllib.request.urlopen` 一律 monkeypatch 成假的回應，`time.sleep` 也換掉以免重試拖慢測試。
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tg_send  # noqa: E402


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def fake_api(monkeypatch):
    """把 urlopen 換成記錄 payload 的假 API；`responses` 可塞入例外或回應 dict。"""
    calls: list[dict] = []
    responses: list = []

    def urlopen(req, timeout=0):
        body = req.data
        calls.append({"url": req.full_url,
                      "payload": json.loads(body) if req.headers.get("Content-type") == "application/json" else body})
        r = responses.pop(0) if responses else {"ok": True, "result": {"message_id": len(calls)}}
        if isinstance(r, Exception):
            raise r
        return _Resp(json.dumps(r).encode())

    monkeypatch.setattr(tg_send.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(tg_send.time, "sleep", lambda s: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TEST:TOKEN")
    return calls, responses


def _http_error(code: int, body: dict) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.telegram.org/x", code, "Bad", {}, io.BytesIO(json.dumps(body).encode()))


# ── 逸出 ──────────────────────────────────────────────


def test_apply_escape_auto_keeps_tg_html_but_escapes_plain_text():
    """auto：含 Telegram 認得的標籤 → 原樣；純文字裡的 `<`、`&` → 逸出（否則 TG 回 400）。"""
    assert tg_send.apply_escape("<b>日報</b> 1 < 2", "auto") == "<b>日報</b> 1 < 2"
    assert tg_send.apply_escape("營收 1 < 2 & 3 > 0", "auto") == "營收 1 &lt; 2 &amp; 3 &gt; 0"
    assert tg_send.apply_escape("<div>非 TG 標籤</div>", "auto") == "&lt;div&gt;非 TG 標籤&lt;/div&gt;"
    assert tg_send.apply_escape("<b>x</b>", "always") == "&lt;b&gt;x&lt;/b&gt;"
    assert tg_send.apply_escape("a < b", "never") == "a < b"


# ── 長度裁切（dry-run，不需 token）─────────────────────


def _long_text(paragraphs: int = 30, size: int = 190) -> str:
    return "\n\n".join(f"<b>第{i}段</b> " + "字" * size for i in range(paragraphs))


def test_truncate_cuts_at_paragraph_boundary_and_appends_note():
    """預設 truncate：超長只送一則、≤ 4000 字、切在段落邊界（標籤不被切開）、附截斷註記。"""
    r = tg_send.send_text(_long_text(), chat_id=1, dry_run=True)
    assert r["status"] == "dry_run" and r["parts"] == 1
    assert r["chars"][0] <= tg_send.TEXT_LIMIT
    text, _ = tg_send._fit(_long_text(), "truncate")
    body = text[0].rsplit("\n\n<i>", 1)[0]
    assert body.count("<b>") == body.count("</b>")
    assert text[0].endswith("內容過長已截斷</i>")


def test_split_preserves_all_paragraphs_within_limit():
    """split：每則 ≤ 上限，且所有段落都送得出去（不可遺失內容）。"""
    src = _long_text()
    chunks, mode = tg_send._fit(src, "split")
    assert mode == "split" and len(chunks) >= 2
    assert all(len(c) <= tg_send.TEXT_LIMIT for c in chunks)
    joined = "\n\n".join(chunks)
    assert all(f"<b>第{i}段</b>" in joined for i in range(30))


def test_overflow_error_mode_and_exact_limit_boundary():
    """邊界：剛好 4000 字不算超長；4001 字在 on_overflow=error 時回錯誤而非送出。"""
    assert tg_send.send_text("a" * tg_send.TEXT_LIMIT, chat_id=1, on_overflow="error", dry_run=True)["parts"] == 1
    r = tg_send.send_text("a" * (tg_send.TEXT_LIMIT + 1), chat_id=1, on_overflow="error", dry_run=True)
    assert r["status"] == "error" and "超過上限" in r["message"]


# ── 目標解析 ──────────────────────────────────────────


def test_resolve_target_from_team_yaml_and_unknown_topic(tmp_path, monkeypatch):
    """topic 走 team.yaml（group_id + thread + token_env）；未知 topic 要報錯並列出可用清單。"""
    y = tmp_path / "team.yaml"
    y.write_text("channel:\n  group_id: -100123\n  bot_token_env: TG_GA  # ninja\n"
                 "topics:\n  daily_report: 42\n  alerts: 7\n", encoding="utf-8")
    assert tg_send.resolve_target(topic="daily_report", team_yaml=y) == (-100123, 42, "TG_GA")
    with pytest.raises(ValueError, match=r"alerts.*daily_report"):
        tg_send.resolve_target(topic="nope", team_yaml=y)
    # 沒裝 PyYAML 時的極簡解析也要給出同樣結果（行尾註解要去掉）
    assert tg_send._minimal_yaml(y.read_text(encoding="utf-8")) == {
        "channel": {"group_id": -100123, "bot_token_env": "TG_GA"},
        "topics": {"daily_report": 42, "alerts": 7},
    }
    # 由 cwd 往上找 team.yaml
    sub = tmp_path / "agents" / "a"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    assert tg_send.resolve_target(topic="alerts")[1] == 7


def test_cli_no_target_exits_nonzero_only_with_raise_on_error(monkeypatch, capsys):
    """反例：沒有任何發送目標 → JSON 回 error；加 --raise-on-error 時 exit 1（給排程判斷失敗）。"""
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert tg_send.main(["text", "--text", "hi", "--dry-run"]) == 0
    assert tg_send.main(["text", "--text", "hi", "--dry-run", "--raise-on-error"]) == 1
    out = capsys.readouterr().out
    assert "未指定發送目標" in out


# ── Bot API 呼叫（mock urlopen）──────────────────────


def test_send_text_success_payload_has_thread_id(fake_api):
    """正常路徑：payload 帶 chat_id + message_thread_id + parse_mode，回 message_id。"""
    calls, _ = fake_api
    r = tg_send.send_text("<b>hi</b>", chat_id=-100, thread_id=9)
    assert r["status"] == "success" and r["message_id"] == 1
    p = calls[0]["payload"]
    assert p["chat_id"] == -100 and p["message_thread_id"] == 9 and p["text"] == "<b>hi</b>"
    assert calls[0]["url"].endswith("/botTEST:TOKEN/sendMessage")


def test_http_400_reports_body_description_without_retry(fake_api):
    """反例：400 的原因要從 body 的 description 取出（不是「Bad Request」），且不重試。"""
    calls, responses = fake_api
    responses.append(_http_error(400, {"ok": False, "description": "Bad Request: can't parse entities: Unclosed start tag"}))
    r = tg_send.send_text("<b>x", chat_id=1, escape="never")
    assert r["status"] == "error" and r["http_status"] == 400
    assert "Unclosed start tag" in r["message"]
    assert len(calls) == 1


def test_http_429_retries_then_succeeds(fake_api):
    """429 依 retry_after 等待後重試，第二次成功即回 success。"""
    calls, responses = fake_api
    responses.append(_http_error(429, {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 1}}))
    r = tg_send.send_text("hi", chat_id=1)
    assert r["status"] == "success" and len(calls) == 2


def test_send_file_missing_and_oversize(tmp_path, monkeypatch):
    """反例：檔案不存在／超過 50 MB 都要在送出前擋下並說明原因。"""
    assert "檔案不存在" in tg_send.send_file(tmp_path / "nope.html", chat_id=1)["message"]
    f = tmp_path / "big.bin"
    f.write_bytes(b"x")
    monkeypatch.setattr(tg_send, "FILE_LIMIT_BYTES", 0)
    assert "超過 Bot API 上限" in tg_send.send_file(f, chat_id=1)["message"]


@pytest.mark.xfail(strict=True, reason="BUG：--parse-mode plain 原樣送出 parse_mode='plain'，"
                   "Telegram 不認得此值會回 400；plain 應省略 parse_mode 欄位")
def test_plain_parse_mode_is_not_sent_to_api(fake_api):
    """SKILL.md 列 `plain` 為合法 parse_mode；送到 API 時不該帶 Telegram 不支援的值。"""
    calls, _ = fake_api
    tg_send.send_text("1 < 2", chat_id=1, parse_mode="plain")
    assert calls[0]["payload"].get("parse_mode") in (None, "")
