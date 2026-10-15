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


# raw title 與 H1 刻意不同，才能驗證「沿用 frontmatter title」而非「抓第一個 #」
RAW_TITLE_DIFFERS = """---
title: "活動設定表權威清單"
type: entity
tags: [bq-table, activity, config]
---

# 內文用的另一個標題

說明文字。
"""


def test_raw_title_is_preserved_not_from_h1(tmp_path):
    """殘留修正：raw 有 title 就沿用，不被內文第一個 # 標題覆寫（aibi-agent 回報殘留）。"""
    d = tmp_path / "raw" / "bq"
    d.mkdir(parents=True)
    src = d / "activity.md"
    src.write_text(RAW_TITLE_DIFFERS, encoding="utf-8")
    page = build_wiki_page(src, "activity", "bq", src.read_text(encoding="utf-8"), tmp_path)
    assert parse_frontmatter(page).get("title") == "活動設定表權威清單", (
        "title 被內文 H1 覆寫（應沿用 raw frontmatter 的 title）"
    )


# raw 帶 [[wikilink]] 錨點，驗證不被骨架硬寫的 overview 覆蓋
RAW_WITH_RELATED = """---
title: "虎機 k8s 發布"
type: pipeline
tags: [devops, k8s]
related: [[GoldenHoyeahServer-DevOps]]
---

# 虎機 k8s 發布

內容。
"""


def test_raw_related_anchor_is_preserved_not_overwritten(tmp_path):
    """殘留修正：raw 的 related [[wikilink]] 錨點應沿用，不被骨架硬寫的 [overview] 吃掉。"""
    d = tmp_path / "raw" / "infra"
    d.mkdir(parents=True)
    src = d / "k8s.md"
    src.write_text(RAW_WITH_RELATED, encoding="utf-8")
    page = build_wiki_page(src, "k8s", "infra", src.read_text(encoding="utf-8"), tmp_path)
    assert "GoldenHoyeahServer-DevOps" in page, "related 錨點遺失（被 overwrite 成 overview）"
    rel = parse_frontmatter(page).get("related", [])
    rel_str = ", ".join(str(r) for r in rel) if isinstance(rel, list) else str(rel)
    assert "GoldenHoyeahServer-DevOps" in rel_str, f"related={rel}（錨點未保留）"


def test_related_defaults_to_overview_when_raw_has_none(tmp_path):
    """raw 無 related 時，骨架回退預設 overview（維持原行為）。"""
    src = _make_raw(tmp_path)  # RAW_WITH_FM 無 related
    page = build_wiki_page(src, "bq-tables", "bq", src.read_text(encoding="utf-8"), tmp_path)
    rel = parse_frontmatter(page).get("related", [])
    rel_str = ", ".join(str(r) for r in rel) if isinstance(rel, list) else str(rel)
    assert "overview" in rel_str, f"related={rel}（無 raw related 時應預設 overview）"
