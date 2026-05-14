"""ark-env-doctor: 開發環境診斷與修復工具"""
import argparse
import sys
import os
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8")

from detectors import detect_python, detect_go, detect_node, detect_packages, detect_system
from installers import generate_fix_commands
from reporter import generate_report, generate_fix_scripts


def main():
    parser = argparse.ArgumentParser(description="開發環境診斷與修復")
    parser.add_argument("--fix", action="store_true", help="自動執行修復")
    parser.add_argument("--check", choices=["python", "go", "node"], help="僅檢查特定語言")
    parser.add_argument("--output", default="env_report.md", help="報告輸出路徑")
    args = parser.parse_args()

    project_root = Path.cwd()

    # 偵測
    result = {"system": detect_system()}

    if not args.check or args.check == "python":
        result["python"] = detect_python()
        result["python_packages"] = detect_packages(project_root / "requirements.txt")

    if not args.check or args.check == "go":
        result["go"] = detect_go()

    if not args.check or args.check == "node":
        result["node"] = detect_node()
        result["node_packages"] = detect_packages(project_root / "package.json", pkg_type="node")

    # 報告
    report = generate_report(result)
    print(report)

    Path(args.output).write_text(report, encoding="utf-8")
    print(f"\n📄 報告已儲存: {args.output}")

    # 修復
    fix_cmds = generate_fix_commands(result)
    if fix_cmds:
        generate_fix_scripts(fix_cmds)
        print("📝 修復腳本已產出: fix_env.sh / fix_env.ps1")

        if args.fix:
            import subprocess
            print("\n🔧 執行自動修復...")
            for cmd in fix_cmds:
                print(f"  → {cmd}")
                subprocess.run(cmd, shell=True)
            print("✅ 修復完成")
    else:
        print("\n✅ 環境正常，無需修復")


if __name__ == "__main__":
    main()
