"""反證測試 —— ingest 自動 build 鎖定 tokenizer（aidev-agent 回報 F-5）

## 回報的問題（修前這測試必須紅）

- F-5（P2）：ingest 內部呼叫 wiki_index build 時沒帶 --tokenizer（用預設 auto）→
  不同環境 auto 可能 resolve 成不同 mode（jieba vs bigram）→ 與 query 端不一致，
  每查必 TOKENIZER_MISMATCH、index_used:false，靠 L0 全文兜底。

修法：ingest 加 --tokenizer，run_index_build 透傳給 wiki_index build --tokenizer，
使 build/query 分詞一致。
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import wiki_ingest  # noqa: E402


class _FakeProc:
    def __init__(self, rc=0):
        self.returncode = rc
        self.stdout = "{}"
        self.stderr = ""


def test_tokenizer_passed_through_to_index_build(tmp_path, monkeypatch):
    """指定 --tokenizer bigram → run_index_build 的子進程 cmd 應含 --tokenizer bigram。"""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc(0)

    monkeypatch.setattr(wiki_ingest.subprocess, "run", fake_run)
    ok, err = wiki_ingest.run_index_build(tmp_path / "wiki", tokenizer="bigram")
    assert ok is True and err is None
    cmd = captured["cmd"]
    assert "--tokenizer" in cmd, f"子進程 cmd 應含 --tokenizer；cmd={cmd}"
    i = cmd.index("--tokenizer")
    assert cmd[i + 1] == "bigram", f"--tokenizer 值應為 bigram；cmd={cmd}"


def test_no_tokenizer_means_no_flag(tmp_path, monkeypatch):
    """未指定 tokenizer（None/空）→ 不加 --tokenizer，交 wiki_index 用預設 auto。"""
    captured = {}

    def fake_run2(cmd, **k):
        captured["cmd"] = cmd
        return _FakeProc(0)

    monkeypatch.setattr(wiki_ingest.subprocess, "run", fake_run2)
    wiki_ingest.run_index_build(tmp_path / "wiki", tokenizer=None)
    assert "--tokenizer" not in captured["cmd"], f"未指定時不該加 --tokenizer；cmd={captured['cmd']}"


def test_index_build_failure_captures_stderr(tmp_path, monkeypatch):
    """build 失敗 → 回 (False, stderr 內容)，不靜默。"""
    def fail_run(cmd, **k):
        p = _FakeProc(1)
        p.stderr = "TOKENIZER_MISMATCH: build=jieba query=bigram"
        return p
    monkeypatch.setattr(wiki_ingest.subprocess, "run", fail_run)
    ok, err = wiki_ingest.run_index_build(tmp_path / "wiki", tokenizer="jieba")
    assert ok is False
    assert err and "TOKENIZER_MISMATCH" in err, f"應接住 stderr；err={err}"
