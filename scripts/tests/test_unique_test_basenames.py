"""測試檔名不得重複 —— pytest 用 basename 當 module 名。

## 為什麼需要這支

同名的兩個 `test_x.py`（沒有 `__init__.py` 時）會讓 pytest collection 直接中斷：

    import file mismatch: imported module 'test_cli_contract' has this __file__ …

**整包測試跑不起來**，不是少跑一條 —— 所有守門同時失效，而錯誤訊息長得像環境問題。

2026-09-14~16 這個衝突發生了**三次**（`test_scaffold.py` ×2、
`test_cli_contract.py` 在 `ark-skill-creator` 與 `ark-superpowers` 各一次），
每次都是不同的人在自己的 skill 底下建了一個「很自然的通用名字」。

> 💡 判準：**同一個坑踩第三次就該有守門，不是再改一次名。**
> 這條的修法對作者也友善 —— 它直接告訴你該叫什麼。
"""
from __future__ import annotations

import collections
from pathlib import Path

SKILLS_REPO = Path(__file__).resolve().parent.parent.parent


def test_no_duplicate_test_file_basenames():
    files = [p for p in SKILLS_REPO.rglob("test_*.py")
             if "__pycache__" not in p.parts and ".git" not in p.parts]
    by_name: dict[str, list[Path]] = collections.defaultdict(list)
    for p in files:
        by_name[p.name].append(p)

    dupes = {n: ps for n, ps in by_name.items() if len(ps) > 1}
    if dupes:
        lines = []
        for n, ps in sorted(dupes.items()):
            owners = [p.relative_to(SKILLS_REPO).parts[0] for p in ps]
            lines.append(f"  {n} —— {', '.join(owners)}")
            lines.append(f"     改成帶 skill 名的唯一檔名，例如 "
                         f"test_{owners[-1].removeprefix('ark-').replace('-', '_')}_"
                         f"{n.removeprefix('test_')}")
        raise AssertionError(
            "測試檔名重複會讓 pytest collection 整包中斷（所有守門一起失效）：\n"
            + "\n".join(lines))

    assert files, "一個 test_*.py 都沒掃到 —— 掃描範圍錯了"
