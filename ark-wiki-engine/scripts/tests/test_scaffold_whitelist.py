"""反證測試 —— build_wiki 新手骨架的 tags 白名單（nana 2026-10-05 回報）

## 回報的問題（修前這些測試必須紅）

新手跟著 SKILL 範例走：`build_wiki.py` 建骨架 → 帶 `--schema` ingest 第一篇文章。
但骨架 schema 的「## tags 白名單」原本只有 `- overview` 一個 tag →
任何帶常見 tag（note/howto/concept…）的頁面首次 ingest 必被 `TAG_NOT_IN_WHITELIST` 擋下，
而此時使用者還沒有任何 tag 可 approve → 死路（新手首次必卡）。

修法：build_wiki 的 _schema_md 白名單預帶一組通用基礎 tags
（overview/concept/reference/note/howto/tool/methodology），讓新手首次 ingest 能通過。
治理需求出現時再用 propose/approve 收窄或擴充。
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import wiki_taxonomy  # noqa: E402
from build_wiki import _schema_md  # noqa: E402
from wiki_ingest import ingest_file  # noqa: E402


# 新手骨架白名單至少該涵蓋的通用 tags
BASELINE_TAGS = {"overview", "concept", "reference", "note", "howto", "tool", "methodology"}


def _write_schema(tmp_path: Path) -> Path:
    """用 build_wiki 的 _schema_md 產出骨架 schema，模擬新手剛 build 完的狀態。"""
    schema = tmp_path / "schema.md"
    schema.write_text(_schema_md("測試知識庫"), encoding="utf-8")
    return schema


def test_scaffold_whitelist_covers_common_tags(tmp_path):
    """build_wiki 產的骨架白名單應涵蓋通用基礎 tags（修前只有 overview → 紅）。"""
    schema = _write_schema(tmp_path)
    wl = wiki_taxonomy.load_whitelist(schema)
    missing = BASELINE_TAGS - wl
    assert not missing, f"骨架白名單缺少通用 tags：{sorted(missing)}；實際={sorted(wl)}"


def test_scaffold_whitelist_not_empty(tmp_path):
    """骨架白名單不可為空（空集合 = fail-closed 擋下所有 ingest）。"""
    schema = _write_schema(tmp_path)
    wl = wiki_taxonomy.load_whitelist(schema)
    assert len(wl) >= 3, f"骨架白名單過少（{sorted(wl)}）→ 新手首次 ingest 幾乎必被擋"


def test_newbie_first_ingest_passes_with_common_tags(tmp_path):
    """端到端：新手帶常見 tag 的首篇文章，用骨架 schema ingest 應通過（非 blocked）。

    修前白名單只有 overview → 帶 [note, howto] 的頁面會回 TAG_NOT_IN_WHITELIST（紅）。
    修後 note/howto 在白名單 → 應成功落盤。
    """
    schema = _write_schema(tmp_path)
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    raw = tmp_path / "raw"
    raw.mkdir()
    src = raw / "my-first-note.md"
    src.write_text(
        "---\n"
        "title: 我的第一篇筆記\n"
        "type: note\n"
        "tags: [note, howto]\n"
        "created: 2026-10-05\n"
        "updated: 2026-10-05\n"
        "---\n\n"
        "# 我的第一篇筆記\n\n這是新手跟著教學丟進來的第一篇文章。\n",
        encoding="utf-8",
    )
    result = ingest_file(src, wiki_dir, "", "my-first-note", False, schema=schema)
    assert result.get("status") != "blocked", (
        f"新手首次 ingest 被擋：{result.get('code')} unknown={result.get('unknown_tags')}"
    )
