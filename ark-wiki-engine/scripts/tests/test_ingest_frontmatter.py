"""反證測試 —— wiki_ingest.build_wiki_page 對 raw frontmatter 的處置（aibi-agent 回報）

## 兩個回報的 bug（修前這些測試必須紅）

- P0 trust：ingest 產出頁預設 `trust: deterministic` + `approved: true`，
  違反 BRAIN.md「LLM/agent 蒸餾內容一律 llm-distilled + approved: false + status: seedling」。
- P1 tags/type：build_wiki_page 無視 raw 的 frontmatter tags/type，
  改用 CATEGORY_KEYWORDS substring 硬湊 tags（CJK 內容湊不到、截斷）、detect_type 猜 type。

修法：build_wiki_page 先 parse raw frontmatter，raw 有 tags/type 就沿用；trust 預設 llm-distilled。
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

from _wikilib import parse_frontmatter  # noqa: E402
from wiki_ingest import build_wiki_page  # noqa: E402

# 帶完整 frontmatter 的 raw（模擬 aibi 的 bq-table 素材）
RAW_WITH_FM = """---
title: "BQ 資料表清單"
type: entity
tags: [bq-table, activity, config]
---

# BQ 資料表清單

活動設定表與通路清單，架構如下。
"""


def _make_raw(tmp_path: Path) -> Path:
    d = tmp_path / "raw" / "bq"
    d.mkdir(parents=True)
    f = d / "bq-tables.md"
    f.write_text(RAW_WITH_FM, encoding="utf-8")
    return f


def test_trust_defaults_to_llm_distilled_not_approved(tmp_path):
    """P0：ingest 產出頁 trust 應為 llm-distilled、approved false、status seedling。"""
    src = _make_raw(tmp_path)
    page = build_wiki_page(src, "bq-tables", "bq", src.read_text(encoding="utf-8"), tmp_path)
    fm = parse_frontmatter(page)
    assert fm.get("trust") == "llm-distilled", f"trust={fm.get('trust')}（不該是 deterministic）"
    assert str(fm.get("approved")).lower() == "false", f"approved={fm.get('approved')}（不該 true）"
    assert fm.get("status") == "seedling", f"status={fm.get('status')}"


def test_raw_tags_are_preserved_not_substring_matched(tmp_path):
    """P1：raw 有 tags 就沿用，不被 CATEGORY_KEYWORDS 硬湊/截斷。"""
    src = _make_raw(tmp_path)
    page = build_wiki_page(src, "bq-tables", "bq", src.read_text(encoding="utf-8"), tmp_path)
    tags = parse_frontmatter(page).get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    assert "bq-table" in tags and "activity" in tags and "config" in tags, f"tags={tags}（raw 的 tags 遺失）"


def test_raw_type_is_preserved_not_detected(tmp_path):
    """P1：raw 有 type 就沿用，不被 detect_type 改寫。"""
    src = _make_raw(tmp_path)
    page = build_wiki_page(src, "bq-tables", "bq", src.read_text(encoding="utf-8"), tmp_path)
    assert parse_frontmatter(page).get("type") == "entity", "type 被 detect_type 誤改（應沿用 raw 的 entity）"
