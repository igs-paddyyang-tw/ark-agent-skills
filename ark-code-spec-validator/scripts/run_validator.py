"""Wrapper script for running the code-spec validator.

Usage:
    py scripts/run_validator.py [--full] [project_root]
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

    if args:
        project_root = args[0]

    cmd.append(project_root)

    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


if __name__ == "__main__":
    # 🔴 在讀位置參數之前攔截 —— 否則 `--help` 會被當成路徑，
    #    輕則 exit≠0，重則在 cwd 產出整包骨架（scripts/tests/test_cli_contract.py 在驗）。
    if {"-h", "--help"} & set(sys.argv[1:]):
        print(__doc__ or "")
        raise SystemExit(0)
    main()
