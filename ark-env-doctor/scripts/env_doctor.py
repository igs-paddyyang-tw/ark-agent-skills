"""ark-env-doctor: 開發環境診斷與修復工具"""
import argparse
import sys
import os
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8")

from detectors import detect_python, detect_go, detect_node, detect_packages, detect_system, detect_git, detect_gemini, detect_kiro
from installers import generate_fix_commands
from reporter import generate_report, generate_fix_scripts


def run_endpoints(args) -> int:
    """端點模式：任一失敗 exit 1（可直接接排程或 CI）。"""
    from endpoints import check_all, load_endpoints, render
    eps = load_endpoints(args.endpoints, args.sse, args.endpoints_file)
    if not eps:
        print("⏭  沒有任何端點可檢查（清單檔是空的）")
        return 0
    results = check_all(eps, args.timeout)
    report = render(results)
    print(report)
    out = Path(args.output or "endpoint_report.md")
    out.write_text(report, encoding="utf-8")
    print(f"📄 報告已儲存: {out}")
    return 0 if all(r["ok"] for r in results) else 1


def main():
    parser = argparse.ArgumentParser(description="開發環境診斷與修復")
    parser.add_argument("--fix", action="store_true", help="自動執行修復")
    parser.add_argument("--check", choices=["python", "go", "node"], help="僅檢查特定語言")
    parser.add_argument("--output", default=None,
                        help="報告輸出路徑（預設 env_report.md；端點模式 endpoint_report.md）")
    # 端點模式（2026-10-29 由 ark-dashboard-health 併入）：檢查已部署服務，不做開發機診斷
    parser.add_argument("--endpoints", nargs="+", metavar="URL", help="檢查這些端點（預設預期 2xx）")
    parser.add_argument("--sse", nargs="+", metavar="URL", help="檢查 SSE 端點（只驗 content-type，不等事件）")
    parser.add_argument("--endpoints-file", type=Path, help="端點清單 JSON／YAML（格式見 scripts/endpoints.py）")
    parser.add_argument("--timeout", type=float, default=5.0, help="端點模式每個請求的逾時秒數")
    args = parser.parse_args()

    if args.endpoints or args.sse or args.endpoints_file:
        return run_endpoints(args)
    args.output = args.output or "env_report.md"

    project_root = Path.cwd()

    # 偵測
    result = {"system": detect_system()}

    # 通用工具（永遠檢查）
    result["git"] = detect_git()
    result["gemini"] = detect_gemini()
    result["kiro"] = detect_kiro()

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
    sys.exit(main())
