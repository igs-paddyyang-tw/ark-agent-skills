"""`sources:` 必須正規化成「相對 domain root」的單一形狀。

## 這個 bug 的形狀

`build_wiki_page` 原本是 `rel_source = str(source_path)` ——
**呼叫端給什麼就寫什麼**。於是同一份素材，用不同呼叫方式 ingest
會得到不同的 `sources:`（相對路徑／絕對路徑／不同層級）。

後果不只是難看：下游用 `sources:` 的上游路徑**取交集**判斷「互補型重複」
（兩頁講同一主題但內容互補時相似度反而極低，只有共同上游抓得到）——
形狀不一致的值永遠交集不到。絕對路徑還會綁死某台機器。

> 💡 與 `ark_team_agent.team_mcp` 在 **1.7.26** 修過的是同一個病
> （當時修了 203 頁的 `raw//home/…` 黏合）。
> 通則：**接受多種輸入形狀的入口，輸出必須正規化成一種。**
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wiki_ingest  # noqa: E402


DOMAIN = Path("knowledge/package-dev")
EXPECTED = "raw/local/a.md"


@pytest.mark.parametrize("given", [
    "knowledge/package-dev/raw/local/a.md",          # 相對於 cwd
    "./knowledge/package-dev/raw/local/a.md",        # 帶 ./
    "knowledge/package-dev/./raw/local/a.md",        # 中間有 .
])
def test_relative_forms_normalize_to_one(given):
    """三種相對形狀 → 同一個輸出。

    反證：把 `relative_source` 改回 `str(source_path)` → 這條紅。
    """
    assert wiki_ingest.relative_source(Path(given), DOMAIN) == EXPECTED


def test_absolute_path_is_normalized():
    """🔴 絕對路徑**必須**被正規化 —— 否則 `sources:` 綁死某台機器。

    實例（team 側 1.7.26 修的那批）：有一頁寫著 `/home/user/…`，
    那是在另一台機器上 ingest 的，在本機永遠解析不到。
    """
    abs_path = (Path.cwd() / DOMAIN / "raw/local/a.md")
    assert wiki_ingest.relative_source(abs_path, DOMAIN) == EXPECTED


def test_outside_domain_warns_and_does_not_fabricate(capsys):
    """🔴 素材不在 domain 底下 → **不靜默**：退回檔名並警告。

    那通常代表呼叫端傳錯了 `--wiki_dir`。靜默地寫一個看起來合理的值，
    會讓「傳錯參數」偽裝成「一切正常」。

    反證：把 except 分支改成 `return str(source_path)` 且不印 → 這條紅。
    """
    out = wiki_ingest.relative_source(Path("/tmp/somewhere/else/x.md"), DOMAIN)
    assert out == "x.md", "不該吐出一個看起來像相對路徑的假值"
    assert "domain root" in capsys.readouterr().err


def test_build_wiki_page_uses_normalized_source(tmp_path):
    """端到端：產出的 frontmatter 與內文都用正規化後的路徑。

    🔴 內文也要 —— 舊版把同一個 `rel_source` 同時寫進 `sources:` 與
    「> 萃取自 `…`」，兩處都會帶著未正規化的值。
    """
    domain = tmp_path / "dom"
    (domain / "raw" / "local").mkdir(parents=True)
    src = domain / "raw" / "local" / "note.md"
    src.write_text("# 標題\n\n內容\n", encoding="utf-8")

    page = wiki_ingest.build_wiki_page(src, "note", "source", "# 標題\n內容", domain)
    assert "sources: [raw/local/note.md]" in page
    assert str(tmp_path) not in page, "頁面裡漏出了絕對路徑"


def test_signature_requires_domain_root():
    """🔴 釘住 `domain_root` 是**必填**。

    給它預設值（例如 `Path(".")`）會讓呼叫端漏傳時靜默產出錯的路徑
    —— 而那正是這個 bug 原本的樣子：沒有人需要提供基準，所以沒有人提供。
    """
    import inspect
    sig = inspect.signature(wiki_ingest.build_wiki_page)
    p = sig.parameters["domain_root"]
    assert p.default is inspect.Parameter.empty, (
        "domain_root 有了預設值 —— 呼叫端漏傳會靜默產出錯的 sources")


# ── source-id bucket 提醒（ADR-009）：提醒但不擋 ────────────────

def _rel(tmp_path, rel: str, capsys):
    import wiki_ingest
    root = tmp_path / "pkg"
    src = root / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# x\n", encoding="utf-8")
    out = wiki_ingest.relative_source(src, root)
    return out, capsys.readouterr().err


def test_flat_raw_file_gets_a_reminder_but_still_works(tmp_path, capsys):
    """🔴 契約是 ADR-009 的 `raw/<source-id>/…`，素材直接躺在 raw/ 底下要提醒。

    **不擋**：既有散檔多數已遷移完，這條的價值在攔住新進來的；
    做成錯誤會讓正在遷移的人卡住。
    """
    out, err = _rel(tmp_path, "raw/a.md", capsys)
    assert out == "raw/a.md", "提醒不該改變回傳值"
    assert "source-id bucket" in err and "ADR-009" in err


def test_bucketed_source_is_silent(tmp_path, capsys):
    out, err = _rel(tmp_path, "raw/local/a.md", capsys)
    assert out == "raw/local/a.md"
    assert "source-id bucket" not in err, "合法形狀不該有雜訊"


def test_deeper_bucket_path_is_silent(tmp_path, capsys):
    out, err = _rel(tmp_path, "raw/statistics/2026/a.md", capsys)
    assert out == "raw/statistics/2026/a.md"
    assert "source-id bucket" not in err


def test_non_raw_path_is_not_judged_by_this_rule(tmp_path, capsys):
    """只管 raw/ 底下的版面 —— 別的位置不是這條規則的範圍"""
    out, err = _rel(tmp_path, "docs/a.md", capsys)
    assert out == "docs/a.md"
    assert "source-id bucket" not in err
