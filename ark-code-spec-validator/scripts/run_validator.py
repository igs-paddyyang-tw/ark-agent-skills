"""Wrapper script for running the code-spec validator.

Usage:
    py scripts/run_validator.py [--full] [project_root]
    py scripts/run_validator.py [--full] --target <project_root>   # 與 SKILL.md 的寫法相容
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    args = sys.argv[1:]
    project_root = "."

    cmd = [sys.executable, "-m", "ark_team_agent.code_spec_validator"]

    if "--full" in args:
        cmd.append("--full")
        args.remove("--full")

    if "--target" in args:                 # SKILL.md 示範的寫法；原本會把 '--target' 當成路徑（2026-10-30）
        i = args.index("--target")
        if i + 1 >= len(args):
            sys.exit("--target 後面要接專案路徑")
        project_root = args[i + 1]
        del args[i:i + 2]
    elif args:
        project_root = args[0]

    cmd.append(project_root)

    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


if __name__ == "__main__":
    # 🔴 在讀位置參數之前攔截 —— 否則 `--help` 會被當成路徑，
    #    輕則 exit≠0，重則在 cwd 產出整包骨架。
    if {"-h", "--help"} & set(sys.argv[1:]):
        print(__doc__ or "")
        raise SystemExit(0)
    main()
