"""反證測試 —— wiki_ingest index build 失敗時的狀態/exit code（aidev-agent 回報 F-3）

## 回報的問題（修前這些測試必須紅）

- F-3（P1）：index build 子進程失敗時 `index_built=false`，但 payload 仍 `ok:true`、
  exit 0 → 成功 ingest 但索引靜默沒建，下游程式化判斷誤判為完全成功。

修法：區分 ok / partial / blocked 三態 ——
  partial（落盤成功但索引失敗）→ ok:false, exit 3, 帶 index_error。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import wiki_ingest  # noqa: E402


def _setup_kb(tmp_path: Path) -> tuple[Path, Path]:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    raw = tmp_path / "raw" / "local"
    raw.mkdir(parents=True)
    (tmp_path / "index.md").write_text("# 索引\n\n", encoding="utf-8")
    (tmp_path / "log.md").write_text("# 日誌\n\n", encoding="utf-8")
    src = raw / "clean.md"
    src.write_text("---\ntitle: \"測試頁\"\ntype: concept\ntags: [prob-method]\n---\n\n"
                   "# 測試頁\n\n乾淨內容。\n", encoding="utf-8")
    return wiki, src


def _run_main(monkeypatch, argv, capsys):
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as e:
        wiki_ingest.main()
    out = capsys.readouterr().out
    return e.value.code, out


def test_index_build_failure_returns_partial_not_ok(tmp_path, monkeypatch, capsys):
    """index build 失敗 → status=partial, ok:false, exit 3, 帶 index_error。"""
    wiki, src = _setup_kb(tmp_path)
    # 強制 index build 失敗
    monkeypatch.setattr(wiki_ingest, "run_index_build",
                        lambda *a, **k: (False, "模擬 build 失敗：磁碟錯誤"))
    code, out = _run_main(monkeypatch,
                          ["wiki_ingest.py", "--source", str(src), "--wiki_dir", str(wiki), "--json"],
                          capsys)
    payload = json.loads(out)
    assert payload["created"] == 1, "頁面應已落盤"
    assert payload["ok"] is False, "索引失敗時 ok 不該是 true（修前的 bug）"
    assert payload["status"] == "partial", f"應為 partial，得 {payload.get('status')}"
    assert payload["index_built"] is False
    assert "index_error" in payload and payload["index_error"], "應回報 index_error 原因（不靜默）"
    assert code == 3, f"partial 應 exit 3，得 {code}"


def test_full_success_returns_ok_exit_0(tmp_path, monkeypatch, capsys):
    """index build 成功 → status=ok, ok:true, exit 0。"""
    wiki, src = _setup_kb(tmp_path)
    monkeypatch.setattr(wiki_ingest, "run_index_build", lambda *a, **k: (True, None))
    code, out = _run_main(monkeypatch,
                          ["wiki_ingest.py", "--source", str(src), "--wiki_dir", str(wiki), "--json"],
                          capsys)
    payload = json.loads(out)
    assert payload["ok"] is True and payload["status"] == "ok"
    assert payload["index_built"] is True
    assert "index_error" not in payload
    assert code == 0, f"全成功應 exit 0，得 {code}"
