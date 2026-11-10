"""反證測試 —— wiki_lint 孤立頁判定把 frontmatter `related:` 雙向計入（3.2.0，kiro-bot 2026-11-10 回報）

## 回報的問題

kiro-bot 櫃 `2026-11-09-agent-backend-model-reorg` 在 `related:` 宣告與改名頁相關、內文也有 [[改名頁]]，
lint 仍報它孤立 —— 舊判定只看「別人內文有沒有 [[我]]」，而補一行連結要手寫 wiki（禁止）、
ingest 又會跳過既有頁，沒有合法修法。

「相關」是對稱關係：A 宣告與 B 相關，A、B 都不該算孤立。但有兩個邊界不能放：
1. `overview` 不給雙向分 —— ingest 預設 `related: [overview]`，算進去等於孤立偵測全滅
2. related 指向不存在的頁不給分 —— 不能宣告一個 red link 就脫離孤立
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wiki_lint import lint_wiki  # noqa: E402


def _page(wiki: Path, name: str, related: str, body: str = "") -> None:
    (wiki / f"{name}.md").write_text(
        f"---\ntitle: \"{name}\"\ntype: concept\ntags: [a]\nsources: [raw/x.md]\n"
        f"related: [{related}]\ncreated: 2026-11-10\nupdated: 2026-11-10\nstatus: seedling\n"
        f"trust: deterministic\napproved: false\n---\n\n# {name}\n{body}\n", encoding="utf-8")


def _orphans(wiki: Path) -> set[str]:
    res = lint_wiki(wiki)
    return {Path(w["file"]).stem for w in res["warnings"] if "孤立" in w["msg"]}


def test_related_counts_both_directions(tmp_path):
    """A related B（無任何 wikilink）→ A、B 都不孤立。"""
    _page(tmp_path, "a", "b")
    _page(tmp_path, "b", "overview")
    assert _orphans(tmp_path) == set()


def test_overview_related_does_not_rescue(tmp_path):
    """邊界 1：只 related overview（ingest 預設值）且 overview 存在 → 仍孤立。"""
    _page(tmp_path, "overview", "overview")
    _page(tmp_path, "lonely", "overview")
    assert _orphans(tmp_path) == {"lonely"}


def test_related_to_missing_page_does_not_rescue(tmp_path):
    """邊界 2：related 指向不存在的頁 → 宣告者仍孤立。"""
    _page(tmp_path, "lonely", "ghost-page")
    assert _orphans(tmp_path) == {"lonely"}


def test_self_related_does_not_rescue(tmp_path):
    _page(tmp_path, "lonely", "lonely")
    assert _orphans(tmp_path) == {"lonely"}


def test_wikilink_style_related_value(tmp_path):
    """related 寫成 [[b|顯示]] 也要認得（ingest 會原樣保留 raw 的 wikilink 錨點）。"""
    (tmp_path / "a.md").write_text(
        "---\ntitle: a\ntype: concept\ntags: [a]\nsources: [raw/x.md]\nrelated:\n  - \"[[b|B 頁]]\"\n"
        "created: 2026-11-10\nupdated: 2026-11-10\nstatus: seedling\ntrust: deterministic\napproved: false\n---\n",
        encoding="utf-8")
    _page(tmp_path, "b", "overview")
    assert _orphans(tmp_path) == set()


def test_plain_wikilink_behaviour_unchanged(tmp_path):
    """舊行為：內文 [[b]] 讓 b 不孤立，但 a 自己仍孤立（沒人連它、也沒 related 關聯）。"""
    _page(tmp_path, "a", "overview", body="見 [[b]]")
    _page(tmp_path, "b", "overview")
    assert _orphans(tmp_path) == {"a"}
