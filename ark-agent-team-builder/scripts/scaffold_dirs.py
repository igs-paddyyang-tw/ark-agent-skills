"""讀 team.yaml，建立 agents/ 目錄骨架。

Usage:
    python scaffold_dirs.py [path/to/team.yaml]

為每個 instance 建立 working_directory 下的 knowledge/ 和 docs/ 子目錄。
冪等：已存在的目錄不會被修改。
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def scaffold(team_path: Path, base: Path | None = None) -> list[str]:
    """建立目錄，回傳已建立的路徑清單。"""
    base = base or team_path.parent
    with open(team_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if not isinstance(cfg, dict):
        print("❌ team.yaml is not a valid YAML mapping")
        return []

    created: list[str] = []
    for name, inst in cfg.get("instances", {}).items():
        wd = inst.get("working_directory", f"agents/{name}")
        # Skip instances with absolute paths or '.' (admin/self-referencing)
        if wd == "." or Path(wd).is_absolute():
            continue

        agent_dir = base / wd
        for sub in ("knowledge", "docs"):
            d = agent_dir / sub
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                gitkeep = d / ".gitkeep"
                if not gitkeep.exists():
                    gitkeep.touch()
                created.append(str(d.relative_to(base)))

    return created


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("team.yaml")
    if not target.exists():
        print(f"❌ {target} not found")
        sys.exit(1)

    dirs = scaffold(target)
    if dirs:
        print(f"✅ Created {len(dirs)} directories:")
        for d in dirs:
            print(f"  📁 {d}")
    else:
        print("ℹ️ All directories already exist (or no relative working_directory found)")


if __name__ == "__main__":
    main()
