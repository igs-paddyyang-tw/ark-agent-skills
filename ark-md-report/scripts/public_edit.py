"""公開版去敏的替換小工具：供專案自己的 make_public 腳本 import。

替換清單依報告內容而寫，無法共用；共用的是「替換一定要命中、而且只命中一次」這條紀律。
`str.replace` 找不到目標時靜默無動作、找到多處時全部換掉 —— 報告文字改了以後，
去敏腳本會悄悄失效，敏感字串就這樣留在公開版裡。`must()` 讓這種情況直接報錯。

用法（專案腳本內）：
    import sys; sys.path.insert(0, "<ark-md-report>/scripts")
    from public_edit import must, must_all, strip_frontmatter

    body = must(body, "（commit a8748b8）", "")
    body = must_all(body, [("Golden Hoyeah 老虎機", "老虎機"), ("釘 commit", "釘版本")])
"""
from __future__ import annotations

import re

_FM = re.compile(r"\A---\n.*?\n---\n", re.S)


class EditMiss(AssertionError):
    """替換目標沒命中或命中不只一次。"""


def must(text: str, old: str, new: str) -> str:
    """把 old 換成 new；old 必須剛好出現一次，否則拋 EditMiss。"""
    n = text.count(old)
    if n != 1:
        raise EditMiss(f"預期命中 1 次，實際 {n} 次：{old[:70]!r}")
    return text.replace(old, new)


def must_all(text: str, pairs: list[tuple[str, str]]) -> str:
    """依序套用多組 must()；任一組失敗就停。"""
    for old, new in pairs:
        text = must(text, old, new)
    return text


def strip_frontmatter(text: str) -> tuple[str, str]:
    """拆出 frontmatter 與內文，回傳 (frontmatter 原文含分隔線, 內文)；沒有 frontmatter 時前者為空字串。"""
    m = _FM.match(text)
    return (m.group(0), text[m.end():]) if m else ("", text)
