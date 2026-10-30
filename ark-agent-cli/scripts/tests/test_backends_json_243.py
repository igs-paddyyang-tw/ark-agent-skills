"""2.4.3：codex／gemini 的 json 輸出 —— 夾具是 2026-10-30 真 CLI 實測輸出（codex-cli 0.146、gemini-cli 0.53）。

2.4.2 只對 claude 開 json（另兩家格式未驗證）；本版實測後補齊：回覆文字解包、usage 抽取、gemini headless 需 --skip-trust。
"""
import json
import pathlib
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import agent_cli as A  # noqa: E402
import agent_common as C  # noqa: E402
import agent_worker as W  # noqa: E402

CODEX_JSONL = '{"type":"thread.started","thread_id":"01a18b55-d5d0-7f33-a06a-cd675621fc18"}\n{"type":"turn.started"}\n{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"{\\"status\\":\\"done\\",\\"progress\\":\\"ok\\",\\"actions\\":1}"}}\n{"type":"turn.completed","usage":{"input_tokens":11512,"cached_input_tokens":0,"cache_write_input_tokens":11509,"output_tokens":17,"reasoning_output_tokens":0}}\n'
GEMINI_JSON = '{"session_id": "s", "response": "{\\"status\\":\\"done\\",\\"progress\\":\\"ok\\",\\"actions\\":1}", "stats": {"models": {"gemini-3.1-flash-lite": {"tokens": {"input": 920, "prompt": 920, "candidates": 36, "total": 2251, "cached": 0, "thoughts": 1295, "tool": 0}}, "gemini-3.6-flash": {"tokens": {"input": 8396, "prompt": 8396, "candidates": 13, "total": 8859, "cached": 0, "thoughts": 450, "tool": 0}}}}}'
CP = {"status": "done", "progress": "ok", "actions": 1}


def test_codex_event_stream_unwraps_agent_message_and_usage():
    r = A._finish("codex", CODEX_JSONL, "", 0, 0, True, None)
    assert json.loads(r["text"]) == CP, r["text"]
    assert r["usage"]["input_tokens"] == 11512 and r["usage"]["output_tokens"] == 17


def test_gemini_response_unwrapped_and_usage_summed_across_models():
    r = A._finish("gemini", GEMINI_JSON, "", 0, 0, True, None)
    assert json.loads(r["text"]) == CP
    # router（920＋36＋1295 thoughts）＋ main（8396＋13＋450 thoughts）
    assert r["usage"]["input_tokens"] == 920 + 8396
    assert r["usage"]["output_tokens"] == 36 + 1295 + 13 + 450


def test_worker_checkpoint_fallback_reads_unwrapped_text(tmp_path):
    """read-only 時 checkpoint 只在輸出裡 —— 解包後 worker 的退路才撈得到（不是撈到事件流的第一個 JSON）。"""
    for backend, raw in (("codex", CODEX_JSONL), ("gemini", GEMINI_JSON)):
        r = A._finish(backend, raw, "", 0, 0, True, None)
        cp = W.read_checkpoint(tmp_path / f"{backend}.json", r["text"])
        assert cp and cp["status"] == "done", backend


def test_worker_requests_json_for_all_three():
    assert set(W.JSON_USAGE_BACKENDS) == {"claude", "codex", "gemini"}


def test_gemini_argv_skips_trust_prompt():
    """gemini-cli 0.53 headless 在未信任目錄 exit 55 —— 背景 job 的 cwd 常是新目錄。"""
    argv, _, _ = C.build_argv("gemini", "hi", json_output=True, access="read-only")
    assert "--skip-trust" in argv and "--output-format" in argv
