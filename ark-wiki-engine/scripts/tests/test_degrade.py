"""降級路徑測試 —— 不能只跑 auto（plan §2.1 N-1 / 風險 R-1）

## 為什麼要有這支

`bm25s` / `jieba` 在**某些**解譯器裡是裝好的（本機 `.venv` 有、系統 `python3` 沒有），
所以 `--backend auto` / `--tokenizer auto` 在該環境永遠選較好的那條，
**purepy 與 bigram 兩條降級路徑不會被自然走到**。

MEMORY 記過同型事故：`sync_release_readme()` 的 PUT 路徑「有呼叫點，
只是那次的資料讓它提前 return」→ 發版時才炸。

因此這裡**顯式製造降級條件**（指定 tokenizer / 刪索引 / 假 manifest），
讓兩條路徑在任何解譯器下都必然被執行。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
FIXTURE = SCRIPTS / "tests" / "fixtures" / "wiki"
sys.path.insert(0, str(SCRIPTS))

import _wikilib  # noqa: E402
from _wikilib import ErrorCode, index_dir, tokenize  # noqa: E402


def run(script: str, *args: str) -> tuple[int, dict | str]:
    proc = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                          capture_output=True, text=True)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, proc.stdout


def build(*extra: str) -> dict:
    code, payload = run("wiki_index.py", "build", "--wiki_dir", str(FIXTURE), *extra)
    return payload


def test_bigram_tokenizer_is_actually_exercised():
    """AC: AC-013 — bigram 路徑必然被執行：CJK 切 bigram 而非逐字"""
    toks = tokenize("留存口徑", mode="bigram")
    assert toks == ["留存", "存口", "口徑"], toks
    # v2 是逐字（['留','存','口','徑']）→ 單字 df 幾乎等於文件數，IDF 趨近 0
    assert all(len(t) == 2 for t in toks)


def test_jieba_unavailable_falls_back_in_process(monkeypatch):
    """AC: AC-013 — jieba 不可用時 tokenize 自動退 bigram，不拋例外"""
    monkeypatch.setattr(_wikilib, "jieba_available", lambda: False)
    assert _wikilib.resolve_tokenizer("auto") == "bigram"
    monkeypatch.setitem(sys.modules, "jieba", None)   # import jieba → 取到 None 會壞掉
    toks = tokenize("留存口徑 DAU", mode="jieba")
    assert toks and "留存" in toks                     # 壞掉也要有 token 出來


def test_backend_purepy_only_and_bm25s_rejected():
    """AC: AC-013 — backend 恆為 purepy；--backend bm25s 明確拒絕（W4 才實作）"""
    mf = build()["manifest"]
    assert mf["bm25_backend"] == "purepy"

    code, payload = run("wiki_index.py", "build", "--wiki_dir", str(FIXTURE),
                        "--backend", "bm25s")
    assert code == 2
    assert payload["error"]["code"] == ErrorCode.BAD_ARGUMENTS
    assert "W4" in payload["error"]["msg"]      # 明講「還沒做」而不是靜默當 purepy

    code, out = run("wiki_query.py", "--wiki_dir", str(FIXTURE), "--query", "留存")
    assert out["meta"]["bm25_backend"] == "purepy"


def test_tokenizer_mismatch_warns_and_recomputes():
    """AC: AC-014 — manifest 記 jieba 而查詢端用 bigram → warning + 記憶體重算 + 結果非空"""
    build()
    mfp = index_dir(FIXTURE) / "manifest.json"
    original = mfp.read_text(encoding="utf-8")
    try:
        mf = json.loads(original)
        mf["tokenizer"] = "jieba"       # 假裝索引是用 jieba 建的
        mfp.write_text(json.dumps(mf, ensure_ascii=False), encoding="utf-8")

        code, out = run("wiki_query.py", "--wiki_dir", str(FIXTURE),
                        "--query", "留存口徑", "--tokenizer", "bigram")
        assert code == 0
        assert ErrorCode.TOKENIZER_MISMATCH in out["meta"]["warnings"]
        assert out["meta"]["index_used"] is False       # 不可拿別的分詞建的索引來查
        assert out["meta"]["tokenizer"] == "bigram"
        assert out["results"], "分詞不符時仍必須回答"
        assert out["results"][0]["slug"] == "retention-definition"
    finally:
        mfp.write_text(original, encoding="utf-8")


def test_no_index_at_all_still_answers():
    """AC: AC-014 — 索引完全不存在 → INDEX_MISSING warning，現場掃 frontmatter 仍回答"""
    idx = index_dir(FIXTURE)
    backup = FIXTURE.parent / ".index_backup"
    if backup.exists():
        shutil.rmtree(backup)
    shutil.move(str(idx), str(backup))
    try:
        code, out = run("wiki_query.py", "--wiki_dir", str(FIXTURE), "--query", "留存口徑")
        assert code == 0 and out["ok"] is True
        assert ErrorCode.INDEX_MISSING in out["meta"]["warnings"]
        assert out["meta"]["index_used"] is False
        assert out["results"][0]["slug"] == "retention-definition"   # L0 不依賴索引
        assert "L0" in out["results"][0]["layers"]
    finally:
        if idx.exists():
            shutil.rmtree(idx)
        shutil.move(str(backup), str(idx))


def test_graph_json_missing_falls_back_to_live_parse():
    """AC: AC-014 — graph.json 缺失 → 現場解析 [[wikilink]]，L3 仍作用"""
    build()
    gp = index_dir(FIXTURE) / "graph.json"
    original = gp.read_text(encoding="utf-8")
    gp.unlink()
    try:
        code, out = run("wiki_query.py", "--wiki_dir", str(FIXTURE),
                        "--query", "五層架構", "--top_k", "5")
        assert code == 0
        hit = [r for r in out["results"] if r["slug"] == "graph-only-page"]
        assert hit and hit[0]["layers"] == ["L3"]
    finally:
        gp.write_text(original, encoding="utf-8")
