#!/usr/bin/env python3
"""gen_readme.py — 由各 SKILL.md 的 frontmatter 重新產生 README 的目錄章節。

## 為何需要這支腳本

2026-08-12 盤點時，README 出現三個互不相同的數字：

| 來源 | 數字 |
|------|-----:|
| 標題宣稱 | 66 |
| 分類表實際列出 | 57 |
| 目錄裡有 `SKILL.md` | **63** |

原因是目錄與 README 各自演化：新增 skill 沒補進表格（`ark-md-report` 這個
改版主角只出現在 changelog）、移除的 skill 沒從表格拿掉（`ark-report-template`
已是 deprecated stub 卻仍列在「⑤ 文件輸出」）。

**手動維護一份會過期的索引，就是這種漂移的來源。** 這支腳本讓 README 的
目錄章節由 frontmatter 推導 —— 資料只有一份。

## 用法

    python scripts/gen_readme.py            # 重寫 README 目錄章節
    python scripts/gen_readme.py --check    # 只檢查是否過期（CI 用，過期回非 0）

**Changelog 與「分類規格」章節是手寫的，腳本會原樣保留。** 只有兩條分隔線之間
的目錄章節會被重寫。

## Deprecated skill

**兩種形態都算 deprecated**，都不列入目錄也不計入總數，但會在頁尾另立一節
說明去向 —— 直接消失會讓還在用舊 skill 的人找不到遷移路徑。詳見 `scan()`。

判定結果與 `ark-skills-align/scripts/audit_skills.py` 對帳：兩者的
active / deprecated 數字必須一致，不一致代表其中一方的判定漏了形態。
"""
# ── Change Log ────────────────────────────────────────────
# 2026-08-12 | admin-agent | init: 修 README 與目錄脫節（三個數字對不上）
# 2026-08-12 | admin-agent | fix: deprecated 判定補上 frontmatter status
#              （原本只認「沒有 SKILL.md」，5 個標記型被誤列為 active）
# 2026-09-04 | admin-agent | feat: 登記 executor 分類（ark-db-query v2 executor 化後
#              未補登記，重產 README 會落到「⚠️ 未分類」）
# 2026-09-04 | admin-agent | fix: 移除 ⑤ presentation-content 節並重編號 ——
#              audit_skills.py 已把該值列為 legacy 別名（P3 → document），
#              這裡卻還當現行分類展示且恆印「（目前無）」，兩道守門說法不一致
# ──────────────────────────────────────────────────────────
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

#: 章節順序與標題。key 對應 SKILL.md frontmatter 的 `metadata.category`。
#:
#: 新增分類時**必須同時**在這裡登記 —— 否則該 skill 會被歸到「未分類」，
#: 那一節的存在就是為了讓漏登記看得見，而不是靜默漏掉。
SECTIONS = [
    ("process",              "① 流程鏈 Process",          "MD 給 AI"),
    ("scaffolder",           "② 平台生成器 Scaffolders",   "專案骨架"),
    ("pipeline",             "③ 管線元件 Pipeline",        "結構化資料"),
    ("view",                 "④ 呈現層 View",              "HTML / 視覺（給人看）"),
    ("document",             "⑤ 文件輸出 Document",        "MD / Office"),
    ("domain",               "⑥ 領域 SOP Domain",          "策略分析 MD"),
    ("ops",                  "⑦ 維運 Ops",                 "診斷 / 驗證"),
    ("executor",             "⑧ 執行器 Executor",          "捆綁 scripts，agent 直接跑"),
]

_FM = re.compile(r"^---\s*\n(.*?)\n---", re.S)
_CATEGORY = re.compile(r"^\s{2,}category:\s*([A-Za-z0-9_-]+)", re.M)
_STATUS = re.compile(r"^\s{2,}status:\s*([A-Za-z0-9_-]+)", re.M)
_DESC = re.compile(r"^description:\s*(\|[-+]?)?\s*(.*?)(?=^\w|\Z)", re.M | re.S)
_MIGRATED = re.compile(r"\*\*Migrated to\*\*:\s*(.+)")
#: SKILL.md 內的 deprecation 說明。格式如
#: `description: "⚠️ DEPRECATED — 已合併至 ark-agent-builder。"`
_DEPRECATED_NOTE = re.compile(r"DEPRECATED\s*[—\-–]\s*(.+?)(?:\n|$)")

MARK_START = "<!-- BEGIN GENERATED CATALOGUE -->"
MARK_END = "<!-- END GENERATED CATALOGUE -->"


def _first_line(desc: str, limit: int = 100) -> str:
    """取描述第一句當定位。表格容不下整段 description。"""
    text = " ".join(desc.split())
    text = text.strip().strip('"')
    for sep in ("。", "．"):
        if sep in text[:limit]:
            return text[: text.index(sep) + 1]
    return text[:limit] + ("…" if len(text) > limit else "")


