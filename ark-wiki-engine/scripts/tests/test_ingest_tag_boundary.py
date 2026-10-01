"""反證測試 —— wiki_ingest tag fallback 的詞邊界比對（aidev-agent 回報 F-2）

## 回報的問題（修前這些測試必須紅）

- F-2（P1）：raw 無 tags 時走 CATEGORY_KEYWORDS fallback，用 `kw.lower() in content.lower()`
  子字串命中 → 檔名引用（`-sop.md` 的 "sop"）、說明文字（"摘要"/"踩坑"）被誤抽成 tag。

修法：fallback 關鍵字命中改詞邊界比對 —— 英文/數字詞用 \b 詞邊界、
且只掃正文（排除檔名污染）。

注意：F-1 已讓 raw 有 tags 時直接沿用，所以本測試的 raw **不帶 frontmatter tags**，
才會走到 fallback 路徑。
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

from _wikilib import parse_frontmatter  # noqa: E402
from wiki_ingest import build_wiki_page  # noqa: E402


def _tags_of(page: str) -> list[str]:
    tags = parse_frontmatter(page).get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    return tags


def test_english_keyword_requires_word_boundary(tmp_path):
    """英文關鍵字 'api' 不該因子字串（如 'apiary'/'rapid'）被誤抽。

    raw 無 frontmatter → 走 fallback。內文只有 'rapid prototyping'（含 'api' 子字串）
    但沒有獨立的 'api' 詞 → 不該抽出 'api'。
    """
    src = tmp_path / "raw"
    src.mkdir()
    f = src / "notes.md"
    f.write_text("# 筆記\n\nrapid prototyping 的流程說明。\n", encoding="utf-8")
    page = build_wiki_page(f, "notes", "", f.read_text(encoding="utf-8"), tmp_path)
    assert "api" not in _tags_of(page), f"'api' 被子字串誤抽（rapid 內的 api）；tags={_tags_of(page)}"


def test_filename_sop_not_leaked_into_tags(tmp_path):
    """檔名含 'sop' 不該讓 'SOP' 關鍵字被抽成 tag（檔名污染）。

    raw 無 frontmatter、內文不含 SOP 詞 → tags 不該有 operations 的 'SOP'。
    """
    src = tmp_path / "raw"
    src.mkdir()
    f = src / "competitor-analysis-sop.md"
    f.write_text("# 競品分析\n\n這是一份競品比較報告。\n", encoding="utf-8")
    page = build_wiki_page(f, "competitor-analysis-sop", "",
                           f.read_text(encoding="utf-8"), tmp_path)
    assert "SOP" not in _tags_of(page), f"檔名的 sop 洩漏成 tag；tags={_tags_of(page)}"


def test_cjk_explanatory_word_not_abused(tmp_path):
    """說明文字裡的 '摘要'/'踩坑' 不該被當 tag 抽出。

    這些是 meetings/learnings 分類的關鍵字，但出現在說明語境（非主題）→ 誤抽。
    改法：fallback 只掃正文主體，CJK 關鍵字命中後仍可留（CJK 整詞已精準），
    但本案驗的是『不因檔名/說明雜訊誤抽』—— 內文確實沒有討論會議紀錄或踩坑主題。
    """
    src = tmp_path / "raw"
    src.mkdir()
    f = src / "doc.md"
    # 內文主題是「資料表結構」，只在一句說明裡提到「摘要」二字
    f.write_text("# 資料表\n\n以下為資料表結構。本頁為內容摘要。\n", encoding="utf-8")
    page = build_wiki_page(f, "doc", "", f.read_text(encoding="utf-8"), tmp_path)
    # 「摘要」出現在說明語境，不是頁面主題 → 不該被當成分類 tag
    assert "摘要" not in _tags_of(page), f"說明詞『摘要』被誤抽成 tag；tags={_tags_of(page)}"


def test_legit_english_keyword_still_matched(tmp_path):
    """回歸：合法的獨立英文關鍵字（有詞邊界）仍要能抽出。

    內文有獨立的 'architecture' 詞 → fallback 應抽出 'architecture'。
    """
    src = tmp_path / "raw"
    src.mkdir()
    f = src / "sys.md"
    f.write_text("# 系統\n\nThis document describes the system architecture in detail.\n",
                 encoding="utf-8")
    page = build_wiki_page(f, "sys", "", f.read_text(encoding="utf-8"), tmp_path)
    assert "architecture" in _tags_of(page), f"合法關鍵字 architecture 應被抽出；tags={_tags_of(page)}"
