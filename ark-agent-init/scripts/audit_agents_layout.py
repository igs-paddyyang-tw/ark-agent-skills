#!/usr/bin/env python3
"""audit_agents_layout.py — 稽核 workspace 的 AGENTS.md 佈局（單一權威見 SKILL.md「AGENTS.md 放哪」）。

規則（2.4.0 起）：
    1. 專案根有 `AGENTS.md`（SSOT）
    2. team.yaml 編制內、working_directory 不是 "." 的 agent，其**工作目錄根**有 `AGENTS.md`（複本）
    3. 任何 `.kiro/steering/AGENTS.md` 都不應存在 —— 例外：symlink 指向同層 workspace 根的
       `AGENTS.md`（同一份內容，不構成兩份並存，例：nana-bot 刻意保留的 steering symlink）

只看 team.yaml **編制內**的 agent：編制外的殘留目錄（已裁撤角色的空殼）不檢查，
否則會製造假紅。缺 team.yaml 或編制為空 → 明說「跳過」，不偽裝成通過。

用法:
    python audit_agents_layout.py [project_dir] [--json]

exit: 0 通過或跳過；1 有違規；2 參數錯誤。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def _steering_agents_ok(steering_agents: Path, expected: Path) -> bool:
    """steering/AGENTS.md 只在「symlink 指向 workspace 根那份」時可接受。"""
    if not steering_agents.is_symlink():
        return False
    try:
        return steering_agents.resolve() == expected.resolve()
    except OSError:
        return False


def check_layout(project_dir: Path, instances: dict) -> list[dict]:
    """回傳違規清單；每筆 {agent, problem, fix}，訊息可直接照做。"""
    project_dir = Path(project_dir)
    issues: list[dict] = []
    root_agents = project_dir / "AGENTS.md"
    if not root_agents.exists():
        issues.append({"agent": "(專案根)", "problem": "缺 AGENTS.md（SSOT）",
                       "fix": f"在 {root_agents} 建立；團隊規範只在這裡改"})

    for name, inst in (instances or {}).items():
        wd = (inst or {}).get("working_directory", f"agents/{name}")
        agent_root = project_dir if wd == "." else project_dir / wd
        expected = agent_root / "AGENTS.md"
        steering_agents = agent_root / ".kiro" / "steering" / "AGENTS.md"

        if wd != "." and not expected.exists():
            issues.append({"agent": name, "problem": f"{wd}/AGENTS.md 缺少",
                           "fix": f"複製專案根 AGENTS.md 到 {expected}（或重跑 build_kiro.py）"})
        if (steering_agents.exists() or steering_agents.is_symlink()) \
                and not _steering_agents_ok(steering_agents, expected):
            rel = steering_agents.relative_to(project_dir)
            issues.append({"agent": name, "problem": f"{rel} 放錯（.kiro/steering/ 不放 AGENTS.md）",
                           "fix": f"內容併入 {expected.relative_to(project_dir)} 後刪除 {rel}"
                                  "（要保留就改成指向它的 symlink）"})
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description="稽核 AGENTS.md 佈局：專案根 1 份＋每個編制內 agent 根 1 份＋steering 0 份")
    ap.add_argument("project_dir", nargs="?", default=".")
    ap.add_argument("--json", action="store_true", help="機器可讀輸出")
    args = ap.parse_args()

    project_dir = Path(args.project_dir)
    team_yaml = project_dir / "team.yaml"
    if not team_yaml.exists():
        result = {"status": "skipped", "reason": f"找不到 {team_yaml}（不是 team workspace，未檢查）", "issues": []}
    else:
        cfg = yaml.safe_load(team_yaml.read_text(encoding="utf-8")) or {}
        instances = cfg.get("instances") or {}
        if not instances:
            result = {"status": "skipped", "reason": "team.yaml 沒有 instances（編制為空，未檢查）", "issues": []}
        else:
            issues = check_layout(project_dir, instances)
            result = {"status": "fail" if issues else "pass", "checked_agents": len(instances), "issues": issues}

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["status"] == "skipped":
        print(f"⏭️ 跳過：{result['reason']}")
    elif result["status"] == "pass":
        print(f"✅ AGENTS.md 佈局正確（{result['checked_agents']} 個編制內 agent）")
    else:
        print(f"❌ AGENTS.md 佈局 {len(result['issues'])} 處違規：")
        for i in result["issues"]:
            print(f"  - [{i['agent']}] {i['problem']} → {i['fix']}")
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
