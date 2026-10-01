"""反證測試 —— ingest 寫 log/index 的兩缺陷（slot-bot 回報，問題單 2026-10-01）

兩缺陷同一形狀：寫入稽核/索引時靠字串推斷位置，而非用已算好的真實值。

- 缺陷1：--category 時 log.md 記成 wiki/<page>.md，漏了 category 子目錄（實際在 wiki/<cat>/<page>.md）。
- 缺陷2a：update_index 用子字串比對標題 → `### server` 命中 `### server（3 頁）` 把標題切成兩半。
- 缺陷2b：page_name in content 子字串判「已索引」→ 頁名在內文別處出現過就靜默漏索引。

修前這些測試必須紅。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent


def _ingest(kb: Path, src: Path, *extra):
    cmd = [sys.executable, str(SCRIPTS / "wiki_ingest.py"),
           "--source", str(src), "--wiki_dir", str(kb / "wiki"), "--by", "repro", *extra]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def _kb(tmp: Path) -> Path:
    kb = tmp / "kb"
    (kb / "wiki").mkdir(parents=True)
    (kb / "raw" / "src").mkdir(parents=True)
    (kb / "log.md").write_text("- **2026-01-01** | init | 初始化\n", encoding="utf-8")
    (kb / "schema.md").write_text("## tags 白名單\n\n- server\n", encoding="utf-8")
    return kb


def _raw(kb: Path, name: str, title: str = "Demo") -> Path:
    f = kb / "raw" / "src" / f"{name}.md"
    f.write_text(f'---\ntitle: "{title}"\ntype: source\ntags: [server]\n---\n# {title} 頁\n內容\n', encoding="utf-8")
    return f


# ── 缺陷 1：log 路徑含 category ──────────────────────────────

def test_log_path_includes_category_subdir(tmp_path):
    kb = _kb(tmp_path)
    src = _raw(kb, "demo")
    r = _ingest(kb, src, "--category", "server", "--schema", str(kb / "schema.md"))
    assert r.returncode == 0, r.stderr
    log = (kb / "log.md").read_text(encoding="utf-8")
    assert "`wiki/server/demo.md`" in log, f"log 應記實際落點 wiki/server/demo.md；log=\n{log}"
    assert "`wiki/demo.md`" not in log, "log 不該記漏 category 的 wiki/demo.md"


def test_log_path_without_category_unchanged(tmp_path):
    """不帶 --category 時行為不變：wiki/demo.md。"""
    kb = _kb(tmp_path)
    src = _raw(kb, "demo")
    r = _ingest(kb, src, "--schema", str(kb / "schema.md"))
    assert r.returncode == 0, r.stderr
    log = (kb / "log.md").read_text(encoding="utf-8")
    assert "`wiki/demo.md`" in log, f"無 category 應記 wiki/demo.md；log=\n{log}"


# ── 缺陷 2a：整行比對，不切壞人工標題 ───────────────────────

def test_index_does_not_corrupt_titled_section(tmp_path):
    kb = _kb(tmp_path)
    # index 有人工維護的 `### server（3 頁）` —— 子字串 `### server` 會命中它
    (kb / "index.md").write_text("# 索引\n\n### server（3 頁）\n- [[old]] — 舊頁\n", encoding="utf-8")
    src = _raw(kb, "demo")
    r = _ingest(kb, src, "--category", "server", "--schema", str(kb / "schema.md"))
    assert r.returncode == 0, r.stderr
    idx = (kb / "index.md").read_text(encoding="utf-8")
    # 原標題行必須完好（不被切成 `### server` + 連結 + `（3 頁）`）
    assert "### server（3 頁）" in idx, f"人工標題 `### server（3 頁）` 不該被切壞；index=\n{idx}"
    # demo 必須有被索引（另開 `### server` 新段或其他正確位置）
    assert "[[demo]]" in idx, f"demo 應被索引；index=\n{idx}"


# ── 缺陷 2b：內文提到頁名不影響索引 ─────────────────────────

def test_index_not_skipped_when_pagename_in_prose(tmp_path):
    kb = _kb(tmp_path)
    # index 內文別處提到 demo2 字串（非連結）
    (kb / "index.md").write_text("# 索引\n\n> 參見 demo2 的說明\n\n### server\n", encoding="utf-8")
    src = _raw(kb, "demo2")
    r = _ingest(kb, src, "--category", "server", "--schema", str(kb / "schema.md"))
    assert r.returncode == 0, r.stderr
    idx = (kb / "index.md").read_text(encoding="utf-8")
    assert idx.count("[[demo2]]") == 1, f"demo2 應被索引剛好 1 次（內文提及不算已索引）；index=\n{idx}"
