#!/usr/bin/env python3
"""依角色矩陣同步各 agent 的 skill（從上游 ark-agent-skills 複製）。

為什麼需要這支腳本
------------------
market-team 的 skill 是**複本**不是 symlink（symlink 指向 repo 外絕對路徑，
clone 到新機器必斷鏈）。複本讓專案自我完備，代價是上游更新不會自動同步
→ 靠本腳本從上游 `ark-agent-skills` 拉齊。

同時做**角色邊界**：每個 agent 只裝該職責用得到的 skill，避免無關 skill
稀釋 context（skill 會進 agent 的 context window）。

上游來源
--------
`~/kiro-cli/.kiro/skills/`（git repo: igs-paddyyang-tw/ark-agent-skills）

用法
----
    python3 scripts/sync_skills.py            # 依矩陣同步
    python3 scripts/sync_skills.py --dry-run  # 只印要做什麼
    python3 scripts/sync_skills.py --check    # 只檢查是否一致（不改檔）

> 🔴 team.yaml 的 `kiro_files.skills.policy` 必須是 `skip` ——
> 否則套件 `_deploy_skills` 每次啟動會把 bundled skill 推翻本腳本的角色矩陣。
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

# 上游 skill 庫（git repo: igs-paddyyang-tw/ark-agent-skills）
UPSTREAM = Path.home() / "kiro-cli" / ".kiro" / "skills"

# 全員共用：SOUL 指定 wiki_query 為主力查詢工具
COMMON = ["ark-wiki-engine"]

# 角色矩陣（不含 COMMON）—— 市場情報團隊 6 instance
MATRIX: dict[str, list[str]] = {
    # 🗺️ 總機（積極型通用 AI）：意圖路由、知識查詢、能做的直接做，深工轉派 leader
    #    具備：RAG 查詢 + 規格/計畫執行 + 報告 + 需求澄清
    "market-agent": ["ark-weknora-cli", "ark-superpowers", "ark-project-planning",
                     "ark-planning-with-files", "ark-md-report", "ark-html-report",
                     "ark-grill-me"],
    # 🎯 統籌：拆解情報需求、派工、驗收彙整
    "leader-agent": ["ark-project-planning", "ark-superpowers", "ark-grill-me",
                     "ark-md-report"],
    # 👑 維運：環境、健康、成本、日報
    "admin-agent": ["ark-env-doctor", "ark-dashboard-health", "ark-cost-tracker",
                    "ark-md-report", "ark-html-report"],
    # 🔍 競品分析：抓競品資料、對比、態勢報告
    "competitor-agent": ["ark-web-scraper", "ark-marketing", "ark-chart-generator",
                         "ark-md-report", "ark-html-report", "ark-weknora-cli"],
    # 📈 趨勢研究：市場動態、新品、法規、玩家偏好
    "trend-agent": ["ark-web-scraper", "ark-daily-news", "ark-marketing",
                    "ark-md-report", "ark-html-report", "ark-weknora-cli"],
    # 📝 情報報告：彙整分析為 MD→HTML→TG 報告
    "report-agent": ["ark-md-report", "ark-html-report", "ark-chart-generator",
                     "ark-ingest-guard"],
}

ROOT = Path(__file__).resolve().parent.parent

# manager 的 working_directory 是專案根（team.yaml: market-agent wd="."）
MANAGER = "market-agent"


def wanted(agent: str) -> set[str]:
    """該 agent 應有的 skill 集合。"""
    return set(COMMON) | set(MATRIX.get(agent, []))


def skills_dir(agent: str) -> Path:
    """agent 的 skill 目錄；manager 的 working_directory 是專案根。"""
    base = ROOT if agent == MANAGER else ROOT / "agents" / agent
    return base / ".kiro" / "skills"


def source_of(name: str) -> Path:
    """skill 來源：一律從上游取（market-team 無自建 skill）。"""
    return UPSTREAM / name


def _deprecated(src: Path) -> bool:
    """上游是否已把此 skill 降級（兩種樣態都擋）。

    ① 完全 stub：沒 SKILL.md，只留標 DEPRECATED 的 README
    ② 半降級：SKILL.md 在，但 frontmatter `status:` 非 active
    """
    skill_md = src / "SKILL.md"
    if not skill_md.is_file():
        readme = src / "README.md"
        return readme.is_file() and "DEPRECATED" in readme.read_text(
            encoding="utf-8", errors="replace")[:200]
    head = skill_md.read_text(encoding="utf-8", errors="replace")[:1500]
    m = re.search(r"^\s*status:\s*(\S+)", head, re.M)
    return bool(m) and m.group(1).strip().strip('"\'') != "active"


def _differs(a: Path, b: Path) -> bool:
    """比對兩個 skill 目錄的檔案內容（忽略 __pycache__）。"""
    def snap(root: Path) -> dict[str, bytes]:
        out = {}
        for f in root.rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts:
                out[str(f.relative_to(root))] = f.read_bytes()
        return out
    return snap(a) != snap(b)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只印要做什麼")
    ap.add_argument("--check", action="store_true", help="只檢查一致性，不改檔")
    args = ap.parse_args()

    if not UPSTREAM.is_dir():
        print(f"🔴 上游 skill 庫不存在：{UPSTREAM}")
        print("   git clone https://github.com/igs-paddyyang-tw/ark-agent-skills.git "
              f"{UPSTREAM}")
        return 1

    added = removed = updated = 0
    problems: list[str] = []

    for agent in MATRIX:
        d = skills_dir(agent)
        want = wanted(agent)
        have = {p.name for p in d.iterdir() if p.is_dir()} if d.is_dir() else set()

        # 來源缺漏／降級先擋下，不靜默略過
        for name in sorted(want):
            src = source_of(name)
            if not src.is_dir():
                problems.append(f"{agent}: 來源不存在 {src}")
            elif _deprecated(src):
                problems.append(f"{agent}: {name} 已被上游標為 DEPRECATED → 改用替代 skill")

        for name in sorted(want - have):
            src = source_of(name)
            if not src.is_dir():
                continue
            print(f"  ➕ {agent:18} {name}")
            added += 1
            if not (args.dry_run or args.check):
                d.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, d / name)

        for name in sorted(have - want):
            print(f"  ➖ {agent:18} {name}")
            removed += 1
            if not (args.dry_run or args.check):
                shutil.rmtree(d / name)

        for name in sorted(want & have):
            src = source_of(name)
            if not src.is_dir():
                continue
            if _differs(src, d / name):
                print(f"  🔄 {agent:18} {name}（與來源不同 → 更新）")
                updated += 1
                if not (args.dry_run or args.check):
                    shutil.rmtree(d / name)
                    shutil.copytree(src, d / name)

    for p in problems:
        print(f"  🔴 {p}")

    total = added + removed + updated
    mode = "檢查" if args.check else ("預覽" if args.dry_run else "同步")
    print(f"\n{mode}結果：新增 {added}｜移除 {removed}｜更新 {updated}")
    if problems:
        return 1
    if args.check and total:
        print("⚠️ 與矩陣不一致 → 執行 python3 scripts/sync_skills.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