def scan() -> tuple[dict[str, list[tuple[str, str]]], list[tuple[str, str]]]:
    """掃描所有 skill 目錄。

    ## deprecated 有兩種形態，兩種都要認

    初版只認第一種，於是 5 個第二種的 skill 被當成 active 列進分類表 ——
    正是這支腳本原本要修的那類錯誤（2026-08-12 發現）：

    | 形態 | 判定 | 例 |
    |------|------|---|
    | 目錄只剩 `README.md` | 沒有 `SKILL.md` | `ark-report-template` |
    | **保留 `SKILL.md`，frontmatter 標記** | `status: deprecated` 或 `category: deprecated` | `ark-llm-cli` |

    第二種保留 SKILL.md 是為了讓觸發詞仍能導向遷移說明 —— 使用者說出舊 skill
    的關鍵字時，agent 會讀到「已合併至 X」而不是完全沒反應。

    Returns:
        (依分類分組的 active skill, deprecated 清單 `[(名稱, 去向)]`)
    """
    active: dict[str, list[tuple[str, str]]] = {}
    deprecated: list[tuple[str, str]] = []

    for d in sorted(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("ark-")):
        skill_md = d / "SKILL.md"

        # 形態一：目錄只剩 README stub
        if not skill_md.exists():
            readme = d / "README.md"
            去向 = ""
            if readme.exists():
                m = _MIGRATED.search(readme.read_text(encoding="utf-8", errors="replace"))
                去向 = m.group(1).strip() if m else ""
            deprecated.append((d.name, 去向))
            continue

        text = skill_md.read_text(encoding="utf-8", errors="replace")
        fm = _FM.search(text)
        block = fm.group(1) if fm else ""
        cat_m = _CATEGORY.search(block)
        cat = cat_m.group(1) if cat_m else "__uncategorised__"
        status_m = _STATUS.search(block)
        status = (status_m.group(1) if status_m else "active").lower()

        # 形態二：SKILL.md 還在，但 frontmatter 標記已廢
        if status == "deprecated" or cat == "deprecated":
            note = _DEPRECATED_NOTE.search(text)
            去向 = note.group(1).strip().rstrip('"。') if note else ""
            deprecated.append((d.name, 去向))
            continue

        desc_m = _DESC.search(block)
        desc = _first_line(desc_m.group(2)) if desc_m else "（無描述）"
        active.setdefault(cat, []).append((d.name, desc))

    return active, deprecated


def render(active: dict, deprecated: list) -> str:
    total = sum(len(v) for v in active.values())
    known = {k for k, _, _ in SECTIONS}
    未分類 = sorted(set(active) - known)

    L = [MARK_START, "", f"> **{total} 個 Skill**，兩層分類（職能角色 × 受眾）。",
         "> 本節由 `scripts/gen_readme.py` 依各 `SKILL.md` 的 frontmatter 產生，**不要手動編輯**。", ""]

    for key, title, audience in SECTIONS:
        rows = sorted(active.get(key, []))
        L += [f"## {title}", "", f"> 輸出：{audience}｜`category: {key}`｜{len(rows)} 個", ""]
        if not rows:
            L += ["（目前無）", ""]
            continue
        L += ["| Skill | 定位 |", "|-------|------|"]
        L += [f"| `{n}` | {d.replace('|', '｜')} |" for n, d in rows]
        L += [""]

    if 未分類:
        L += ["## ⚠️ 未分類", "",
              "> 這些 skill 的 `metadata.category` 不在 `SECTIONS` 登記表內。",
              "> 要嘛補登記，要嘛修正 frontmatter —— 留在這一節代表分類治理有缺口。", "",
              "| Skill | category |", "|-------|----------|"]
        for cat in 未分類:
            for n, _ in sorted(active[cat]):
                L += [f"| `{n}` | `{'（無）' if cat == '__uncategorised__' else cat}` |"]
        L += [""]

    if deprecated:
        L += ["## 🗑️ 已移除（保留供遷移）", "",
              "> 兩種形態：目錄只剩 `README.md`，或保留 `SKILL.md` 但 frontmatter 標 "
              "`status: deprecated`（讓舊觸發詞仍導向遷移說明）。**不計入上方總數。**", "",
              "| Skill | 遷移到 |", "|-------|--------|"]
        L += [f"| `{n}` | {去向 or '—'} |" for n, 去向 in sorted(deprecated)]
        L += [""]

    L += [MARK_END]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="由 frontmatter 重產 README 目錄章節")
    ap.add_argument("--check", action="store_true", help="只檢查是否過期，不寫檔")
    args = ap.parse_args()

    active, deprecated = scan()
    catalogue = render(active, deprecated)
    old = README.read_text(encoding="utf-8")

    if MARK_START in old and MARK_END in old:
        head = old[: old.index(MARK_START)]
        tail = old[old.index(MARK_END) + len(MARK_END):]
        new = head + catalogue + tail
    else:
        print("❌ README 找不到產生區標記，請先手動加入：", file=sys.stderr)
        print(f"   {MARK_START} … {MARK_END}", file=sys.stderr)
        return 2

    if args.check:
        if new != old:
            print("❌ README 目錄章節已過期，請執行：python scripts/gen_readme.py", file=sys.stderr)
            return 1
        print("✅ README 與目錄一致")
        return 0

    README.write_text(new, encoding="utf-8")
    total = sum(len(v) for v in active.values())
    print(f"✅ README 已更新：{total} 個 active、{len(deprecated)} 個 deprecated stub")
    未分類 = sorted(set(active) - {k for k, _, _ in SECTIONS})
    if 未分類:
        print(f"⚠️  未分類 category：{未分類}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
