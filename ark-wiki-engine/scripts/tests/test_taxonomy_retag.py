"""反證測試 —— wiki_taxonomy retag（kiro-bot 2026-11-10 回報）

## 回報的問題

白名單建好後，存量頁的 tag 沒有合法的修法：
- wiki 禁手寫；而 raw → ingest 遇既有頁回 `already_exists` 跳過，且只產「待填骨架」
  → 想靠重新 ingest 改 tag 只能先刪頁，整理過的內容會被換成空章節。

retag 的契約（每條都有測試釘住）：
1. 只改 frontmatter 的 `tags:`，其餘位元組（內文、BOM、CRLF）原封不動
2. 對照目標必須已在白名單 —— 不能變成繞過受控詞彙的後門；不合法時一個檔都不改
3. dry_run 不寫檔、不寫 log
4. 每頁變更記進 log.md（稽核軌跡，與 approve 平行）
5. 對照後 tags 會變空 → 跳過該頁並 exit 1，不留下無 tag 的頁
6. 有殘留未知 tag → exit 1（看得出「還沒修完」，不假裝通過）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
TAXONOMY = SCRIPTS / "wiki_taxonomy.py"

SCHEMA = "## tags 白名單\n\n- architecture\n- kiro-cli\n- install\n\n# Schema\n"
BODY = "\n# 標題\n\n內文 第一行\n- 這行不是 tags\ntags: [不是 frontmatter]\n"


def _run(*args):
    r = subprocess.run([sys.executable, str(TAXONOMY), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout, r.stderr


def _setup(tmp_path: Path, pages: dict[str, bytes]) -> tuple[Path, Path]:
    kb = tmp_path / "kb"
    wiki = kb / "wiki"
    wiki.mkdir(parents=True)
    (kb / "schema.md").write_text(SCHEMA, encoding="utf-8")
    for name, data in pages.items():
        p = wiki / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return kb / "schema.md", wiki


def _page(tags_line: str, *, nl: str = "\n", bom: bool = False) -> bytes:
    text = f"---{nl}title: \"T\"{nl}{tags_line}{nl}status: seedling{nl}---{nl}" + BODY.replace("\n", nl)
    return (b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8")


def _retag(schema: Path, wiki: Path, *extra: str):
    rc, out, err = _run("retag", "--schema", str(schema), "--wiki_dir", str(wiki),
                        "--no-index", "--json", "--by", "qa-agent", *extra)
    return rc, json.loads(out), err


def test_only_tags_line_changes_body_bytes_identical(tmp_path):
    """契約 1：內文（含像 tags 的假行）逐位元組不變。"""
    orig = _page("tags: [cli, architecture]")
    schema, wiki = _setup(tmp_path, {"a.md": orig})
    rc, payload, err = _retag(schema, wiki, "--map", "cli=kiro-cli")
    assert rc == 0, (payload, err)
    new = (wiki / "a.md").read_bytes()
    assert new == orig.replace(b"tags: [cli, architecture]", b"tags: [kiro-cli, architecture]")
    assert payload["changed"] == [{"page": "a.md", "before": ["cli", "architecture"],
                                   "after": ["kiro-cli", "architecture"]}]


def test_preserves_crlf_and_bom(tmp_path):
    """契約 1：CRLF 與 BOM 不得被轉掉（Python 文字模式預設會把 CRLF 轉 LF）。"""
    orig = _page("tags: ['cli', 'install']", nl="\r\n", bom=True)
    schema, wiki = _setup(tmp_path, {"sub/b.md": orig})
    rc, payload, _ = _retag(schema, wiki, "--map", "cli=kiro-cli")
    assert rc == 0, payload
    new = (wiki / "sub" / "b.md").read_bytes()
    assert new.startswith(b"\xef\xbb\xbf---\r\n"), new[:20]
    assert new.count(b"\r\n") == orig.count(b"\r\n")
    assert b"tags: [kiro-cli, install]\r\n" in new


def test_block_list_tags(tmp_path):
    orig = b"---\ntitle: T\ntags:\n  - cli\n  - architecture\nstatus: seedling\n---\n\nbody\n"
    schema, wiki = _setup(tmp_path, {"c.md": orig})
    rc, payload, _ = _retag(schema, wiki, "--map", "cli=kiro-cli")
    assert rc == 0, payload
    assert (wiki / "c.md").read_bytes() == orig.replace(b"  - cli\n", b"  - kiro-cli\n")


def test_map_target_must_be_whitelisted_and_nothing_written(tmp_path):
    """契約 2：對照到未核准 tag → exit 2、不改任何檔，訊息要說怎麼修。"""
    orig = _page("tags: [cli]")
    schema, wiki = _setup(tmp_path, {"a.md": orig})
    rc, payload, _ = _retag(schema, wiki, "--map", "cli=brand-new")
    assert rc == 2
    assert payload["ok"] is False
    assert any("propose" in d for d in payload["details"]), payload
    assert (wiki / "a.md").read_bytes() == orig
    assert not (schema.parent / "log.md").exists()


def test_dry_run_writes_nothing(tmp_path):
    """契約 3。"""
    orig = _page("tags: [cli]")
    schema, wiki = _setup(tmp_path, {"a.md": orig})
    rc, payload, _ = _retag(schema, wiki, "--map", "cli=kiro-cli", "--dry_run")
    assert rc == 0 and payload["dry_run"] is True and len(payload["changed"]) == 1
    assert (wiki / "a.md").read_bytes() == orig
    assert not (schema.parent / "log.md").exists()


def test_log_records_each_change(tmp_path):
    """契約 4。"""
    schema, wiki = _setup(tmp_path, {"a.md": _page("tags: [cli]"), "b.md": _page("tags: [install]")})
    rc, _, _ = _retag(schema, wiki, "--map", "cli=kiro-cli")
    assert rc == 0
    log = (schema.parent / "log.md").read_text(encoding="utf-8")
    assert "| retag | `a.md` | qa-agent | cli → kiro-cli" in log
    assert "b.md" not in log, "沒變的頁不該記 log"


def test_would_empty_is_skipped_and_red(tmp_path):
    """契約 5：不留下沒有 tag 的頁。"""
    orig = _page("tags: [架構]")
    schema, wiki = _setup(tmp_path, {"a.md": orig})
    rc, payload, _ = _retag(schema, wiki, "--map", "架構=")
    assert rc == 1
    assert payload["skipped"][0]["reason"] == "would_empty"
    assert (wiki / "a.md").read_bytes() == orig


def test_residual_unknown_is_red_then_drop_unknown_is_green(tmp_path):
    """契約 6：有殘留就紅；加 --drop-unknown 移除後轉綠（同一組資料兩個方向）。"""
    schema, wiki = _setup(tmp_path, {"a.md": _page("tags: [architecture, query-path]")})
    rc, payload, _ = _retag(schema, wiki, "--dry_run")
    assert rc == 1 and payload["residual"] == [{"page": "a.md", "unknown": ["query-path"]}]
    rc, payload, _ = _retag(schema, wiki, "--drop-unknown")
    assert rc == 0, payload
    assert b"tags: [architecture]\n" in (wiki / "a.md").read_bytes()


def test_dedupes_after_mapping(tmp_path):
    schema, wiki = _setup(tmp_path, {"a.md": _page("tags: [架構, architecture]")})
    rc, payload, _ = _retag(schema, wiki, "--map", "架構=architecture")
    assert rc == 0
    assert payload["changed"][0]["after"] == ["architecture"]


def test_skips_index_and_log_pages(tmp_path):
    schema, wiki = _setup(tmp_path, {"index.md": _page("tags: [cli]"), "log.md": _page("tags: [cli]")})
    rc, payload, _ = _retag(schema, wiki, "--map", "cli=kiro-cli")
    assert rc == 0 and payload["changed"] == []
