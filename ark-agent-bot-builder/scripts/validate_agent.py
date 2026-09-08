"""validate_agent.py — 驗證 ark_bot_agent 消費端骨架完整性。

用法：python validate_agent.py <project_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_FILES = ["start.py", "bot.yaml", "agents.yaml", ".env", "requirements.txt"]
REQUIRED_DIRS = [
    ".kiro/steering",
    "knowledge/shared/wiki",
    "knowledge/shared/raw",
    "knowledge/raw/memory-archive",
    "memory/daily",
    "artifacts/reports",
]


def validate(root: Path) -> list[str]:
    issues: list[str] = []
    for f in REQUIRED_FILES:
        if not (root / f).is_file():
            issues.append(f"缺檔案：{f}")
    for d in REQUIRED_DIRS:
        if not (root / d).is_dir():
            issues.append(f"缺目錄：{d}/")

    # start.py 必須走套件入口
    sp = root / "start.py"
    if sp.is_file() and "run_bot" not in sp.read_text(encoding="utf-8"):
        issues.append("start.py 未使用 run_bot（套件入口）")

    # 佔位符殘留檢查
    for f in ("bot.yaml", "agents.yaml"):
        p = root / f
        if p.is_file() and "{" in p.read_text(encoding="utf-8"):
            issues.append(f"{f} 仍有未替換的佔位符 {{...}}")

    return issues


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python validate_agent.py <project_dir>")
        return 2
    root = Path(sys.argv[1]).resolve()
    issues = validate(root)
    if issues:
        print(f"❌ {len(issues)} 個問題：")
        for i in issues:
            print(f"   - {i}")
        return 1
    print(f"✅ 骨架完整：{root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
