"""報告與修復腳本產出模組"""
from pathlib import Path


def generate_report(result: dict) -> str:
    """產出 Markdown 格式環境診斷報告"""
    lines = ["# 🧠 Environment Report\n"]

    # System
    if "system" in result:
        s = result["system"]
        lines.append("## System")
        lines.append(f"- OS: {s['os']} {s['arch']}")
        lines.append(f"- Shell: {s['shell']}\n")

    # Python
    if "python" in result:
        p = result["python"]
        icon = "✅" if p["exists"] else "❌"
        lines.append(f"## Python {icon}")
        lines.append(f"- Version: {p['version']}")
        lines.append(f"- Path: {p['path']}")
        venv_status = f"active ({p['venv_path']})" if p["venv_active"] else "inactive"
        lines.append(f"- venv: {venv_status}")
        if p["pip"]:
            pip_ver = p["pip"].split("(")[0].strip().split()[-1] if p["pip"] else "N/A"
            lines.append(f"- pip: {pip_ver}")
        lines.append("")

    # Go
    if "go" in result:
        g = result["go"]
        icon = "✅" if g["exists"] else "⚠️"
        lines.append(f"## Go {icon}")
        if g["exists"]:
            lines.append(f"- Version: {g['version']}")
            lines.append(f"- GOPATH: {g['gopath']}")
        else:
            lines.append("- Not found in PATH")
        lines.append("")

    # Node
    if "node" in result:
        n = result["node"]
        icon = "✅" if n["exists"] else "⚠️"
        lines.append(f"## Node.js {icon}")
        if n["exists"]:
            lines.append(f"- Version: {n['version']}")
            lines.append(f"- npm: {n['npm']}")
            if n["pnpm"]:
                lines.append(f"- pnpm: {n['pnpm']}")
        else:
            lines.append("- Not found in PATH")
        lines.append("")

    # Missing packages
    for key in ["python_packages", "node_packages"]:
        if key in result and result[key].get("missing"):
            pkg_type = "Python" if "python" in key else "Node"
            lines.append(f"## Missing {pkg_type} Packages ({len(result[key]['missing'])})")
            for pkg in result[key]["missing"]:
                lines.append(f"- {pkg}")
            lines.append("")

    return "\n".join(lines)


def generate_fix_scripts(cmds: list[str]):
    """產出 fix_env.sh 和 fix_env.ps1"""
    # Bash
    sh_lines = ["#!/bin/bash", "set -e", "echo '🔧 Fixing environment...'\n"]
    for cmd in cmds:
        if cmd.startswith("venv\\"):
            continue  # skip Windows-only activate
        sh_cmd = cmd.replace("venv\\Scripts\\activate", "source venv/bin/activate")
        sh_lines.append(sh_cmd)
    sh_lines.append("\necho '✅ Done!'")
    Path("fix_env.sh").write_text("\n".join(sh_lines), encoding="utf-8")

    # PowerShell
    ps_lines = ["# fix_env.ps1", "Write-Host '🔧 Fixing environment...'\n"]
    for cmd in cmds:
        if cmd.startswith("source "):
            continue  # skip Unix-only activate
        ps_lines.append(cmd)
    ps_lines.append("\nWrite-Host '✅ Done!'")
    Path("fix_env.ps1").write_text("\n".join(ps_lines), encoding="utf-8")
